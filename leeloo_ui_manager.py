#!/usr/bin/env python3
"""
LEELOO UI Manager - Event-driven state machine for display management

This is the PRO solution: A single UI manager that owns the display and
handles all state transitions cleanly. No race conditions, no fighting
for the framebuffer.

Architecture:
- Single owner of the framebuffer
- State machine controls what's displayed
- Events trigger state transitions
- Animations block the main loop (they ARE the main loop during animation)

States:
- NORMAL: Standard UI with weather, time, messages, album
- EXPANDING: Frame is animating open
- EXPANDED: Frame is open, showing content
- COLLAPSING: Frame is animating closed

Events:
- tap_weather, tap_time, tap_messages, tap_album: User tapped a frame
- animation_complete: Expand/collapse animation finished
- timeout: Content display time expired
- tap_close: User tapped to close expanded view
"""

import os
import time
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from gadget_display import LeelooDisplay, COLORS
from display.frame_animator import (
    FrameAnimator, FrameType,
    rgb_to_rgb565_fast, write_region_to_framebuffer_rowbyrow
)
from PIL import Image, ImageDraw, ImageFont


# Screen constants
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320


class UIState(Enum):
    """UI states"""
    NORMAL = auto()
    EXPANDING = auto()
    EXPANDED = auto()
    COLLAPSING = auto()


@dataclass
class ExpandedContent:
    """Content to show in expanded frame"""
    frame_type: FrameType
    title: str
    lines: list  # List of (text, font_size, color) tuples
    duration: float = 10.0  # How long to show content


