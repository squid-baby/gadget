#!/usr/bin/env python3
"""
LEELOO Crew Setup Screen
Shows QR code and handles crew pairing.
"""

import time
import asyncio
from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    import qrcode
except ImportError:
    print("Installing qrcode...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'qrcode[pil]'])
    import qrcode

from leeloo_client import LeelooClient

# Screen dimensions
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320

# Colors
COLORS = {
    'bg': '#1A1D2E',
    'lavender': '#A7AFD4',
    'purple': '#9C93DD',
    'white': '#FFFFFF',
    'green': '#719253',
    'tan': '#C2995E',
}


class CrewSetupScreen:
    """Crew setup/pairing screen"""

    def __init__(self, fb_path='/dev/fb1', relay_url='ws://localhost:8765'):
        self.fb_path = fb_path
        self.relay_url = relay_url
        self.client = LeelooClient(relay_url=relay_url)

        # Fonts
        try:
            self.font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 9)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
            self.font_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            self.font_code = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 28)
        except:
            self.font_header = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_med = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_code = ImageFont.load_default()

    def rgb_to_rgb565(self, img: Image.Image) -> np.ndarray:
        """Convert PIL image to RGB565 numpy array"""
        arr = np.array(img)
        r = (arr[:, :, 0] >> 3).astype(np.uint16)
        g = (arr[:, :, 1] >> 2).astype(np.uint16)
        b = (arr[:, :, 2] >> 3).astype(np.uint16)
        return (r << 11) | (g << 5) | b

    def write_to_fb(self, img: Image.Image):
        """Write image to framebuffer"""
        rgb565 = self.rgb_to_rgb565(img)
        with open(self.fb_path, 'wb') as fb:
            fb.write(rgb565.tobytes())

    def generate_qr(self, data: str, size: int = 120) -> Image.Image:
        """Generate QR code image"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="white", back_color=COLORS['bg'])
        qr_img = qr_img.resize((size, size), Image.Resampling.NEAREST)
        return qr_img.convert('RGB')

    def draw_welcome_screen(self) -> Image.Image:
        """Draw initial welcome/choice screen"""
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([2, 4, SCREEN_WIDTH - 3, SCREEN_HEIGHT - 4],
                       outline=COLORS['lavender'], width=1)
        draw.rectangle([6, -1, 180, 12], fill=COLORS['bg'])
        draw.text((8, 0), "LEELOO v1.0", font=self.font_header, fill=COLORS['lavender'])
        draw.text((100, 0), "crew setup", font=self.font_header, fill=COLORS['lavender'])

        # Main content
        y = 50
        draw.text((20, y), "Welcome to LEELOO!", font=self.font_large, fill=COLORS['white'])

        y += 50
        draw.text((20, y), "Choose an option:", font=self.font_med, fill=COLORS['lavender'])

        # Option 1: Create crew
        y += 40
        draw.rectangle([20, y, SCREEN_WIDTH - 20, y + 50],
                       outline=COLORS['green'], width=2)
        draw.text((30, y + 8), "TAP LEFT", font=self.font_small, fill=COLORS['green'])
        draw.text((30, y + 28), "Create New Crew", font=self.font_med, fill=COLORS['white'])

        # Option 2: Join crew
        y += 70
        draw.rectangle([20, y, SCREEN_WIDTH - 20, y + 50],
                       outline=COLORS['purple'], width=2)
        draw.text((30, y + 8), "TAP RIGHT", font=self.font_small, fill=COLORS['purple'])
        draw.text((30, y + 28), "Join Existing Crew", font=self.font_med, fill=COLORS['white'])

        # Skip option
        y += 70
        draw.text((20, y), "HOLD to skip (no messaging)", font=self.font_small,
                  fill=self._dim_color(COLORS['lavender']))

        return img

    def draw_creating_crew_screen(self) -> Image.Image:
        """Draw 'creating crew' loading screen"""
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([2, 4, SCREEN_WIDTH - 3, SCREEN_HEIGHT - 4],
                       outline=COLORS['lavender'], width=1)
        draw.rectangle([6, -1, 180, 12], fill=COLORS['bg'])
        draw.text((8, 0), "LEELOO v1.0", font=self.font_header, fill=COLORS['lavender'])
        draw.text((100, 0), "crew setup", font=self.font_header, fill=COLORS['lavender'])

        # Content
        y = 120
        text = "Creating your crew..."
        try:
            text_width = self.font_large.getlength(text)
        except:
            text_width = len(text) * 14
        x = (SCREEN_WIDTH - text_width) // 2
        draw.text((x, y), text, font=self.font_large, fill=COLORS['white'])

        # Loading dots
        y += 50
        dots = "..."
        try:
            dots_width = self.font_large.getlength(dots)
        except:
            dots_width = 30
        x = (SCREEN_WIDTH - dots_width) // 2
        draw.text((x, y), dots, font=self.font_large, fill=COLORS['lavender'])

        return img

    def draw_crew_created_screen(self, crew_code: str) -> Image.Image:
        """Draw screen showing crew code"""
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([2, 4, SCREEN_WIDTH - 3, SCREEN_HEIGHT - 4],
                       outline=COLORS['lavender'], width=1)
        draw.rectangle([6, -1, 180, 12], fill=COLORS['bg'])
        draw.text((8, 0), "LEELOO v1.0", font=self.font_header, fill=COLORS['lavender'])
        draw.text((100, 0), "crew created!", font=self.font_header, fill=COLORS['green'])

        # QR code for Telegram bot
        qr_url = f"https://t.me/LeelooBot?start={crew_code.replace('-', '')}"
        qr_img = self.generate_qr(qr_url, size=140)
        img.paste(qr_img, (30, 40))

        # Crew code display
        x = 190
        y = 40
        draw.text((x, y), "Your Crew Code:", font=self.font_med, fill=COLORS['lavender'])

        y += 30
        draw.text((x, y), crew_code, font=self.font_code, fill=COLORS['green'])

        y += 50
        draw.text((x, y), "Share this code with", font=self.font_small, fill=COLORS['white'])
        y += 18
        draw.text((x, y), "friends to add them!", font=self.font_small, fill=COLORS['white'])

        y += 35
        draw.text((x, y), "Scan QR to connect", font=self.font_small, fill=COLORS['lavender'])
        y += 18
        draw.text((x, y), "Telegram (optional)", font=self.font_small, fill=COLORS['lavender'])

        # Continue button
        y = 260
        draw.rectangle([20, y, SCREEN_WIDTH - 20, y + 40],
                       outline=COLORS['green'], width=2)
        text = "TAP to continue"
        try:
            text_width = self.font_med.getlength(text)
        except:
            text_width = len(text) * 10
        draw.text(((SCREEN_WIDTH - text_width) // 2, y + 10), text,
                  font=self.font_med, fill=COLORS['green'])

        return img

    def draw_join_crew_screen(self, entered_code: str = "", error: str = "") -> Image.Image:
        """Draw screen for entering crew code"""
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([2, 4, SCREEN_WIDTH - 3, SCREEN_HEIGHT - 4],
                       outline=COLORS['lavender'], width=1)
        draw.rectangle([6, -1, 180, 12], fill=COLORS['bg'])
        draw.text((8, 0), "LEELOO v1.0", font=self.font_header, fill=COLORS['lavender'])
        draw.text((100, 0), "join crew", font=self.font_header, fill=COLORS['purple'])

        # Instructions
        y = 40
        draw.text((20, y), "Enter the crew code", font=self.font_med, fill=COLORS['white'])
        y += 25
        draw.text((20, y), "from your friend:", font=self.font_med, fill=COLORS['white'])

        # Code entry field
        y += 50
        code_display = entered_code if entered_code else "LEELOO-____"
        draw.rectangle([20, y, SCREEN_WIDTH - 20, y + 50],
                       outline=COLORS['purple'], width=2, fill=COLORS['bg'])

        try:
            code_width = self.font_code.getlength(code_display)
        except:
            code_width = len(code_display) * 18
        draw.text(((SCREEN_WIDTH - code_width) // 2, y + 8), code_display,
                  font=self.font_code, fill=COLORS['white'])

        # Error message
        if error:
            y += 60
            draw.text((20, y), error, font=self.font_small, fill=COLORS['tan'])

        # Keypad hint
        y = 200
        draw.text((20, y), "Use Telegram to enter code:", font=self.font_small,
                  fill=COLORS['lavender'])
        y += 20
        draw.text((20, y), "t.me/LeelooBot", font=self.font_med, fill=COLORS['purple'])

        # Back button
        y = 270
        draw.text((20, y), "TAP LEFT to go back", font=self.font_small,
                  fill=self._dim_color(COLORS['lavender']))

        return img

    def draw_connecting_screen(self, crew_code: str) -> Image.Image:
        """Draw 'connecting to crew' screen"""
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([2, 4, SCREEN_WIDTH - 3, SCREEN_HEIGHT - 4],
                       outline=COLORS['lavender'], width=1)
        draw.rectangle([6, -1, 180, 12], fill=COLORS['bg'])
        draw.text((8, 0), "LEELOO v1.0", font=self.font_header, fill=COLORS['lavender'])

        # Content
        y = 100
        text = f"Joining {crew_code}..."
        try:
            text_width = self.font_large.getlength(text)
        except:
            text_width = len(text) * 14
        x = (SCREEN_WIDTH - text_width) // 2
        draw.text((x, y), text, font=self.font_large, fill=COLORS['white'])

        # Progress indicator
        y += 60
        draw.text((SCREEN_WIDTH // 2 - 20, y), "...", font=self.font_large, fill=COLORS['purple'])

        return img

    def draw_setup_complete_screen(self, crew_code: str, member_count: int = 1) -> Image.Image:
        """Draw setup complete screen"""
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([2, 4, SCREEN_WIDTH - 3, SCREEN_HEIGHT - 4],
                       outline=COLORS['green'], width=2)
        draw.rectangle([6, -1, 180, 12], fill=COLORS['bg'])
        draw.text((8, 0), "LEELOO v1.0", font=self.font_header, fill=COLORS['green'])
        draw.text((100, 0), "setup complete!", font=self.font_header, fill=COLORS['green'])

        # Checkmark
        y = 60
        check = "OK"
        try:
            check_width = self.font_large.getlength(check)
        except:
            check_width = 50
        draw.text(((SCREEN_WIDTH - check_width) // 2, y), check,
                  font=self.font_large, fill=COLORS['green'])

        # Info
        y = 120
        draw.text((40, y), f"Crew: {crew_code}", font=self.font_med, fill=COLORS['white'])
        y += 30
        draw.text((40, y), f"Members: {member_count}", font=self.font_med, fill=COLORS['lavender'])

        y += 50
        draw.text((40, y), "You're all set!", font=self.font_large, fill=COLORS['white'])
        y += 40
        draw.text((40, y), "Messages from your crew will", font=self.font_small, fill=COLORS['lavender'])
        y += 18
        draw.text((40, y), "appear on your LEELOO.", font=self.font_small, fill=COLORS['lavender'])

        # Continue
        y = 260
        text = "Starting in 3..."
        try:
            text_width = self.font_med.getlength(text)
        except:
            text_width = len(text) * 10
        draw.text(((SCREEN_WIDTH - text_width) // 2, y), text,
                  font=self.font_med, fill=COLORS['green'])

        return img

    def _dim_color(self, hex_color: str) -> str:
        """Return dimmed version of color"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        bg_r, bg_g, bg_b = 0x1A, 0x1D, 0x2E
        dim_r = int(r * 0.4 + bg_r * 0.6)
        dim_g = int(g * 0.4 + bg_g * 0.6)
        dim_b = int(b * 0.4 + bg_b * 0.6)

        return f'#{dim_r:02x}{dim_g:02x}{dim_b:02x}'


# Demo
async def demo():
    """Demo the setup screens"""
    setup = CrewSetupScreen(fb_path='/dev/fb1', relay_url='ws://localhost:8765')

    # Show welcome screen
    print("Showing welcome screen...")
    img = setup.draw_welcome_screen()
    setup.write_to_fb(img)
    await asyncio.sleep(3)

    # Simulate creating crew
    print("Showing creating crew...")
    img = setup.draw_creating_crew_screen()
    setup.write_to_fb(img)

    # Connect and create crew
    if await setup.client.connect():
        crew_code = await setup.client.create_crew("Demo LEELOO")
        if crew_code:
            print(f"Created crew: {crew_code}")

            img = setup.draw_crew_created_screen(crew_code)
            setup.write_to_fb(img)
            await asyncio.sleep(5)

            img = setup.draw_setup_complete_screen(crew_code, 1)
            setup.write_to_fb(img)
            await asyncio.sleep(3)

    print("Demo complete!")


if __name__ == '__main__':
    asyncio.run(demo())
