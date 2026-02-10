# LEELOO Server

Backend services for LEELOO device communication.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LEELOO CLOUD                         │
│                                                         │
│  ┌─────────────┐              ┌─────────────┐          │
│  │  Telegram   │              │   WebSocket │          │
│  │    Bot      │──────────────│    Relay    │          │
│  └─────────────┘              └─────────────┘          │
│         │                            │                  │
└─────────┼────────────────────────────┼──────────────────┘
          │                            │
          ▼                            ▼
    ┌──────────┐                ┌──────────┐
    │ Amy's    │                │ Ben's    │
    │ Telegram │                │ LEELOO   │
    └──────────┘                └──────────┘
```

## Components

### 1. Relay Server (`relay_server.py`)

WebSocket server that routes messages between LEELOO devices.

**Key features:**
- Crew management (create, join, leave)
- Message routing (never decrypts content)
- Device presence (online/offline notifications)

**Run it:**
```bash
python relay_server.py
# Listens on ws://0.0.0.0:8765
```

### 2. Telegram Bot (`telegram_bot.py`)

Handles device pairing and optional phone messaging.

**Features:**
- Create/join crews via Telegram
- Send messages from phone to LEELOO devices
- Device pairing assistance

**Setup:**
1. Create bot with @BotFather on Telegram
2. Set token: `export LEELOO_BOT_TOKEN=your_token`
3. Run: `python telegram_bot.py`

## Privacy Design

- **Messages are end-to-end encrypted** - relay never sees content
- **Crew isolation** - messages only go to crew members
- **No storage** - messages are relayed, not stored
- **Optional Telegram** - works without phone integration

## Crew Codes

Human-readable codes like `LEELOO-7X3K` for easy sharing.

Characters used: `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`
(No I/O/0/1 to avoid confusion)

## Message Types

| Type | Description |
|------|-------------|
| `text` | Text message |
| `reaction` | Love/Fire reaction |
| `song_push` | Push a song to crew |

## Production Deployment

For production:
1. Use a VPS (DigitalOcean, Linode, etc.)
2. Add TLS (wss://) via nginx reverse proxy
3. Use Redis for crew/device state
4. Add rate limiting
5. Set up monitoring

Example nginx config:
```nginx
server {
    listen 443 ssl;
    server_name relay.leeloo.fm;

    ssl_certificate /etc/letsencrypt/live/relay.leeloo.fm/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/relay.leeloo.fm/privkey.pem;

    location / {
        proxy_pass http://localhost:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```
