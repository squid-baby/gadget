#!/usr/bin/env python3
"""
LEELOO Relay Server
WebSocket relay for crew-to-crew encrypted messaging.
The server NEVER sees message content - just routes encrypted blobs.
"""

import asyncio
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Optional
from datetime import datetime

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'websockets'])
    import websockets


@dataclass
class Device:
    """A connected LEELOO device"""
    device_id: str
    crew_id: str
    websocket: any
    display_name: str = "Unknown"
    connected_at: float = field(default_factory=time.time)


@dataclass
class Crew:
    """A group of LEELOO devices that can message each other"""
    crew_id: str
    crew_code: str  # Human-readable pairing code like "LEELOO-7X3K"
    created_at: float = field(default_factory=time.time)
    devices: Set[str] = field(default_factory=set)  # device_ids
    telegram_users: Set[int] = field(default_factory=set)  # telegram user ids


class LeelooRelay:
    def __init__(self):
        # crew_id -> Crew
        self.crews: Dict[str, Crew] = {}

        # device_id -> Device (only connected devices)
        self.connected_devices: Dict[str, Device] = {}

        # crew_code -> crew_id (for pairing lookup)
        self.crew_codes: Dict[str, str] = {}

        # Pending pairings: pairing_code -> {crew_id, expires_at}
        self.pending_pairings: Dict[str, dict] = {}

    def generate_crew_code(self) -> str:
        """Generate a human-readable crew code like LEELOO-7X3K"""
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No I/O/0/1 for clarity
        code = ''.join(secrets.choice(chars) for _ in range(4))
        return f"LEELOO-{code}"

    def generate_device_id(self) -> str:
        """Generate a unique device ID"""
        return f"dev_{secrets.token_hex(8)}"

    def create_crew(self) -> Crew:
        """Create a new crew with a unique code"""
        crew_id = secrets.token_hex(16)
        crew_code = self.generate_crew_code()

        # Ensure unique code
        while crew_code in self.crew_codes:
            crew_code = self.generate_crew_code()

        crew = Crew(crew_id=crew_id, crew_code=crew_code)
        self.crews[crew_id] = crew
        self.crew_codes[crew_code] = crew_id

        print(f"[CREW] Created new crew: {crew_code}")
        return crew

    def get_crew_by_code(self, code: str) -> Optional[Crew]:
        """Look up crew by human-readable code"""
        crew_id = self.crew_codes.get(code.upper())
        if crew_id:
            return self.crews.get(crew_id)
        return None

    async def handle_device(self, websocket, path):
        """Handle a device WebSocket connection"""
        device: Optional[Device] = None

        try:
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get('type')

                if msg_type == 'register':
                    # New device registering
                    device = await self.handle_register(websocket, data)

                elif msg_type == 'join_crew':
                    # Device joining existing crew
                    device = await self.handle_join_crew(websocket, data)

                elif msg_type == 'create_crew':
                    # Device creating new crew
                    device = await self.handle_create_crew(websocket, data)

                elif msg_type == 'message':
                    # Relay message to crew (we don't decrypt!)
                    if device:
                        await self.relay_message(device, data)

                elif msg_type == 'ping':
                    await websocket.send(json.dumps({'type': 'pong'}))

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if device:
                await self.handle_disconnect(device)

    async def handle_register(self, websocket, data) -> Device:
        """Handle device registration"""
        device_id = data.get('device_id') or self.generate_device_id()
        display_name = data.get('display_name', 'LEELOO')

        device = Device(
            device_id=device_id,
            crew_id="",  # Not in a crew yet
            websocket=websocket,
            display_name=display_name
        )

        self.connected_devices[device_id] = device

        await websocket.send(json.dumps({
            'type': 'registered',
            'device_id': device_id
        }))

        print(f"[DEVICE] Registered: {device_id} ({display_name})")
        return device

    async def handle_create_crew(self, websocket, data) -> Device:
        """Device creates a new crew"""
        device_id = data.get('device_id')
        display_name = data.get('display_name', 'LEELOO')

        # Create the crew
        crew = self.create_crew()

        # Create/update device
        device = Device(
            device_id=device_id or self.generate_device_id(),
            crew_id=crew.crew_id,
            websocket=websocket,
            display_name=display_name
        )

        crew.devices.add(device.device_id)
        self.connected_devices[device.device_id] = device

        await websocket.send(json.dumps({
            'type': 'crew_created',
            'device_id': device.device_id,
            'crew_id': crew.crew_id,
            'crew_code': crew.crew_code
        }))

        print(f"[CREW] Device {device.device_id} created crew {crew.crew_code}")
        return device

    async def handle_join_crew(self, websocket, data) -> Optional[Device]:
        """Device joins an existing crew"""
        device_id = data.get('device_id')
        crew_code = data.get('crew_code', '').upper()
        display_name = data.get('display_name', 'LEELOO')

        crew = self.get_crew_by_code(crew_code)
        if not crew:
            await websocket.send(json.dumps({
                'type': 'error',
                'error': 'invalid_crew_code',
                'message': f'Crew {crew_code} not found'
            }))
            return None

        # Create/update device
        device = Device(
            device_id=device_id or self.generate_device_id(),
            crew_id=crew.crew_id,
            websocket=websocket,
            display_name=display_name
        )

        crew.devices.add(device.device_id)
        self.connected_devices[device.device_id] = device

        await websocket.send(json.dumps({
            'type': 'crew_joined',
            'device_id': device.device_id,
            'crew_id': crew.crew_id,
            'crew_code': crew.crew_code,
            'crew_members': len(crew.devices)
        }))

        # Notify other crew members
        await self.broadcast_to_crew(crew.crew_id, {
            'type': 'member_joined',
            'device_id': device.device_id,
            'display_name': display_name
        }, exclude=device.device_id)

        print(f"[CREW] Device {device.device_id} joined crew {crew.crew_code}")
        return device

    async def relay_message(self, sender: Device, data: dict):
        """Relay an encrypted message to all crew members"""
        if not sender.crew_id:
            return

        crew = self.crews.get(sender.crew_id)
        if not crew:
            return

        # We relay the encrypted payload as-is
        # We NEVER decrypt or inspect the content
        relay_msg = {
            'type': 'message',
            'from_device': sender.device_id,
            'from_name': sender.display_name,
            'payload': data.get('payload'),  # Encrypted blob
            'msg_type': data.get('msg_type', 'text'),  # text, reaction, song_push, etc
            'timestamp': time.time()
        }

        await self.broadcast_to_crew(crew.crew_id, relay_msg, exclude=sender.device_id)
        print(f"[MSG] Relayed {data.get('msg_type', 'text')} from {sender.display_name} to crew")

    async def broadcast_to_crew(self, crew_id: str, message: dict, exclude: str = None):
        """Send message to all connected devices in a crew"""
        crew = self.crews.get(crew_id)
        if not crew:
            return

        msg_json = json.dumps(message)

        for device_id in crew.devices:
            if device_id == exclude:
                continue

            device = self.connected_devices.get(device_id)
            if device and device.websocket:
                try:
                    await device.websocket.send(msg_json)
                except:
                    pass  # Device disconnected, will be cleaned up

    async def handle_disconnect(self, device: Device):
        """Handle device disconnection"""
        print(f"[DEVICE] Disconnected: {device.device_id}")

        if device.device_id in self.connected_devices:
            del self.connected_devices[device.device_id]

        # Notify crew (device is still in crew, just offline)
        if device.crew_id:
            await self.broadcast_to_crew(device.crew_id, {
                'type': 'member_offline',
                'device_id': device.device_id,
                'display_name': device.display_name
            })

    async def run(self, host='0.0.0.0', port=8765):
        """Start the relay server"""
        print(f"[SERVER] LEELOO Relay starting on ws://{host}:{port}")

        async with websockets.serve(self.handle_device, host, port):
            await asyncio.Future()  # Run forever


