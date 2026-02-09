#!/usr/bin/env python3
"""
Fast Framebuffer - Optimized framebuffer access for Raspberry Pi

Uses:
- numpy vectorized RGB565 conversion (7-17x faster than pixel loops)
- mmap for direct memory access (no file I/O overhead per frame)
- Pre-allocated buffers (no allocation during animation)

Based on research from:
- https://github.com/mutatrum/fast-pillow-fb
- https://github.com/chidea/FBpyGIF
- https://gist.github.com/Darfk/5790622
"""

import numpy as np
from PIL import Image
import mmap
import os
import time
from typing import Optional, Tuple

# Screen constants
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
BYTES_PER_PIXEL = 2  # RGB565


class FastFramebuffer:
    """
    High-performance framebuffer access using numpy memmap

    Usage:
        fb = FastFramebuffer()
        fb.write_image(pil_image)  # Full screen
        fb.write_region(pil_image, x, y)  # Region only
        fb.close()
    """

    def __init__(self, fb_path: str = '/dev/fb1', width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT):
        """
        Initialize framebuffer with numpy memmap for fastest access

        Args:
            fb_path: Path to framebuffer device
            width: Screen width in pixels
            height: Screen height in pixels
        """
        self.fb_path = fb_path
        self.width = width
        self.height = height
        self.buffer_size = width * height * BYTES_PER_PIXEL

        # Try numpy memmap first (fastest)
        self.np_fb = None
        self.mmap_buffer = None
        self.fb_file = None
        self._mmap_available = False

        try:
            # numpy memmap gives us direct array access to framebuffer
            self.np_fb = np.memmap(fb_path, dtype=np.uint16, mode='r+', shape=(height, width))
            self._mmap_available = True
            self._use_numpy_memmap = True
        except (FileNotFoundError, PermissionError, OSError) as e:
            print(f"Warning: Could not numpy.memmap {fb_path}: {e}")
            self._use_numpy_memmap = False

            # Fall back to Python mmap
            try:
                self.fb_file = open(fb_path, 'r+b')
                self.mmap_buffer = mmap.mmap(
                    self.fb_file.fileno(),
                    self.buffer_size,
                    mmap.MAP_SHARED,
                    mmap.PROT_READ | mmap.PROT_WRITE
                )
                self._mmap_available = True
            except (FileNotFoundError, PermissionError, OSError) as e2:
                print(f"Warning: Could not mmap {fb_path}: {e2}")
                print("Falling back to file I/O mode")
                if self.fb_file:
                    self.fb_file.close()
                    self.fb_file = None

        # Pre-allocate reusable numpy array for full screen
        self._screen_buffer = np.zeros((height, width), dtype=np.uint16)

    def close(self):
        """Clean up mmap and file handles"""
        if self.np_fb is not None:
            del self.np_fb
            self.np_fb = None
        if self.mmap_buffer:
            self.mmap_buffer.close()
            self.mmap_buffer = None
        if self.fb_file:
            self.fb_file.close()
            self.fb_file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def rgb_to_rgb565_fast(image: Image.Image) -> np.ndarray:
        """
        Convert PIL RGB image to RGB565 numpy array using vectorized operations

        This is the key optimization - ~7-17x faster than pixel loops

        Args:
            image: PIL Image in RGB mode

        Returns:
            numpy array of uint16 RGB565 values
        """
        # Convert PIL image to numpy array
        if image.mode != 'RGB':
            image = image.convert('RGB')

        img_array = np.array(image, dtype=np.uint16)

        # Vectorized RGB888 to RGB565 conversion
        # R: 8 bits -> 5 bits (>> 3, << 11)
        # G: 8 bits -> 6 bits (>> 2, << 5)
        # B: 8 bits -> 5 bits (>> 3)
        r = (img_array[:, :, 0] >> 3) << 11
        g = (img_array[:, :, 1] >> 2) << 5
        b = img_array[:, :, 2] >> 3

        rgb565 = (r | g | b).astype(np.uint16)

        return rgb565

    def write_image(self, image: Image.Image):
        """
        Write full screen image to framebuffer

        Args:
            image: PIL Image (will be converted to RGB565)
        """
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)

        rgb565 = self.rgb_to_rgb565_fast(image)

        if self._use_numpy_memmap and self.np_fb is not None:
            # FASTEST: Direct numpy array assignment
            self.np_fb[:] = rgb565
        elif self._mmap_available and self.mmap_buffer:
            # Direct mmap write
            data = rgb565.tobytes()
            self.mmap_buffer.seek(0)
            self.mmap_buffer.write(data)
        else:
            # Fallback to file I/O
            data = rgb565.tobytes()
            with open(self.fb_path, 'wb') as fb:
                fb.write(data)

    def write_region(self, image: Image.Image, x: int, y: int):
        """
        Write a region to the framebuffer (for partial updates)

        Args:
            image: PIL Image for the region
            x, y: Top-left position on screen
        """
        width, height = image.size

        # Bounds checking
        if x < 0 or y < 0 or x + width > self.width or y + height > self.height:
            raise ValueError(f"Region ({x}, {y}, {width}x{height}) out of bounds")

        rgb565 = self.rgb_to_rgb565_fast(image)

        if self._mmap_available and self.mmap_buffer:
            # Write row by row to mmap
            for row in range(height):
                offset = ((y + row) * self.width + x) * BYTES_PER_PIXEL
                row_data = rgb565[row, :].tobytes()
                self.mmap_buffer.seek(offset)
                self.mmap_buffer.write(row_data)
        else:
            # Fallback to file I/O
            with open(self.fb_path, 'r+b') as fb:
                for row in range(height):
                    offset = ((y + row) * self.width + x) * BYTES_PER_PIXEL
                    row_data = rgb565[row, :].tobytes()
                    fb.seek(offset)
                    fb.write(row_data)

    def write_rgb565_bytes(self, data: bytes, x: int, y: int, width: int, height: int):
        """
        Write pre-converted RGB565 bytes to a region

        This is the fastest option when you have pre-processed frames

        Args:
            data: RGB565 bytes (little-endian uint16)
            x, y: Top-left position
            width, height: Region dimensions
        """
        if self._mmap_available and self.mmap_buffer:
            # Convert bytes to numpy array for faster slicing
            region_array = np.frombuffer(data, dtype=np.uint16).reshape(height, width)

            # Write each row directly using mmap slicing
            for row in range(height):
                offset = ((y + row) * self.width + x) * BYTES_PER_PIXEL
                row_data = region_array[row, :].tobytes()
                self.mmap_buffer[offset:offset + width * BYTES_PER_PIXEL] = row_data
        else:
            with open(self.fb_path, 'r+b') as fb:
                for row in range(height):
                    offset = ((y + row) * self.width + x) * BYTES_PER_PIXEL
                    row_start = row * width * BYTES_PER_PIXEL
                    row_end = row_start + width * BYTES_PER_PIXEL
                    fb.seek(offset)
                    fb.write(data[row_start:row_end])

    def write_rgb565_array(self, rgb565: np.ndarray, x: int, y: int):
        """
        Write numpy RGB565 array to a region - fastest method

        Args:
            rgb565: 2D numpy array of uint16 RGB565 values
            x, y: Top-left position
        """
        height, width = rgb565.shape

        if self._use_numpy_memmap and self.np_fb is not None:
            # Direct region write - only update the changed pixels
            # This is faster and causes less tearing than full-screen writes
            self.np_fb[y:y+height, x:x+width] = rgb565
        elif self._mmap_available and self.mmap_buffer:
            # Fallback to Python mmap with row-by-row writes
            for row in range(height):
                offset = ((y + row) * self.width + x) * BYTES_PER_PIXEL
                end_offset = offset + width * BYTES_PER_PIXEL
                self.mmap_buffer[offset:end_offset] = rgb565[row, :].tobytes()
        else:
            data = rgb565.tobytes()
            with open(self.fb_path, 'r+b') as fb:
                for row in range(height):
                    offset = ((y + row) * self.width + x) * BYTES_PER_PIXEL
                    row_start = row * width * BYTES_PER_PIXEL
                    row_end = row_start + width * BYTES_PER_PIXEL
                    fb.seek(offset)
                    fb.write(data[row_start:row_end])

    def sync_screen_buffer(self, full_image_rgb565: np.ndarray = None):
        """
        Initialize the screen buffer with the current screen content.
        Call this before starting animations to prevent tearing.

        Args:
            full_image_rgb565: Full screen RGB565 array (320x480), or None to read from framebuffer
        """
        if full_image_rgb565 is not None:
            self._screen_buffer[:] = full_image_rgb565
        elif self._use_numpy_memmap and self.np_fb is not None:
            # Read current framebuffer content into screen buffer
            self._screen_buffer[:] = self.np_fb[:]


