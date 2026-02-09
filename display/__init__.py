"""
LEELOO Display Module

High-performance display components using numpy and mmap optimization.
"""

from .fast_fb import FastFramebuffer, AnimationBuffer
from .frame_animator import (
    FrameAnimator,
    FrameType,
    FrameGeometry,
    get_frame_geometries,
    get_expanded_geometry,
    ease_in_out_cubic,
    rgb_to_rgb565_fast,
    write_region_to_framebuffer_rowbyrow,
    FRAME_GEOMETRIES,
    EXPANDED_GEOMETRY,
)

__all__ = [
    # Fast framebuffer
    'FastFramebuffer',
    'AnimationBuffer',
    # Frame animator
    'FrameAnimator',
    'FrameType',
    'FrameGeometry',
    'get_frame_geometries',
    'get_expanded_geometry',
    'ease_in_out_cubic',
    'rgb_to_rgb565_fast',
    'write_region_to_framebuffer_rowbyrow',
    'FRAME_GEOMETRIES',
    'EXPANDED_GEOMETRY',
]