class LeelooUIManager:
    """
    Single point of control for the LEELOO display.

    This class owns the framebuffer and manages all display state.
    No other code should write to the framebuffer directly.
    """

    def __init__(self, fb_path: str = '/dev/fb1', album_art_path: str = None):
        self.fb_path = fb_path
        self.album_art_path = album_art_path

        # Display and animator
        self.display = LeelooDisplay(preview_mode=False)
        self.box_right = self._calculate_box_right()
        self.animator = FrameAnimator(self.display, box_right=self.box_right, fb_path=fb_path)

        # State
        self.state = UIState.NORMAL
        self.expanded_frame: Optional[FrameType] = None
        self.expanded_content: Optional[ExpandedContent] = None
        self.expand_start_time: float = 0

        # Data (updated externally)
        self.weather_data: Dict[str, Any] = {'temp_f': 72, 'uv_raw': 5, 'rain_24h_inches': 0}
        self.time_data: Dict[str, Any] = {}
        self.contacts: list = ['Amy', 'Ben']
        self.album_data: Dict[str, Any] = {
            'artist': 'Cinnamon Chasers',
            'track': 'Doorways',
            'bpm': 120,
            'listeners': '262K',
            'pushed_by': 'Amy',
        }

        # Load fonts
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 20)
            self.font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
        except:
            self.font = ImageFont.load_default()
            self.font_large = self.font
            self.font_label = self.font

    def _calculate_box_right(self) -> int:
        """Calculate box_right based on album art position"""
        self.display.image = Image.new('RGB', (self.display.width, self.display.height), color=COLORS['bg'])
        self.display.draw = ImageDraw.Draw(self.display.image)
        album_x = self.display.draw_album_art(album_art_path=self.album_art_path)
        info_panel_right = album_x - 5
        return info_panel_right - 5

    def _write_full_screen(self, image: Image.Image):
        """Write full screen using row-by-row I/O"""
        rgb565 = rgb_to_rgb565_fast(image)
        write_region_to_framebuffer_rowbyrow(rgb565, 0, 0, self.fb_path, SCREEN_WIDTH)

    def _update_time_data(self):
        """Update time data"""
        now = datetime.now()
        self.time_data = {
            'time_str': now.strftime('%-I:%M %p'),
            'date_str': now.strftime('%b %-d'),
            'seconds': now.second,
        }

    def render_normal_ui(self):
        """Render and display the normal UI"""
        self._update_time_data()
        self.display.render(
            self.weather_data,
            self.time_data,
            self.contacts,
            self.album_data,
            album_art_path=self.album_art_path
        )
        self._write_full_screen(self.display.image)

    def _typewriter_content(self, content: ExpandedContent):
        """Typewriter effect for expanded content"""
        content_x = 5 + 10
        content_y = 16 + 25
        line_height = 24
        text_region_width = self.box_right - 5 - 20

        char_delay = 0.03
        line_delay = 0.1

        y_pos = content_y

        with open(self.fb_path, 'r+b') as fb:
            for line_text, font_size, line_color in content.lines:
                if line_text == "":
                    y_pos += line_height // 2
                    continue

                # Select font based on size
                line_font = self.font_large if font_size == "large" else self.font

                current_text = ""
                for char in line_text:
                    current_text += char

                    # Create line image
                    line_img = Image.new('RGB', (text_region_width, line_height), COLORS['bg'])
                    line_draw = ImageDraw.Draw(line_img)
                    line_draw.text((0, 2), current_text, font=line_font, fill=line_color)

                    # Convert and write
                    rgb565 = rgb_to_rgb565_fast(line_img)
                    height, width = rgb565.shape
                    for row in range(height):
                        offset = ((y_pos + row) * SCREEN_WIDTH + content_x) * 2
                        fb.seek(offset)
                        fb.write(rgb565[row, :].tobytes())

                    time.sleep(char_delay)

                y_pos += line_height
                time.sleep(line_delay)

    # =========================================================================
    # PUBLIC API - Event handlers
    # =========================================================================

    def expand_frame(self, frame_type: FrameType, content: ExpandedContent):
        """
        Expand a frame with content.

        This is a BLOCKING call - it runs the full expand animation,
        shows content with typewriter effect, waits, then collapses.

        The main loop is paused during this entire sequence.
        """
        if self.state != UIState.NORMAL:
            return  # Already in an animation

        print(f"[UIManager] Expanding {frame_type.value} frame...")

        # Expand animation
        self.state = UIState.EXPANDING
        self.expanded_frame = frame_type
        self.animator.expand(frame_type, content_drawer=None)

        # Show content with typewriter
        self.state = UIState.EXPANDED
        self._typewriter_content(content)

        # Hold for duration
        print(f"[UIManager] Holding for {content.duration}s...")
        time.sleep(content.duration)

        # Collapse animation
        self.state = UIState.COLLAPSING
        self.animator.collapse(frame_type, content_drawer=None)

        # Back to normal
        self.state = UIState.NORMAL
        self.expanded_frame = None
        self.render_normal_ui()

        print(f"[UIManager] Frame collapsed, back to normal")

    def expand_weather(self):
        """Expand weather frame with current weather data"""
        temp = self.weather_data.get('temp_f', 72)
        content = ExpandedContent(
            frame_type=FrameType.WEATHER,
            title="weather",
            lines=[
                (f"{temp}F", "large", COLORS['tan']),
                ("", None, None),
                ("Partly cloudy", "normal", COLORS['white']),
                ("Humidity: 45%", "normal", COLORS['white']),
                ("Wind: 8 mph SW", "normal", COLORS['white']),
                ("", None, None),
                ("High: 78F", "normal", COLORS['tan']),
                ("Low: 62F", "normal", COLORS['tan']),
            ],
            duration=10.0
        )
        self.expand_frame(FrameType.WEATHER, content)

    def expand_time(self):
        """Expand time frame with calendar/schedule"""
        content = ExpandedContent(
            frame_type=FrameType.TIME,
            title="time",
            lines=[
                ("Today", "large", COLORS['purple']),
                ("", None, None),
                ("9:00 AM  Team standup", "normal", COLORS['white']),
                ("11:30 AM  Design review", "normal", COLORS['white']),
                ("2:00 PM  Client call", "normal", COLORS['white']),
                ("", None, None),
                ("Tomorrow", "large", COLORS['purple']),
                ("10:00 AM  Dentist", "normal", COLORS['white']),
            ],
            duration=10.0
        )
        self.expand_frame(FrameType.TIME, content)

    def expand_messages(self):
        """Expand messages frame"""
        content = ExpandedContent(
            frame_type=FrameType.MESSAGES,
            title="messages",
            lines=[
                ("Amy", "large", COLORS['lavender']),
                ("", None, None),
                ("Hey! Are you free", "normal", COLORS['white']),
                ("for lunch today?", "normal", COLORS['white']),
                ("", None, None),
                ("Ben", "large", COLORS['lavender']),
                ("", None, None),
                ("Check out this song", "normal", COLORS['white']),
            ],
            duration=10.0
        )
        self.expand_frame(FrameType.MESSAGES, content)

    def expand_album(self):
        """Expand album frame with track details"""
        content = ExpandedContent(
            frame_type=FrameType.ALBUM,
            title="album",
            lines=[
                ("Doorways", "large", COLORS['green']),
                ("Cinnamon Chasers", "normal", COLORS['white']),
                ("", None, None),
                ("120 BPM", "normal", COLORS['tan']),
                ("262K listeners", "normal", COLORS['white']),
                ("", None, None),
                ("Pushed by Amy", "normal", COLORS['lavender']),
                ("2 hours ago", "normal", COLORS['white']),
            ],
            duration=10.0
        )
        self.expand_frame(FrameType.ALBUM, content)

    def update(self):
        """
        Called every iteration of the main loop.
        Only updates display if in NORMAL state.
        """
        if self.state == UIState.NORMAL:
            self.render_normal_ui()


# =============================================================================
# Demo / Test
# =============================================================================

def demo():
    """Demo the UI manager"""
    print("LEELOO UI Manager Demo")
    print("=" * 50)

    # Hide cursor
    os.system('echo -e "\\033[?25l" > /dev/tty1 2>/dev/null')

    album_art_path = '/home/pi/doorways-album.jpg'
    if not os.path.exists(album_art_path):
        album_art_path = None

    ui = LeelooUIManager(album_art_path=album_art_path)

    # Show normal UI
    print("\n[Demo] Showing normal UI for 3 seconds...")
    ui.render_normal_ui()
    time.sleep(3)

    # Expand weather
    print("\n[Demo] Expanding weather frame...")
    ui.expand_weather()

    # Back to normal for a bit
    print("\n[Demo] Normal UI for 2 seconds...")
    time.sleep(2)

    print("\n[Demo] Complete!")


if __name__ == "__main__":
    demo()
