#!/usr/bin/env python3
"""
LEELOO Spotify Integration
Handles Spotify scancode generation and track lookups.
"""

import os
import io
import hashlib
from typing import Optional, Tuple
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None

from PIL import Image

from leeloo_config import Config


def get_scancode_url(spotify_uri: str,
                     bg_color: str = None,
                     fg_color: str = None,
                     size: int = None) -> str:
    """
    Generate Spotify scancode URL for a given URI.

    Args:
        spotify_uri: Spotify URI like 'spotify:track:4iV5W9uYEdYUVa79Axb7Rh'
        bg_color: Background color (hex without #, default from config)
        fg_color: Foreground color ('white' or 'black', default from config)
        size: Size in pixels (default from config)

    Returns:
        URL to the scancode PNG image

    Example:
        >>> get_scancode_url('spotify:track:4iV5W9uYEdYUVa79Axb7Rh')
        'https://scannables.scdn.co/uri/plain/png/1A1D2E/white/280/spotify:track:4iV5W9uYEdYUVa79Axb7Rh'
    """
    bg = bg_color or Config.SPOTIFY_SCANCODE_BG_COLOR
    fg = fg_color or Config.SPOTIFY_SCANCODE_FG_COLOR
    sz = size or Config.SPOTIFY_SCANCODE_SIZE

    # URL encode the URI (handles special characters)
    encoded_uri = quote(spotify_uri, safe=':')

    return f"{Config.SPOTIFY_SCANCODE_BASE_URL}/{bg}/{fg}/{sz}/{encoded_uri}"


def download_scancode(spotify_uri: str, save_path: str = None) -> Optional[Image.Image]:
    """
    Download Spotify scancode image.

    Args:
        spotify_uri: Spotify URI
        save_path: Optional path to save the image

    Returns:
        PIL Image object or None if failed
    """
    if requests is None:
        print("[SPOTIFY] requests library not installed")
        return None

    url = get_scancode_url(spotify_uri)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        img = Image.open(io.BytesIO(response.content))

        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            img.save(save_path)
            print(f"[SPOTIFY] Saved scancode to {save_path}")

        return img

    except requests.RequestException as e:
        print(f"[SPOTIFY] Failed to download scancode: {e}")
        return None
    except Exception as e:
        print(f"[SPOTIFY] Error processing scancode: {e}")
        return None


def get_cached_scancode(spotify_uri: str) -> Optional[str]:
    """
    Get scancode from cache or download if not cached.

    Args:
        spotify_uri: Spotify URI

    Returns:
        Path to cached scancode image, or None if failed
    """
    # Create cache filename from URI hash
    uri_hash = hashlib.md5(spotify_uri.encode()).hexdigest()[:12]
    cache_path = os.path.join(Config.ALBUM_ART_DIR, f"scancode_{uri_hash}.png")

    # Return cached if exists
    if os.path.exists(cache_path):
        return cache_path

    # Download and cache
    img = download_scancode(spotify_uri, cache_path)
    if img:
        return cache_path

    return None


def parse_spotify_uri(uri_or_url: str) -> Optional[str]:
    """
    Parse Spotify URI from various formats.

    Accepts:
        - spotify:track:4iV5W9uYEdYUVa79Axb7Rh
        - https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh
        - open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh

    Returns:
        Canonical Spotify URI or None if invalid
    """
    if not uri_or_url:
        return None

    # Already a URI
    if uri_or_url.startswith('spotify:'):
        return uri_or_url

    # Parse URL
    uri_or_url = uri_or_url.replace('https://', '').replace('http://', '')

    if 'open.spotify.com/' in uri_or_url:
        # Format: open.spotify.com/track/ID or open.spotify.com/track/ID?si=xxx
        parts = uri_or_url.split('open.spotify.com/')[1].split('?')[0].split('/')
        if len(parts) >= 2:
            resource_type = parts[0]  # track, album, artist, playlist
            resource_id = parts[1]
            return f"spotify:{resource_type}:{resource_id}"

    return None


def get_track_info(spotify_uri: str) -> Optional[dict]:
    """
    Get track information from Spotify.

    Note: This requires Spotify API credentials for full functionality.
    For now, returns a placeholder structure.

    Args:
        spotify_uri: Spotify track URI

    Returns:
        Dict with artist, track, album, etc. or None
    """
    # TODO: Implement full Spotify API integration
    # For now, we just validate the URI format
    if not spotify_uri or not spotify_uri.startswith('spotify:track:'):
        return None

    # Placeholder - in production, this would call Spotify Web API
    return {
        'uri': spotify_uri,
        'artist': 'Unknown Artist',
        'track': 'Unknown Track',
        'album': 'Unknown Album',
        'album_art_url': None,
    }


def create_scancode_with_art(spotify_uri: str,
                              album_art: Image.Image = None,
                              output_size: Tuple[int, int] = (280, 280)) -> Optional[Image.Image]:
    """
    Create a combined image with album art and scancode.

    The scancode is overlaid on top of the album art with proper positioning.

    Args:
        spotify_uri: Spotify URI
        album_art: Album art PIL Image (optional)
        output_size: Output image size

    Returns:
        Combined PIL Image or None
    """
    scancode = download_scancode(spotify_uri)
    if not scancode:
        return album_art

    if album_art is None:
        return scancode

    # Resize album art to output size
    art = album_art.resize(output_size, Image.Resampling.LANCZOS)

    # Resize scancode to fit at bottom
    scancode_height = output_size[1] // 4
    scancode_ratio = scancode.width / scancode.height
    scancode_width = int(scancode_height * scancode_ratio)
    scancode = scancode.resize((scancode_width, scancode_height), Image.Resampling.LANCZOS)

    # Position scancode at bottom center
    x = (output_size[0] - scancode_width) // 2
    y = output_size[1] - scancode_height - 10

    # Paste scancode onto art
    art.paste(scancode, (x, y))

    return art


# Example usage
if __name__ == '__main__':
    # Test scancode generation
    test_uri = "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"

    print(f"Scancode URL: {get_scancode_url(test_uri)}")

    # Test URL parsing
    test_url = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh?si=abc123"
    parsed = parse_spotify_uri(test_url)
    print(f"Parsed URI: {parsed}")

    # Test download
    if requests:
        img = download_scancode(test_uri)
        if img:
            print(f"Downloaded scancode: {img.size}")
            img.show()
    else:
        print("Install 'requests' library for download functionality")
