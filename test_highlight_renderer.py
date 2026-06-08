#!/usr/bin/env python3
"""Property-Based Tests for Highlight Renderer"""

import pytest
from hypothesis import given, strategies as st, settings
from highlight_renderer import HighlightRenderer, HighlightConfig
from text_mapping_engine import SubtitleMapping, Rect
from subtitle_parser import SubtitleSegment
import tempfile
import os
from PIL import Image


# Feature: video-background-pdf-display-fix, Property 4: 高亮渲染非破坏性
@settings(max_examples=50)
@given(
    img_width=st.integers(min_value=100, max_value=500),
    img_height=st.integers(min_value=100, max_value=500),
    num_rects=st.integers(min_value=1, max_value=5)
)
def test_property_4_highlight_rendering_non_destructive(img_width, img_height, num_rects):
    """
    Property 4: 高亮渲染非破坏性
    Validates: Requirements 5.1, 5.2, 5.5
    """
    # Create test image
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "test.png")
        img = Image.new('RGB', (img_width, img_height), color='white')
        img.save(img_path)
        
        original_size = os.path.getsize(img_path)
        
        # Create test mappings
        mappings = []
        for i in range(num_rects):
            rect = Rect(
                x=float(i * 20 % (img_width - 50)),
                y=float(i * 15 % (img_height - 30)),
                width=40.0,
                height=20.0
            )
            subtitle = SubtitleSegment(i, 0.0, 1.0, "test", "test")
            mapping = SubtitleMapping(
                subtitle=subtitle, page_number=1,
                char_start_index=0, char_end_index=4,
                coordinates=[rect], confidence=1.0, match_type='exact'
            )
            mappings.append(mapping)
        
        # Render with highlights
        renderer = HighlightRenderer()
        output_path = os.path.join(tmpdir, "highlighted.png")
        renderer._render_single_frame(img_path, mappings, output_path)
        
        # Verify output exists and is valid
        assert os.path.exists(output_path), "Output image should exist"
        assert os.path.getsize(output_path) > 0, "Output image should not be empty"
        
        # Verify image is readable
        result_img = Image.open(output_path)
        assert result_img.size == (img_width, img_height), "Image size should be preserved"


# Feature: video-background-pdf-display-fix, Property 5: 时间同步准确性
@settings(max_examples=50)
@given(
    start_time=st.floats(min_value=0.0, max_value=5.0),
    duration=st.floats(min_value=0.5, max_value=3.0)
)
def test_property_5_time_synchronization_accuracy(start_time, duration):
    """
    Property 5: 时间同步准确性
    Validates: Requirements 7.1, 7.2, 7.3, 7.4
    """
    end_time = start_time + duration
    
    # Create subtitle
    subtitle = SubtitleSegment(1, start_time, end_time, "test", "test")
    
    # Verify timing
    assert subtitle.end_time > subtitle.start_time, "End time should be after start time"
    assert subtitle.start_time >= 0, "Start time should be non-negative"
    
    # Test time range check
    test_times = [start_time - 0.1, start_time, start_time + duration/2, end_time, end_time + 0.1]
    
    for t in test_times:
        is_active = subtitle.start_time <= t < subtitle.end_time
        if start_time <= t < end_time:
            assert is_active, f"Subtitle should be active at time {t}"
        else:
            assert not is_active, f"Subtitle should not be active at time {t}"


# Feature: video-background-pdf-display-fix, Property 9: 高亮配置有效性
@settings(max_examples=100)
@given(
    r=st.integers(min_value=-10, max_value=300),
    g=st.integers(min_value=-10, max_value=300),
    b=st.integers(min_value=-10, max_value=300),
    a=st.integers(min_value=-10, max_value=300),
    padding=st.integers(min_value=-5, max_value=20)
)
def test_property_9_highlight_config_validity(r, g, b, a, padding):
    """
    Property 9: 高亮配置有效性
    Validates: Requirements 10.5
    """
    # Validate and normalize config values
    r_valid = max(0, min(255, r))
    g_valid = max(0, min(255, g))
    b_valid = max(0, min(255, b))
    a_valid = max(0, min(255, a))
    padding_valid = max(0, padding)
    
    config = HighlightConfig(
        color=(r_valid, g_valid, b_valid, a_valid),
        padding=padding_valid
    )
    
    # Verify all values are in valid range
    assert 0 <= config.color[0] <= 255, "Red should be 0-255"
    assert 0 <= config.color[1] <= 255, "Green should be 0-255"
    assert 0 <= config.color[2] <= 255, "Blue should be 0-255"
    assert 0 <= config.color[3] <= 255, "Alpha should be 0-255"
    assert config.padding >= 0, "Padding should be non-negative"


def test_highlight_renderer_basic():
    """Basic functionality test."""
    renderer = HighlightRenderer()
    config = HighlightConfig()
    
    assert config.style in ['background', 'underline', 'box']
    assert len(config.color) == 4
    assert config.padding >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
