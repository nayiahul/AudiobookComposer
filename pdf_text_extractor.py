#!/usr/bin/env python3
"""
PDF Text Extractor Module

This module extracts text content and character-level coordinates from PDF files.
Supports both horizontal and vertical text layouts, and handles double-page spreads.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import fitz  # PyMuPDF


@dataclass
class CharacterData:
    """Character data with position information"""
    char: str
    x: float
    y: float
    width: float
    height: float
    font_size: float
    index: int  # Index in full text
    line_index: int = 0  # Line index for grouping


@dataclass
class PageTextData:
    """Page text data with all characters and metadata"""
    page_number: int
    characters: List[CharacterData] = field(default_factory=list)
    full_text: str = ""
    reading_order: str = "horizontal"  # 'horizontal' or 'vertical'
    layout_type: str = "single"  # 'single', 'double_left', 'double_right'
    page_width: float = 0.0
    page_height: float = 0.0


class PDFTextExtractor:
    """
    PDF text extractor with character-level coordinate extraction.
    
    Supports:
    - Horizontal and vertical text layouts
    - Double-page spreads with coordinate mapping
    - Character-level position tracking
    """
    
    def __init__(self):
        self.debug = False
    
    def extract_text_with_coordinates(
        self,
        pdf_path: str,
        page_range: Tuple[int, int],
        vertical_layout: bool = False,
        odd_right_even_left: bool = False
    ) -> List[PageTextData]:
        """
        Extract text with character coordinates from PDF.
        
        Args:
            pdf_path: Path to PDF file
            page_range: Tuple of (start_page, end_page) 1-indexed
            vertical_layout: Whether to combine two pages side by side
            odd_right_even_left: Whether to use odd-right-even-left layout
            
        Returns:
            List of PageTextData for each page (or combined page pair)
            
        Raises:
            RuntimeError: If PDF cannot be opened or processed
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            if total_pages == 0:
                raise RuntimeError(f"PDF has no pages: {pdf_path}")
            
            start_page, end_page = page_range
            if start_page < 1 or start_page > total_pages:
                raise ValueError(f"Start page {start_page} out of range (1-{total_pages})")
            
            if end_page > total_pages:
                end_page = total_pages
            
            pages_data = []
            
            if vertical_layout:
                # Process pages in pairs for vertical layout
                pages_data = self._extract_double_page_text(
                    doc, start_page, end_page, odd_right_even_left
                )
            else:
                # Process pages individually
                pages_data = self._extract_single_page_text(
                    doc, start_page, end_page
                )
            
            doc.close()
            
            if self.debug:
                print(f"Extracted text from {len(pages_data)} page(s)")
                for page_data in pages_data:
                    print(f"  Page {page_data.page_number}: {len(page_data.characters)} chars, "
                          f"reading_order={page_data.reading_order}")
            
            return pages_data
            
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF: {str(e)}")
    
    def _extract_single_page_text(
        self,
        doc: fitz.Document,
        start_page: int,
        end_page: int
    ) -> List[PageTextData]:
        """Extract text from individual pages."""
        pages_data = []
        
        for page_num in range(start_page - 1, end_page):  # Convert to 0-indexed
            page = doc[page_num]
            page_data = self._extract_page_text(page, page_num + 1)
            pages_data.append(page_data)
        
        return pages_data
    
    def _extract_double_page_text(
        self,
        doc: fitz.Document,
        start_page: int,
        end_page: int,
        odd_right_even_left: bool
    ) -> List[PageTextData]:
        """Extract text from double-page spreads."""
        pages_data = []
        actual_pages = end_page - start_page + 1
        
        for i in range(0, actual_pages, 2):
            page_num1 = start_page - 1 + i  # Convert to 0-indexed
            page_num2 = start_page - 1 + i + 1
            
            if page_num2 < len(doc):
                # Both pages exist
                page1 = doc[page_num1]
                page2 = doc[page_num2]
                
                combined_data = self._combine_double_page_text(
                    page1, page2, page_num1 + 1, page_num2 + 1, odd_right_even_left
                )
                pages_data.append(combined_data)
            else:
                # Only one page left
                page = doc[page_num1]
                page_data = self._extract_page_text(page, page_num1 + 1)
                pages_data.append(page_data)
        
        return pages_data
    
    def _extract_page_text(
        self,
        page: fitz.Page,
        page_number: int
    ) -> PageTextData:
        """Extract text from a single page."""
        # Get text with detailed information
        text_dict = page.get_text("dict")
        
        page_data = PageTextData(
            page_number=page_number,
            page_width=page.rect.width,
            page_height=page.rect.height
        )
        
        char_index = 0
        line_index = 0
        full_text_parts = []
        
        # Extract characters from blocks
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    line_chars = []
                    
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        origin = span.get("origin", (0, 0))
                        bbox = span.get("bbox", (0, 0, 0, 0))
                        font_size = span.get("size", 12)
                        
                        # Extract individual characters
                        for i, char in enumerate(text):
                            # Estimate character position within span
                            char_width = (bbox[2] - bbox[0]) / len(text) if text else 0
                            char_x = bbox[0] + i * char_width
                            char_y = bbox[1]
                            char_height = bbox[3] - bbox[1]
                            
                            char_data = CharacterData(
                                char=char,
                                x=char_x,
                                y=char_y,
                                width=char_width,
                                height=char_height,
                                font_size=font_size,
                                index=char_index,
                                line_index=line_index
                            )
                            
                            page_data.characters.append(char_data)
                            line_chars.append(char)
                            char_index += 1
                    
                    if line_chars:
                        full_text_parts.append(''.join(line_chars))
                        line_index += 1
        
        page_data.full_text = '\n'.join(full_text_parts)
        
        # Detect reading order
        page_data.reading_order = self._detect_reading_order(page_data.characters)
        
        # Sort characters by reading order
        if page_data.characters:
            page_data.characters = self._sort_characters_by_reading_order(
                page_data.characters,
                page_data.reading_order
            )
            
            # Rebuild full text based on sorted characters
            if page_data.reading_order == "vertical":
                # For vertical text, rebuild text in correct reading order
                page_data.full_text = ''.join([c.char for c in page_data.characters])
        
        return page_data
    
    def _combine_double_page_text(
        self,
        page1: fitz.Page,
        page2: fitz.Page,
        page_num1: int,
        page_num2: int,
        odd_right_even_left: bool
    ) -> PageTextData:
        """Combine text from two pages into a double-page spread."""
        # Extract text from both pages
        page1_data = self._extract_page_text(page1, page_num1)
        page2_data = self._extract_page_text(page2, page_num2)
        
        # Determine layout
        if odd_right_even_left:
            # Odd page on right, even page on left
            left_page = page2_data
            right_page = page1_data
            layout_type = "double_right"
        else:
            # Standard layout: first page on left, second on right
            left_page = page1_data
            right_page = page2_data
            layout_type = "double_left"
        
        # Create combined page data
        combined_data = PageTextData(
            page_number=page_num1,  # Use first page number
            page_width=left_page.page_width + right_page.page_width,
            page_height=max(left_page.page_height, right_page.page_height),
            reading_order=left_page.reading_order,
            layout_type=layout_type
        )
        
        # Combine characters with adjusted coordinates
        char_index = 0
        
        # Add left page characters (no offset needed)
        for char in left_page.characters:
            char.index = char_index
            combined_data.characters.append(char)
            char_index += 1
        
        # Add right page characters (offset by left page width)
        x_offset = left_page.page_width
        for char in right_page.characters:
            char.x += x_offset
            char.index = char_index
            combined_data.characters.append(char)
            char_index += 1
        
        # Combine full text
        combined_data.full_text = left_page.full_text + '\n' + right_page.full_text
        
        return combined_data
    
    def _detect_reading_order(self, characters: List[CharacterData]) -> str:
        """
        Detect reading order (horizontal or vertical) based on character positions.
        
        Uses multiple heuristics:
        1. Character position variance (vertical vs horizontal spread)
        2. Line grouping analysis
        3. Character sequence direction
        """
        if len(characters) < 10:
            return "horizontal"
        
        # Sample characters for analysis
        sample_size = min(100, len(characters))
        sample = characters[:sample_size]
        
        # Heuristic 1: Position variance
        x_positions = [c.x for c in sample]
        y_positions = [c.y for c in sample]
        
        if not x_positions or not y_positions:
            return "horizontal"
        
        x_range = max(x_positions) - min(x_positions)
        y_range = max(y_positions) - min(y_positions)
        
        # Heuristic 2: Analyze character sequence direction
        # For vertical text, consecutive characters should have similar x but increasing y
        # For horizontal text, consecutive characters should have similar y but increasing x
        vertical_score = 0
        horizontal_score = 0
        
        for i in range(min(20, len(sample) - 1)):
            c1 = sample[i]
            c2 = sample[i + 1]
            
            x_diff = abs(c2.x - c1.x)
            y_diff = abs(c2.y - c1.y)
            
            if y_diff > x_diff * 2:  # Moving more vertically
                vertical_score += 1
            elif x_diff > y_diff * 2:  # Moving more horizontally
                horizontal_score += 1
        
        # Combine heuristics
        if y_range > x_range * 1.5 and vertical_score > horizontal_score:
            return "vertical"
        else:
            return "horizontal"
    
    def _sort_characters_by_reading_order(
        self,
        characters: List[CharacterData],
        reading_order: str
    ) -> List[CharacterData]:
        """
        Sort characters according to reading order.
        
        For vertical text: top-to-bottom, right-to-left
        For horizontal text: left-to-right, top-to-bottom
        """
        if reading_order == "vertical":
            # Group by columns (similar x), then sort by y within each column
            # Sort columns from right to left
            sorted_chars = sorted(
                characters,
                key=lambda c: (-c.x, c.y)  # Right to left, then top to bottom
            )
        else:
            # Group by rows (similar y), then sort by x within each row
            # Sort rows from top to bottom
            sorted_chars = sorted(
                characters,
                key=lambda c: (c.y, c.x)  # Top to bottom, then left to right
            )
        
        # Update indices after sorting
        for i, char in enumerate(sorted_chars):
            char.index = i
        
        return sorted_chars


def main():
    """Test the PDF text extractor."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_text_extractor.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    extractor = PDFTextExtractor()
    extractor.debug = True
    
    try:
        pages_data = extractor.extract_text_with_coordinates(
            pdf_path,
            page_range=(1, 5),  # Extract first 5 pages
            vertical_layout=False
        )
        
        print(f"\n=== Extraction Results ===")
        for page_data in pages_data:
            print(f"\nPage {page_data.page_number}:")
            print(f"  Characters: {len(page_data.characters)}")
            print(f"  Reading order: {page_data.reading_order}")
            print(f"  Dimensions: {page_data.page_width:.1f} x {page_data.page_height:.1f}")
            print(f"  Text preview: {page_data.full_text[:100]}...")
            
            if page_data.characters:
                first_char = page_data.characters[0]
                print(f"  First char: '{first_char.char}' at ({first_char.x:.1f}, {first_char.y:.1f})")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