class AnimationBuffer:
    """
    Pre-processes animation frames for maximum playback speed

    Usage:
        anim = AnimationBuffer()
        anim.add_frame(pil_image)
        anim.add_frame(pil_image2)
        anim.preprocess()  # Convert all to RGB565

        fb = FastFramebuffer()
        anim.play(fb, x, y, fps=30)
    """

    def __init__(self):
        self.frames: list = []  # PIL images
        self.processed_frames: list = []  # RGB565 bytes
        self.frame_size: Optional[Tuple[int, int]] = None

    def add_frame(self, image: Image.Image):
        """Add a PIL image frame"""
        if self.frame_size is None:
            self.frame_size = image.size
        elif image.size != self.frame_size:
            image = image.resize(self.frame_size, Image.Resampling.LANCZOS)

        self.frames.append(image)

    def preprocess(self):
        """Convert all frames to RGB565 bytes (call once before playback)"""
        self.processed_frames = []
        for frame in self.frames:
            rgb565 = FastFramebuffer.rgb_to_rgb565_fast(frame)
            self.processed_frames.append(rgb565.tobytes())

    def play(self, fb: FastFramebuffer, x: int, y: int, fps: float = 30, loops: int = 1):
        """
        Play the animation

        Args:
            fb: FastFramebuffer instance
            x, y: Position on screen
            fps: Target frames per second
            loops: Number of times to loop (0 = infinite)
        """
        if not self.processed_frames:
            self.preprocess()

        width, height = self.frame_size
        frame_time = 1.0 / fps
        frame_count = len(self.processed_frames)

        loop_count = 0
        while loops == 0 or loop_count < loops:
            start_time = time.time()

            for i, frame_bytes in enumerate(self.processed_frames):
                frame_start = time.time()

                fb.write_rgb565_bytes(frame_bytes, x, y, width, height)

                # Maintain timing
                elapsed = time.time() - frame_start
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            loop_count += 1

        actual_duration = time.time() - start_time
        actual_fps = frame_count / actual_duration
        return actual_fps


