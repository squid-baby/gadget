#!/usr/bin/env python3
"""
Demo: Weather Frame Expand with Typewriter Effect - FIXED VERSION

Key fixes:
1. Don't overwrite the full screen after expand animation
2. Use row-by-row writes for typewriter (no tearing)
3. Preserve album art on the right side

Flow:
1. Show standard UI
2. Expand weather frame (animation preserves album art)
3. Typewriter weather report INSIDE the already-expanded frame
4. Wait 2 seconds
5. Collapse back to original
"""

import sys
import time
import os
sys.path.insert(0, '/home/pi')

from gadget_display import LeelooDisplay, COLORS
from display.frame_animator import FrameAnimator, FrameType, rgb_to_rgb565_fast, write_region_to_framebuffer_rowbyrow
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


# Screen constants
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320


def hide_cursor():
    """Hide terminal cursor on tty1"""
    try:
        os.system('echo -e "\\033[?25l" > /dev/tty1 2>/dev/null')
    except:
        pass


def write_full_screen_rowbyrow(image, fb_path='/dev/fb1'):
    """
    Write full screen image using row-by-row I/O (no tearing).
    Use this instead of fb.write_image() which uses memmap.
    """
    rgb565 = rgb_to_rgb565_fast(image)
    write_region_to_framebuffer_rowbyrow(rgb565, 0, 0, fb_path, SCREEN_WIDTH)


def get_box_right(display, album_art_path):
    """Get the actual box_right value based on album art"""
    display.image = Image.new('RGB', (display.width, display.height), color=COLORS['bg'])
    display.draw = ImageDraw.Draw(display.image)
    album_x = display.draw_album_art(album_art_path=album_art_path)
    info_panel_right = album_x - 5
    box_right = info_panel_right - 5
    return box_right


def show_standard_ui(display, album_art_path):
    """Show the standard LEELOO UI using row-by-row writes"""
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

    # Use row-by-row write instead of FastFramebuffer.write_image()
    write_full_screen_rowbyrow(display.image)


def show_weather_content(box_right, fb_path='/dev/fb1'):
    """
    Show weather content instantly (no typewriter effect).
    """

    # Load fonts
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
        font_large = font

    # Content area coordinates (INSIDE the expanded frame border)
    content_x = 7 + 10  # 7 = frame left edge (2px padding from outer frame)
    content_y = 16 + 25
    line_height = 24
    text_region_width = box_right - 7 - 20
    text_region_height = 290 - 30  # Height of content area

    # Create content image
    content_img = Image.new('RGB', (text_region_width, text_region_height), COLORS['bg'])
    draw = ImageDraw.Draw(content_img)

    # Draw all text at once
    y = 0
    draw.text((0, y), "72F", font=font_large, fill=COLORS['tan'])
    y += 28
    draw.text((0, y), "Partly cloudy", font=font, fill=COLORS['white'])
    y += line_height
    draw.text((0, y), "Humidity: 45%", font=font, fill=COLORS['white'])
    y += line_height
    draw.text((0, y), "Wind: 8 mph SW", font=font, fill=COLORS['white'])
    y += line_height + 12
    draw.text((0, y), "High: 78F", font=font, fill=COLORS['tan'])
    y += line_height
    draw.text((0, y), "Low: 62F", font=font, fill=COLORS['tan'])

    # Write content region using row-by-row I/O
    rgb565 = rgb_to_rgb565_fast(content_img)
    write_region_to_framebuffer_rowbyrow(rgb565, content_x, content_y, fb_path)


def clear_weather_content(box_right, fb_path='/dev/fb1'):
    """
    Clear weather content (fill with background color).
    """
    content_x = 7 + 10  # 7 = frame left edge (2px padding from outer frame)
    content_y = 16 + 25
    text_region_width = box_right - 7 - 20
    text_region_height = 290 - 30

    # Create blank content image
    blank_img = Image.new('RGB', (text_region_width, text_region_height), COLORS['bg'])

    # Write blank region
    rgb565 = rgb_to_rgb565_fast(blank_img)
    write_region_to_framebuffer_rowbyrow(rgb565, content_x, content_y, fb_path)


def typewriter_weather_content(box_right, fb_path='/dev/fb1'):
    """
    Typewriter effect for weather content.
    Types out each line character by character.
    """
    # Load fonts
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
        font_large = font

    # Weather lines: (text, font, color)
    lines = [
        ("72F", font_large, COLORS['tan']),
        ("", None, None),  # blank
        ("Partly cloudy", font, COLORS['white']),
        ("Humidity: 45%", font, COLORS['white']),
        ("Wind: 8 mph SW", font, COLORS['white']),
        ("", None, None),  # blank
        ("High: 78F", font, COLORS['tan']),
        ("Low: 62F", font, COLORS['tan']),
    ]

    # Content area coordinates
    content_x = 7 + 10  # 7 = frame left edge (2px padding from outer frame)
    content_y = 16 + 25
    line_height = 24
    text_region_width = box_right - 7 - 20

    # Timing
    char_delay = 0.03  # 30ms per character
    line_delay = 0.1   # 100ms between lines

    y_pos = content_y

    # Keep file handle open for all writes
    with open(fb_path, 'r+b') as fb:
        for line_text, line_font, line_color in lines:
            if line_text == "":
                y_pos += line_height // 2
                continue

            current_text = ""
            for char in line_text:
                current_text += char

                # Create line image
                line_img = Image.new('RGB', (text_region_width, line_height), COLORS['bg'])
                line_draw = ImageDraw.Draw(line_img)
                line_draw.text((0, 2), current_text, font=line_font, fill=line_color)

                # Convert to RGB565
                rgb565 = rgb_to_rgb565_fast(line_img)

                # Write row-by-row
                height, width = rgb565.shape
                for row in range(height):
                    offset = ((y_pos + row) * SCREEN_WIDTH + content_x) * 2
                    fb.seek(offset)
                    fb.write(rgb565[row, :].tobytes())

                time.sleep(char_delay)

            y_pos += line_height
            time.sleep(line_delay)


def demo_weather_typewriter():
    """Demo weather expand with typewriter - FIXED VERSION"""
    print("Weather Frame Typewriter Demo (FIXED)")
    print("=" * 40)

    hide_cursor()

    display = LeelooDisplay(preview_mode=False)

    # Find album art
    album_art_path = '/home/pi/doorways-album.jpg'
    if not os.path.exists(album_art_path):
        album_art_path = None
        print("Warning: Album art not found")

    # Get actual box_right value
    box_right = get_box_right(display, album_art_path)
    print(f"Using box_right = {box_right}")

    # Show standard UI first
    print("\n[1] Showing standard UI...")
    show_standard_ui(display, album_art_path)
    time.sleep(2)

    # Create animator (uses fixed row-by-row method)
    animator = FrameAnimator(display, box_right=box_right, fb_path='/dev/fb1')

    # Expand weather frame
    print("\n[2] Expanding WEATHER frame...")
    animator.expand(FrameType.WEATHER, content_drawer=None)

    # Typewriter the weather content
    print("\n[3] Typewriter weather content...")
    typewriter_weather_content(box_right)

    # Hold for remaining time (10 seconds total, minus typewriter time)
    print("    Holding for 10 seconds...")
    time.sleep(10)

    # Collapse back
    print("\n[4] Collapsing WEATHER frame...")
    animator.collapse(FrameType.WEATHER, content_drawer=None)

    # Restore standard UI
    print("\n[5] Restoring standard UI...")
    show_standard_ui(display, album_art_path)

    print("\nDemo complete!")


if __name__ == "__main__":
    demo_weather_typewriter()
