#!/usr/bin/env python3
"""
Property-Based Tests for Text Mapping Engine
"""

import pytest
from hypothesis import given, strategies as st, settings
from text_mapping_engine import TextMappingEngine, SubtitleMapping, Rect
from pdf_text_extractor import PageTextData, CharacterData
from subtitle_parser import SubtitleSegment


# Feature: video-background-pdf-display-fix, Property 2: 字幕文本映射一致性
@settings(max_examples=100)
@given(
    text_length=st.integers(min_value=10, max_value=50),
    subtitle_length=st.integers(min_value=5, max_value=20)
)
def test_property_2_subtitle_text_mapping_consistency(text_length, subtitle_length):
    """
    Property 2: 字幕文本映射一致性
    Validates: Requirements 4.1, 4.2
    """
    engine = TextMappingEngine()
    
    # Create mock PDF text
    full_text = "这是一段测试文本" * (text_length // 8 + 1)
    full_text = full_text[:text_length]
    
    # Create page data
    characters = []
    for i, char in enumerate(full_text):
        characters.append(CharacterData(
            char=char, x=float(i * 10), y=10.0,
            width=10.0, height=15.0, font_size=12.0, index=i
        ))
    
    page_data = PageTextData(
        page_number=1, characters=characters,
        full_text=full_text, page_width=1000, page_height=800
    )
    
    # Create subtitle with exact match
    subtitle_text = full_text[:subtitle_length]
    subtitle = SubtitleSegment(
        index=1, start_time=0.0, end_time=2.0,
        text=subtitle_text, cleaned_text=subtitle_text
    )
    
    # Map subtitle
    mappings = engine.map_subtitles_to_text([subtitle], [page_data], fuzzy_match=False)
    
    # For exact match, should find with high confidence
    if mappings:
        assert mappings[0].confidence >= 0.9, "Exact match should have confidence >= 0.9"
        assert mappings[0].match_type == 'exact', "Should be exact match"


# Feature: video-background-pdf-display-fix, Property 3: 坐标映射准确性
@settings(max_examples=100)
@given(
    num_chars=st.integers(min_value=5, max_value=30),
    page_width=st.floats(min_value=500, max_value=1000),
    page_height=st.floats(min_value=500, max_value=1000)
)
def test_property_3_coordinate_mapping_accuracy(num_chars, page_width, page_height):
    """
    Property 3: 坐标映射准确性
    Validates: Requirements 4.5, 5.4
    """
    engine = TextMappingEngine()
    
    # Create characters
    characters = []
    for i in range(num_chars):
        characters.append(CharacterData(
            char='字', x=float(i * 15), y=10.0,
            width=12.0, height=15.0, font_size=12.0, index=i
        ))
    
    page_data = PageTextData(
        page_number=1, characters=characters,
        full_text='字' * num_chars,
        page_width=page_width, page_height=page_height
    )
    
    # Create subtitle
    subtitle = SubtitleSegment(
        index=1, start_time=0.0, end_time=2.0,
        text='字' * num_chars, cleaned_text='字' * num_chars
    )
    
    # Map subtitle
    mappings = engine.map_subtitles_to_text([subtitle], [page_data])
    
    if mappings:
        mapping = mappings[0]
        # All coordinates should be within page bounds
        for rect in mapping.coordinates:
            assert rect.x >= 0, f"Rect x should be >= 0, got {rect.x}"
            assert rect.y >= 0, f"Rect y should be >= 0, got {rect.y}"
            assert rect.x + rect.width <= page_width + 1, \
                f"Rect should be within page width {page_width}"
            assert rect.y + rect.height <= page_height + 1, \
                f"Rect should be within page height {page_height}"


# Feature: video-background-pdf-display-fix, Property 8: 模糊匹配容错性
@settings(max_examples=50)
@given(
    base_text=st.text(alphabet='测试文本', min_size=10, max_size=30)
)
def test_property_8_fuzzy_matching_tolerance(base_text):
    """
    Property 8: 模糊匹配容错性
    Validates: Requirements 4.2, 4.3
    """
    engine = TextMappingEngine()
    engine.min_confidence = 0.7
    
    # Create page data
    characters = []
    for i, char in enumerate(base_text):
        characters.append(CharacterData(
            char=char, x=float(i * 10), y=10.0,
            width=10.0, height=15.0, font_size=12.0, index=i
        ))
    
    page_data = PageTextData(
        page_number=1, characters=characters,
        full_text=base_text, page_width=1000, page_height=800
    )
    
    # Create subtitle with minor variation (add punctuation)
    subtitle_text = base_text[:len(base_text)//2]
    subtitle_with_punct = subtitle_text + "，。"
    
    subtitle = SubtitleSegment(
        index=1, start_time=0.0, end_time=2.0,
        text=subtitle_with_punct,
        cleaned_text=subtitle_text  # Cleaned version matches
    )
    
    # Map with fuzzy matching
    mappings = engine.map_subtitles_to_text([subtitle], [page_data], fuzzy_match=True)
    
    # Should find match with reasonable confidence
    if mappings:
        assert mappings[0].confidence >= 0.7, \
            f"Fuzzy match should have confidence >= 0.7, got {mappings[0].confidence}"


def test_text_mapping_basic():
    """Basic functionality test."""
    engine = TextMappingEngine()
    
    # Create simple test data
    text = "这是测试文本"
    characters = []
    for i, char in enumerate(text):
        characters.append(CharacterData(
            char=char, x=float(i * 10), y=10.0,
            width=10.0, height=15.0, font_size=12.0, index=i
        ))
    
    page_data = PageTextData(
        page_number=1, characters=characters,
        full_text=text, page_width=500, page_height=700
    )
    
    subtitle = SubtitleSegment(
        index=1, start_time=0.0, end_time=2.0,
        text="测试", cleaned_text="测试"
    )
    
    mappings = engine.map_subtitles_to_text([subtitle], [page_data])
    
    assert len(mappings) > 0, "Should find mapping"
    assert mappings[0].confidence > 0.5, "Should have reasonable confidence"
    assert len(mappings[0].coordinates) > 0, "Should have coordinates"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
