#!/usr/bin/env python3
"""
Demo: Weather Frame - Using EXACT same approach as working reaction GIF demo

This uses the pixel-by-pixel RGB565 conversion and identical write method
that works in demo_message_expand.py
"""

import sys
import time
import os
sys.path.insert(0, '/home/pi')

from gadget_display import LeelooDisplay, COLORS
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


def hide_cursor():
    try:
        os.system('echo -e "\\033[?25l" > /dev/tty1 2>/dev/null')
    except:
        pass


def frame_to_rgb565(frame):
    """
    Convert PIL frame to RGB565 bytes - EXACT copy from working demo
    Uses pixel-by-pixel Python loop (slow but works)
    """
    img = frame.convert('RGB')
    pixels = img.load()
    width, height = img.size

    data = bytearray(width * height * 2)
    idx = 0
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            data[idx] = rgb565 & 0xFF
            data[idx + 1] = (rgb565 >> 8) & 0xFF
            idx += 2
    return bytes(data)


def write_to_framebuffer(image, fb_path='/dev/fb1'):
    """Write full PIL image to framebuffer"""
    rgb565_data = frame_to_rgb565(image)
    with open(fb_path, 'wb') as f:
        f.write(rgb565_data)


def write_region_to_framebuffer(frame_bytes, x, y, width, height, fb_path='/dev/fb1', screen_width=480):
    """
    Write pre-computed RGB565 bytes to a region of framebuffer
    EXACT copy from working demo
    """
    with open(fb_path, 'r+b') as fb:
        for row in range(height):
            offset = ((y + row) * screen_width + x) * 2
            fb.seek(offset)
            row_start = row * width * 2
            row_end = row_start + width * 2
            fb.write(frame_bytes[row_start:row_end])


def get_box_right(display, album_art_path):
    display.image = Image.new('RGB', (display.width, display.height), color=COLORS['bg'])
    display.draw = ImageDraw.Draw(display.image)
    album_x = display.draw_album_art(album_art_path=album_art_path)
    info_panel_right = album_x - 5
    box_right = info_panel_right - 5
    return box_right


def show_standard_ui(display, album_art_path):
    weather_data = {'temp_f': 72, 'uv_raw': 5, 'rain_24h_inches': 0}
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


def show_expanded_weather(display, album_art_path, box_right):
    """
    Draw expanded weather frame with content - SAME approach as reaction GIF
    Draw everything once, write full screen once.
    """
    # Create full screen image
    display.image = Image.new('RGB', (display.width, display.height), color=COLORS['bg'])
    display.draw = ImageDraw.Draw(display.image)

    # Draw album art on right side (this stays constant)
    display.draw_album_art(album_art_path=album_art_path)

    # Draw expanded frame border
    frame_x = 5
    frame_y = 16
    frame_width = box_right - 5
    frame_height = 290

    display.draw.rectangle(
        [frame_x, frame_y, frame_x + frame_width, frame_y + frame_height],
        outline=COLORS['tan'],
        width=2
    )

    # Draw label
    try:
        label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
    except:
        label_font = ImageFont.load_default()

    label_x = frame_x + 5
    display.draw.rectangle([label_x - 2, frame_y - 6, label_x + 60, frame_y + 6], fill=COLORS['bg'])
    display.draw.text((label_x, frame_y - 5), "weather", font=label_font, fill=COLORS['tan'])

    # Draw weather content
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
        font_large = font

    content_x = frame_x + 10
    content_y = frame_y + 25
    line_height = 24

    y = content_y
    display.draw.text((content_x, y), "72F", font=font_large, fill=COLORS['tan'])
    y += 28
    display.draw.text((content_x, y), "Partly cloudy", font=font, fill=COLORS['white'])
    y += line_height
    display.draw.text((content_x, y), "Humidity: 45%", font=font, fill=COLORS['white'])
    y += line_height
    display.draw.text((content_x, y), "Wind: 8 mph SW", font=font, fill=COLORS['white'])
    y += line_height + 12
    display.draw.text((content_x, y), "High: 78F", font=font, fill=COLORS['tan'])
    y += line_height
    display.draw.text((content_x, y), "Low: 62F", font=font, fill=COLORS['tan'])

    # Write full screen at once
    write_to_framebuffer(display.image)


def demo():
    print("Weather Frame Demo (Using Reaction GIF Method)")
    print("=" * 50)

    hide_cursor()

    display = LeelooDisplay(preview_mode=False)

    album_art_path = '/home/pi/doorways-album.jpg'
    if not os.path.exists(album_art_path):
        album_art_path = None
        print("Warning: Album art not found")

    box_right = get_box_right(display, album_art_path)
    print(f"Using box_right = {box_right}")

    # Show standard UI
    print("\n[1] Showing standard UI...")
    show_standard_ui(display, album_art_path)
    time.sleep(2)

    # Show expanded weather (no animation, just swap)
    print("\n[2] Showing expanded weather frame...")
    show_expanded_weather(display, album_art_path, box_right)

    # Wait 5 seconds
    print("    Waiting 5 seconds...")
    time.sleep(5)

    # Return to standard UI
    print("\n[3] Returning to standard UI...")
    show_standard_ui(display, album_art_path)

    print("\nDemo complete!")


if __name__ == "__main__":
    demo()
