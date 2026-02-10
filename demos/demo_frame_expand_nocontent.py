#!/usr/bin/env python3
"""
Demo: Frame Expansion Animation (No Content)

Shows pure expand/collapse animations without content rendering overhead.
Tests raw animation performance.
"""

import sys
import time
import os
sys.path.insert(0, '/home/pi')

from gadget_display import LeelooDisplay, COLORS
from display.frame_animator import FrameAnimator, FrameType
from PIL import Image, ImageDraw


def hide_cursor():
    """Hide terminal cursor on tty1"""
    try:
        os.system('echo -e "\\033[?25l" > /dev/tty1 2>/dev/null')
    except:
        pass


def write_to_framebuffer(image, fb_path='/dev/fb1'):
    """Write PIL image to framebuffer"""
    from display.fast_fb import FastFramebuffer
    fb = FastFramebuffer(fb_path)
    fb.write_image(image)
    fb.close()


def get_box_right(display, album_art_path):
    """Get the actual box_right value based on album art"""
    display.image = Image.new('RGB', (display.width, display.height), color=COLORS['bg'])
    display.draw = ImageDraw.Draw(display.image)
    album_x = display.draw_album_art(album_art_path=album_art_path)
    info_panel_right = album_x - 5
    box_right = info_panel_right - 5
    return box_right


def show_standard_ui(display, album_art_path):
    """Show the standard LEELOO UI"""
    from datetime import datetime

    weather_data = {
        'temp_f': 72,
        'uv_raw': 5,
        'rain_24h_inches': 0,
    }

    now = datetime.now()
    time_data = {
        'time_str': now.strftime('%-I:%M %p'),
        'date_str': now.strftime('%b %-d'),
        'seconds': now.second,
    }

    contacts = ['Amy', 'Ben']

    album_data = {
        'artist': 'Cinnamon Chasers',
        'track': 'Doorways',
        'bpm': 120,
        'listeners': '262K',
        'pushed_by': 'Amy',
    }

    display.render(weather_data, time_data, contacts, album_data, album_art_path=album_art_path)
    write_to_framebuffer(display.image)


def demo_no_content():
    """Demo frame expansion animations without content (pure animation test)"""
    print("Frame Expansion Animation - NO CONTENT")
    print("=" * 40)

    hide_cursor()

    display = LeelooDisplay(preview_mode=False)

    # Find album art
    album_art_path = '/home/pi/doorways-album.jpg'
    if not os.path.exists(album_art_path):
        album_art_path = None
        print("Warning: Album art not found, using placeholder")

    # Get actual box_right value
    box_right = get_box_right(display, album_art_path)
    print(f"Using box_right = {box_right}")

    # Show standard UI first
    print("\n[1] Showing standard UI...")
    show_standard_ui(display, album_art_path)
    time.sleep(1)

    # Create animator
    animator = FrameAnimator(display, box_right=box_right, fb_path='/dev/fb1')

    # Test all frames with NO content drawer
    frames_to_test = [
        (FrameType.WEATHER, "WEATHER"),
        (FrameType.TIME, "TIME"),
        (FrameType.MESSAGES, "MESSAGES"),
        (FrameType.ALBUM, "ALBUM"),
    ]

    for frame_type, name in frames_to_test:
        print(f"\n[{name}] Expanding...")
        animator.expand(frame_type, content_drawer=None)  # NO CONTENT
        time.sleep(1)

        print(f"[{name}] Collapsing...")
        animator.collapse(frame_type, content_drawer=None)  # NO CONTENT
        time.sleep(0.3)

        # Restore UI between tests
        show_standard_ui(display, album_art_path)
        time.sleep(0.5)

    # Cleanup
    animator.close()
    print("\nDemo complete!")


if __name__ == "__main__":
    demo_no_content()