def benchmark():
    """Benchmark the fast framebuffer vs old method"""
    from PIL import ImageDraw

    print("FastFramebuffer Benchmark")
    print("=" * 50)

    # Create test image
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), '#1A1D2E')
    draw = ImageDraw.Draw(img)
    for i in range(0, SCREEN_HEIGHT, 20):
        draw.rectangle([0, i, SCREEN_WIDTH, i+10], fill='#719253')

    # Benchmark old method (pixel loop)
    print("\n1. Old method (pixel-by-pixel loop):")
    start = time.time()
    for _ in range(10):
        pixels = img.load()
        data = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT * 2)
        idx = 0
        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                r, g, b = pixels[x, y]
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                data[idx] = rgb565 & 0xFF
                data[idx + 1] = (rgb565 >> 8) & 0xFF
                idx += 2
    old_time = (time.time() - start) / 10
    print(f"   Average: {old_time*1000:.1f}ms per frame ({1/old_time:.1f} fps)")

    # Benchmark new method (numpy vectorized)
    print("\n2. New method (numpy vectorized):")
    start = time.time()
    for _ in range(100):
        rgb565 = FastFramebuffer.rgb_to_rgb565_fast(img)
        data = rgb565.tobytes()
    new_time = (time.time() - start) / 100
    print(f"   Average: {new_time*1000:.1f}ms per frame ({1/new_time:.1f} fps)")

    speedup = old_time / new_time
    print(f"\n   Speedup: {speedup:.1f}x faster!")

    # Test mmap if available
    print("\n3. Testing framebuffer access:")
    try:
        with FastFramebuffer('/dev/fb1') as fb:
            if fb._use_numpy_memmap:
                print("   Using numpy.memmap (fastest)")
            elif fb._mmap_available:
                print("   Using Python mmap")
            else:
                print("   Using file I/O fallback")

            if fb._mmap_available:
                # Full screen test
                start = time.time()
                for _ in range(30):
                    fb.write_image(img)
                write_time = (time.time() - start) / 30
                print(f"   Full screen write: {write_time*1000:.1f}ms ({1/write_time:.1f} fps)")

                # Region test (simulating animation frame)
                region = Image.new('RGB', (210, 290), '#1A1D2E')
                rgb565 = FastFramebuffer.rgb_to_rgb565_fast(region)
                start = time.time()
                for _ in range(60):
                    fb.write_rgb565_array(rgb565, 5, 16)
                region_time = (time.time() - start) / 60
                print(f"   Region write (210x290): {region_time*1000:.1f}ms ({1/region_time:.1f} fps)")
    except Exception as e:
        print(f"   Could not test: {e}")


if __name__ == "__main__":
    benchmark()