# Telegram bot integration endpoint
class TelegramBridge:
    """Bridge between Telegram bot and relay server"""

    def __init__(self, relay: LeelooRelay):
        self.relay = relay

    def create_crew_for_telegram(self, telegram_user_id: int) -> str:
        """Called by Telegram bot when user wants to create a crew"""
        crew = self.relay.create_crew()
        crew.telegram_users.add(telegram_user_id)
        return crew.crew_code

    def join_crew_from_telegram(self, telegram_user_id: int, crew_code: str) -> bool:
        """Called by Telegram bot when user wants to join a crew"""
        crew = self.relay.get_crew_by_code(crew_code)
        if crew:
            crew.telegram_users.add(telegram_user_id)
            return True
        return False

    async def send_message_from_telegram(self, telegram_user_id: int, crew_code: str,
                                          message_payload: dict):
        """Called by Telegram bot to send message to crew devices"""
        crew = self.relay.get_crew_by_code(crew_code)
        if not crew or telegram_user_id not in crew.telegram_users:
            return False

        await self.relay.broadcast_to_crew(crew.crew_id, {
            'type': 'message',
            'from_device': 'telegram',
            'from_name': message_payload.get('sender_name', 'Phone'),
            'payload': message_payload.get('payload'),
            'msg_type': message_payload.get('msg_type', 'text'),
            'timestamp': time.time()
        })
        return True


if __name__ == '__main__':
    relay = LeelooRelay()
    asyncio.run(relay.run())
