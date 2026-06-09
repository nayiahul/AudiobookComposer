#!/usr/bin/env python3
"""
Subtitle Parser Module

This module parses SRT subtitle files and extracts timing and text information.
"""

from dataclasses import dataclass
from typing import List, Optional
import re


@dataclass
class SubtitleSegment:
    """Subtitle segment with timing and text"""
    index: int
    start_time: float  # Seconds
    end_time: float    # Seconds
    text: str
    cleaned_text: str = ""  # Text without punctuation/whitespace


class SubtitleParser:
    """
    SRT subtitle file parser.
    
    Parses SRT format subtitles and extracts:
    - Subtitle index
    - Start and end timestamps (converted to seconds)
    - Original text
    - Cleaned text (for matching)
    """
    
    def __init__(self):
        self.debug = False
    
    def parse_srt(self, srt_path: str) -> List[SubtitleSegment]:
        """
        Parse SRT subtitle file.
        
        Args:
            srt_path: Path to SRT file
            
        Returns:
            List of SubtitleSegment objects
            
        Raises:
            RuntimeError: If file cannot be parsed
        """
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            segments = self._parse_srt_content(content)
            
            if self.debug:
                print(f"Parsed {len(segments)} subtitle segments from {srt_path}")
            
            return segments
            
        except Exception as e:
            raise RuntimeError(f"Failed to parse SRT file: {str(e)}")
    
    def parse_srt_content(self, content: str) -> List[SubtitleSegment]:
        """
        Parse SRT content from string.
        
        Args:
            content: SRT file content as string
            
        Returns:
            List of SubtitleSegment objects
        """
        return self._parse_srt_content(content)
    
    def _parse_srt_content(self, content: str) -> List[SubtitleSegment]:
        """Internal method to parse SRT content."""
        segments = []
        
        # Split by double newline to get individual subtitle blocks
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            if not block.strip():
                continue
            
            try:
                segment = self._parse_subtitle_block(block)
                if segment:
                    segments.append(segment)
            except Exception as e:
                if self.debug:
                    print(f"Warning: Failed to parse subtitle block: {e}")
                    print(f"Block content: {block[:100]}...")
                continue
        
        return segments
    
    def _parse_subtitle_block(self, block: str) -> Optional[SubtitleSegment]:
        """
        Parse a single subtitle block.
        
        Expected format:
        1
        00:00:01,000 --> 00:00:03,000
        Subtitle text here
        """
        lines = block.strip().split('\n')
        
        if len(lines) < 3:
            return None
        
        # Parse index
        try:
            index = int(lines[0].strip())
        except ValueError:
            # Sometimes index might be missing or malformed
            index = 0
        
        # Parse timing line — accepts 3-5 digit milliseconds
        timing_line = lines[1].strip()
        timing_match = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3,5})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3,5})',
            timing_line
        )

        if not timing_match:
            if self.debug:
                print(f"Warning: Invalid timing format: {timing_line}")
            return None

        # Extract timing components
        start_h, start_m, start_s = map(int, timing_match.groups()[:3])
        end_h, end_m, end_s = map(int, timing_match.groups()[4:7])

        # Normalize millisecond strings to 3 digits (take first 3 chars)
        start_ms_str = timing_match.group(4)
        end_ms_str = timing_match.group(8)
        start_ms = int(start_ms_str[:3].ljust(3, '0'))
        end_ms = int(end_ms_str[:3].ljust(3, '0'))

        # Convert to seconds
        start_time = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000.0
        end_time = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000.0
        
        # Extract text (everything after timing line)
        text = '\n'.join(lines[2:]).strip()
        
        # Clean text for matching
        cleaned_text = self._clean_text(text)
        
        return SubtitleSegment(
            index=index,
            start_time=start_time,
            end_time=end_time,
            text=text,
            cleaned_text=cleaned_text
        )
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text for matching purposes.
        
        Removes:
        - HTML tags
        - Punctuation
        - Extra whitespace
        - Line breaks
        
        Args:
            text: Original text
            
        Returns:
            Cleaned text
        """
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove common punctuation (but keep Chinese characters)
        # Keep: letters, numbers, Chinese characters
        # Remove: punctuation, symbols
        text = re.sub(r'[，。！？；：、""''（）《》【】…—\s\.,!?;:\'"()\[\]{}<>-]', '', text)
        
        return text
    
    def validate_subtitles(self, segments: List[SubtitleSegment]) -> dict:
        """
        Validate subtitle segments for common issues.
        
        Args:
            segments: List of subtitle segments
            
        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []
        
        if not segments:
            issues.append("No subtitle segments found")
            return {
                'valid': False,
                'issues': issues,
                'warnings': warnings
            }
        
        # Check for timing issues
        for i, segment in enumerate(segments):
            # Check if end time is after start time
            if segment.end_time <= segment.start_time:
                issues.append(f"Segment {segment.index}: End time <= start time")
            
            # Check for negative times
            if segment.start_time < 0 or segment.end_time < 0:
                issues.append(f"Segment {segment.index}: Negative timestamp")
            
            # Check for empty text
            if not segment.text.strip():
                warnings.append(f"Segment {segment.index}: Empty text")
            
            # Check for overlapping segments
            if i > 0:
                prev_segment = segments[i - 1]
                if segment.start_time < prev_segment.end_time:
                    warnings.append(
                        f"Segment {segment.index}: Overlaps with previous segment"
                    )
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'total_segments': len(segments),
            'total_duration': segments[-1].end_time if segments else 0
        }


def main():
    """Test the subtitle parser."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python subtitle_parser.py <srt_file>")
        sys.exit(1)
    
    srt_path = sys.argv[1]
    
    parser = SubtitleParser()
    parser.debug = True
    
    try:
        segments = parser.parse_srt(srt_path)
        
        print(f"\n=== Parsing Results ===")
        print(f"Total segments: {len(segments)}")
        
        if segments:
            print(f"Duration: {segments[-1].end_time:.2f} seconds")
            print(f"\nFirst 5 segments:")
            for segment in segments[:5]:
                print(f"\n[{segment.index}] {segment.start_time:.2f}s - {segment.end_time:.2f}s")
                print(f"  Text: {segment.text[:50]}...")
                print(f"  Cleaned: {segment.cleaned_text[:50]}...")
        
        # Validate
        validation = parser.validate_subtitles(segments)
        print(f"\n=== Validation ===")
        print(f"Valid: {validation['valid']}")
        if validation['issues']:
            print(f"Issues: {validation['issues']}")
        if validation['warnings']:
            print(f"Warnings: {validation['warnings']}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
