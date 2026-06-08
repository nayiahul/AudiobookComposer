#!/usr/bin/env python3
"""
Text Mapping Engine

Maps subtitle text to PDF text coordinates for highlighting.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from difflib import SequenceMatcher
from pdf_text_extractor import PageTextData, CharacterData
from subtitle_parser import SubtitleSegment


@dataclass
class Rect:
    """Rectangle region"""
    x: float
    y: float
    width: float
    height: float


@dataclass
class SubtitleMapping:
    """Mapping from subtitle to PDF text coordinates"""
    subtitle: SubtitleSegment
    page_number: int
    char_start_index: int
    char_end_index: int
    coordinates: List[Rect]
    confidence: float  # 0-1
    match_type: str  # 'exact', 'fuzzy', 'approximate'


class TextMappingEngine:
    """
    Maps subtitle text to PDF text coordinates.
    
    Supports:
    - Exact matching
    - Fuzzy matching (punctuation, whitespace)
    - Simplified-Traditional Chinese conversion
    """
    
    def __init__(self):
        self.debug = False
        self.min_confidence = 0.5
    
    def map_subtitles_to_text(
        self,
        subtitles: List[SubtitleSegment],
        pages_text: List[PageTextData],
        fuzzy_match: bool = True
    ) -> List[SubtitleMapping]:
        """
        Map subtitles to PDF text.
        
        Args:
            subtitles: List of subtitle segments
            pages_text: List of page text data
            fuzzy_match: Enable fuzzy matching
            
        Returns:
            List of subtitle mappings
        """
        mappings = []
        
        # Build full text index
        full_text, char_to_page = self._build_text_index(pages_text)
        
        for subtitle in subtitles:
            mapping = self._map_single_subtitle(
                subtitle, full_text, char_to_page, pages_text, fuzzy_match
            )
            if mapping:
                mappings.append(mapping)
        
        if self.debug:
            print(f"Mapped {len(mappings)}/{len(subtitles)} subtitles")
        
        return mappings
    
    def _build_text_index(
        self, pages_text: List[PageTextData]
    ) -> Tuple[str, List[Tuple[int, int]]]:
        """Build full text and character-to-page mapping."""
        full_text_parts = []
        char_to_page = []
        
        for page_data in pages_text:
            page_text = ''.join([c.char for c in page_data.characters])
            full_text_parts.append(page_text)
            
            for char in page_data.characters:
                char_to_page.append((page_data.page_number, char.index))
        
        return ''.join(full_text_parts), char_to_page
    
    def _map_single_subtitle(
        self,
        subtitle: SubtitleSegment,
        full_text: str,
        char_to_page: List[Tuple[int, int]],
        pages_text: List[PageTextData],
        fuzzy_match: bool
    ) -> Optional[SubtitleMapping]:
        """Map a single subtitle to text."""
        search_text = subtitle.cleaned_text
        
        if not search_text:
            return None
        
        # Try exact match first
        start_idx = full_text.find(search_text)
        if start_idx != -1:
            return self._create_mapping(
                subtitle, start_idx, start_idx + len(search_text),
                char_to_page, pages_text, 1.0, 'exact'
            )
        
        # Try fuzzy match
        if fuzzy_match:
            match_result = self._fuzzy_find(search_text, full_text)
            if match_result:
                start_idx, end_idx, confidence = match_result
                if confidence >= self.min_confidence:
                    return self._create_mapping(
                        subtitle, start_idx, end_idx,
                        char_to_page, pages_text, confidence, 'fuzzy'
                    )
        
        if self.debug:
            print(f"Warning: Could not map subtitle {subtitle.index}: {search_text[:30]}...")
        
        return None
    
    def _fuzzy_find(
        self, search_text: str, full_text: str
    ) -> Optional[Tuple[int, int, float]]:
        """Find text using fuzzy matching."""
        best_match = None
        best_ratio = 0.0
        
        search_len = len(search_text)
        
        # Sliding window search
        for i in range(len(full_text) - search_len + 1):
            window = full_text[i:i + search_len]
            ratio = SequenceMatcher(None, search_text, window).ratio()
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = (i, i + search_len)
        
        if best_match and best_ratio >= self.min_confidence:
            return (best_match[0], best_match[1], best_ratio)
        
        return None
    
    def _create_mapping(
        self,
        subtitle: SubtitleSegment,
        start_idx: int,
        end_idx: int,
        char_to_page: List[Tuple[int, int]],
        pages_text: List[PageTextData],
        confidence: float,
        match_type: str
    ) -> SubtitleMapping:
        """Create mapping with coordinates."""
        if start_idx >= len(char_to_page) or end_idx > len(char_to_page):
            return None
        
        page_num, _ = char_to_page[start_idx]
        
        # Find page data
        page_data = next((p for p in pages_text if p.page_number == page_num), None)
        if not page_data:
            return None
        
        # Get character range
        char_start = start_idx
        char_end = min(end_idx, len(char_to_page))
        
        # Generate coordinate rectangles
        coordinates = self._generate_coordinates(
            char_start, char_end, char_to_page, pages_text
        )
        
        return SubtitleMapping(
            subtitle=subtitle,
            page_number=page_num,
            char_start_index=char_start,
            char_end_index=char_end,
            coordinates=coordinates,
            confidence=confidence,
            match_type=match_type
        )
    
    def _generate_coordinates(
        self,
        char_start: int,
        char_end: int,
        char_to_page: List[Tuple[int, int]],
        pages_text: List[PageTextData]
    ) -> List[Rect]:
        """Generate highlight rectangles for character range."""
        rectangles = []
        
        # Group characters by line
        current_line = []
        current_line_y = None
        
        for i in range(char_start, char_end):
            if i >= len(char_to_page):
                break
            
            page_num, char_idx = char_to_page[i]
            page_data = next((p for p in pages_text if p.page_number == page_num), None)
            
            if not page_data or char_idx >= len(page_data.characters):
                continue
            
            char = page_data.characters[char_idx]
            
            # Check if same line (similar y coordinate)
            if current_line_y is None or abs(char.y - current_line_y) < char.height * 0.5:
                current_line.append(char)
                current_line_y = char.y if current_line_y is None else current_line_y
            else:
                # New line, create rectangle for previous line
                if current_line:
                    rect = self._create_rect_from_chars(current_line)
                    rectangles.append(rect)
                
                current_line = [char]
                current_line_y = char.y
        
        # Add last line
        if current_line:
            rect = self._create_rect_from_chars(current_line)
            rectangles.append(rect)
        
        return rectangles
    
    def _create_rect_from_chars(self, chars: List[CharacterData]) -> Rect:
        """Create bounding rectangle from character list."""
        if not chars:
            return Rect(0, 0, 0, 0)
        
        min_x = min(c.x for c in chars)
        max_x = max(c.x + c.width for c in chars)
        min_y = min(c.y for c in chars)
        max_y = max(c.y + c.height for c in chars)
        
        return Rect(
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y
        )


def main():
    """Test the text mapping engine."""
    print("Text Mapping Engine - Test Mode")
    print("This module requires PDF and subtitle data to test.")


if __name__ == "__main__":
    main()
