#!/usr/bin/env python3
"""
LEELOO Boot Sequence
Handles the complete startup flow:
1. Splash screen (already shown by systemd)
2. WiFi check/setup
3. Crew check/setup (optional)
4. Main UI
"""

import os
import sys
import time
import subprocess
import asyncio

# Add boot directory to path
sys.path.insert(0, '/home/pi/leeloo-ui/boot')
sys.path.insert(0, '/home/pi/leeloo-ui')

from boot.leeloo_splash import show_splash, clear_screen

# Configuration
WIFI_CONFIG_PATH = '/home/pi/leeloo-ui/wifi_config.json'
CREW_CONFIG_PATH = '/home/pi/leeloo-ui/crew_config.json'
FIRST_RUN_COMPLETE = '/home/pi/leeloo-ui/.first_run_complete'


def is_first_run():
    """Check if this is a first-time boot"""
    return not os.path.exists(FIRST_RUN_COMPLETE)


def mark_first_run_complete():
    """Mark first run as complete"""
    with open(FIRST_RUN_COMPLETE, 'w') as f:
        f.write('1')


def check_wifi_connected():
    """Check if we have a working internet connection"""
    try:
        # Try to ping a reliable host
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def get_wifi_ssid():
    """Get currently connected WiFi SSID"""
    try:
        # Try nmcli first (more reliable on modern systems)
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'active,ssid', 'dev', 'wifi'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.startswith('yes:'):
                    return line.split(':', 1)[1]
        # Fallback to iwgetid
        result = subprocess.run(
            ['iwgetid', '-r'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None


def run_first_run_screen():
    """Show the first-run welcome/setup screen"""
    try:
        from leeloo_first_run import show_first_run
        show_first_run("leeloo")
        return True
    except Exception as e:
        print(f"First run screen error: {e}")
        return False


def start_captive_portal():
    """Start the captive portal AP for WiFi setup"""
    try:
        from captive_portal import CaptivePortal
        portal = CaptivePortal()

        # Start AP mode in background
        print("Starting WiFi AP for setup...")
        portal.start_ap_mode()

        # Start the web server (this blocks)
        print("Starting captive portal web server...")
        portal.run(host='0.0.0.0', port=80)

    except Exception as e:
        print(f"Captive portal error: {e}")
        # Try simpler AP setup
        try:
            import subprocess
            # Create a simple AP using nmcli
            subprocess.run([
                'sudo', 'nmcli', 'device', 'wifi', 'hotspot',
                'ifname', 'wlan0',
                'ssid', 'leeloo',
                'password', 'leeloo123'
            ], timeout=30)
            print("Simple AP started: leeloo / leeloo123")
        except Exception as e2:
            print(f"Simple AP also failed: {e2}")


def run_wifi_setup():
    """Run the WiFi setup flow"""
    show_splash("Starting WiFi setup...", 30)
    time.sleep(1)

    # Import and run gadget_setup
    try:
        from gadget_setup import SetupDisplay
        setup = SetupDisplay()
        setup.run_setup_flow()
        return True
    except Exception as e:
        print(f"WiFi setup error: {e}")
        show_splash(f"WiFi error: {str(e)[:30]}", 30)
        time.sleep(3)
        return False


def run_crew_setup():
    """Run the crew setup flow"""
    show_splash("Crew setup...", 60)
    time.sleep(1)

    try:
        # For now, just show the setup screen
        # In full implementation, this would be interactive
        from leeloo_setup_crew import CrewSetupScreen
        setup = CrewSetupScreen()

        # Show welcome screen
        img = setup.draw_welcome_screen()
        setup.write_to_fb(img)

        # Wait for tap input (placeholder - would use actual touch detection)
        time.sleep(5)

        # For now, skip crew setup
        return True

    except Exception as e:
        print(f"Crew setup error: {e}")
        show_splash(f"Setup error: {str(e)[:30]}", 60)
        time.sleep(3)
        return True  # Continue anyway


def run_main_ui():
    """Start the main LEELOO UI"""
    show_splash("Loading UI...", 90)
    time.sleep(0.5)

    try:
        # Import and run the main display
        from gadget_main import main as gadget_main
        gadget_main()
    except ImportError:
        # Fallback: just render static display
        print("gadget_main not available, running static display")
        run_static_display()
    except Exception as e:
        print(f"Main UI error: {e}")
        show_splash(f"UI error: {str(e)[:30]}", 90)
        time.sleep(5)


def run_static_display():
    """Run a static display as fallback"""
    from gadget_display import LeelooDisplay
    from datetime import datetime
    import numpy as np

    display = LeelooDisplay(preview_mode=False)

    # Basic data
    weather_data = {'temp_f': 72, 'uv_raw': 5, 'rain_24h_inches': 0}
    now = datetime.now()
    time_data = {
        'time_str': now.strftime('%-I:%M %p'),
        'date_str': now.strftime('%b %-d'),
        'seconds': now.second
    }
    contacts = ['Amy', 'Ben']
    album_data = {
        'artist': 'Cinnamon Chasers',
        'track': 'Doorways',
        'bpm': 120,
        'listeners': '262K',
        'pushed_by': 'Amy'
    }

    # Check for album art
    album_art_path = '/home/pi/leeloo-ui/Retro-Music-Panel/client/public/doorways-album.jpg'
    if not os.path.exists(album_art_path):
        album_art_path = None

    # Render
    img = display.render(weather_data, time_data, contacts, album_data, album_art_path=album_art_path)

    # Write to framebuffer
    def rgb_to_rgb565(img):
        arr = np.array(img)
        r = (arr[:, :, 0] >> 3).astype(np.uint16)
        g = (arr[:, :, 1] >> 2).astype(np.uint16)
        b = (arr[:, :, 2] >> 3).astype(np.uint16)
        return (r << 11) | (g << 5) | b

    rgb565 = rgb_to_rgb565(img)
    with open('/dev/fb1', 'wb') as fb:
        fb.write(rgb565.tobytes())

    print("Static display rendered")

    # Keep running (update time every minute)
    while True:
        time.sleep(60)
        now = datetime.now()
        time_data['time_str'] = now.strftime('%-I:%M %p')
        time_data['date_str'] = now.strftime('%b %-d')
        time_data['seconds'] = now.second

        img = display.render(weather_data, time_data, contacts, album_data, album_art_path=album_art_path)
        rgb565 = rgb_to_rgb565(img)
        with open('/dev/fb1', 'wb') as fb:
            fb.write(rgb565.tobytes())


def main():
    """Main boot sequence"""
    print("=" * 50)
    print("LEELOO Boot Sequence Starting")
    print("=" * 50)

    # Step 1: Show initial splash
    show_splash("Initializing...", 10)
    time.sleep(0.5)

    # Step 2: Check WiFi and first run status
    wifi_connected = check_wifi_connected()
    first_run = is_first_run()

    print(f"First run: {first_run}, WiFi connected: {wifi_connected}")

    # Only start captive portal if this is first run AND no WiFi
    if first_run and not wifi_connected:
        print("First run with no WiFi - starting captive portal")
        show_splash("Starting setup...", 20)
        time.sleep(0.5)

        # Show first-run welcome screen with WiFi instructions
        run_first_run_screen()

        # Start captive portal AP in a separate thread
        import threading
        portal_thread = threading.Thread(target=start_captive_portal, daemon=True)
        portal_thread.start()
        print("Captive portal started in background")

        # Wait for WiFi connection
        print("Waiting for WiFi setup via captive portal...")

        # Check every 5 seconds for WiFi connection (with timeout)
        MAX_WIFI_RETRIES = 120  # 10 minutes max wait
        wifi_retry_count = 0
        while wifi_retry_count < MAX_WIFI_RETRIES:
            wifi_connected = check_wifi_connected()
            wifi_ssid = get_wifi_ssid()
            if wifi_connected and wifi_ssid:
                print(f"WiFi connected: {wifi_ssid}")
                mark_first_run_complete()
                break
            wifi_retry_count += 1
            if wifi_retry_count % 12 == 0:  # Every minute
                print(f"Still waiting for WiFi... ({wifi_retry_count * 5}s)")
            time.sleep(5)
        else:
            print("WiFi connection timeout - continuing anyway")
            # Still mark first run complete so we don't loop forever
            mark_first_run_complete()

    elif first_run and wifi_connected:
        # First run but WiFi already works - just mark complete and continue
        print("First run but WiFi already connected - skipping setup")
        mark_first_run_complete()

    # Step 3: Check WiFi (for subsequent boots)
    show_splash("Checking WiFi...", 30)

    wifi_connected = check_wifi_connected()
    wifi_ssid = get_wifi_ssid()

    if wifi_connected and wifi_ssid:
        print(f"WiFi connected: {wifi_ssid}")
        show_splash(f"Connected to {wifi_ssid}", 50)
        time.sleep(1)
    else:
        print("WiFi not connected, showing setup screen...")
        run_first_run_screen()
        # Wait for connection with timeout
        MAX_WIFI_RETRIES = 60  # 5 minutes for reconnect
        wifi_retry_count = 0
        while wifi_retry_count < MAX_WIFI_RETRIES:
            if check_wifi_connected():
                break
            wifi_retry_count += 1
            time.sleep(5)
        else:
            print("WiFi reconnect timeout - continuing to UI anyway")

    # Step 4: Check crew config (optional)
    show_splash("Checking crew...", 60)
    time.sleep(0.5)

    if os.path.exists(CREW_CONFIG_PATH):
        print("Crew already configured")
        show_splash("Crew ready!", 80)
        time.sleep(0.5)
    else:
        print("No crew configured (this is optional)")
        show_splash("No crew (setup later)", 80)
        time.sleep(1)

    # Step 5: Start main UI
    show_splash("Starting LEELOO...", 95)
    time.sleep(0.5)

    print("Launching main UI...")
    run_main_ui()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nBoot interrupted")
        clear_screen()
    except Exception as e:
        print(f"Boot error: {e}")
        show_splash(f"Error: {str(e)[:40]}", 0)
        time.sleep(10)
