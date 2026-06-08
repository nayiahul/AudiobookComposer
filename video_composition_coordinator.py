#!/usr/bin/env python3
"""
Video Composition Coordinator

Coordinates the entire highlighted video generation process.
"""

from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
import os
import tempfile
from pdf_text_extractor import PDFTextExtractor
from subtitle_parser import SubtitleParser
from text_mapping_engine import TextMappingEngine
from highlight_renderer import HighlightRenderer, HighlightConfig


@dataclass
class VideoConfig:
    """Video generation configuration"""
    start_page: int = 1
    end_page: Optional[int] = None
    vertical_layout: bool = False
    odd_right_even_left: bool = False
    enable_crop: bool = False
    crop_settings: Optional[Dict] = None
    transition_effect: str = 'none'
    quality_preset: str = 'medium'
    target_bitrate: str = '1.5M'
    resolution: Optional[str] = None
    highlight_config: Optional[HighlightConfig] = None
    enable_highlight: bool = True


class VideoCompositionCoordinator:
    """
    Coordinates the highlighted video generation process.
    
    Workflow:
    1. Extract text from PDF with coordinates
    2. Parse subtitle file
    3. Map subtitles to PDF text
    4. Render highlighted frames
    5. Generate video (delegated to existing create_video module)
    """
    
    def __init__(self, progress_callback: Optional[Callable[[str, int], None]] = None):
        """
        Initialize coordinator.
        
        Args:
            progress_callback: Optional callback for progress updates (message, percentage)
        """
        self.progress_callback = progress_callback
        self.debug = False
        
        # Initialize modules
        self.pdf_extractor = PDFTextExtractor()
        self.subtitle_parser = SubtitleParser()
        self.text_mapper = TextMappingEngine()
        self.highlight_renderer = None  # Created with config
        
        # Statistics
        self.stats = {
            'total_pages': 0,
            'total_subtitles': 0,
            'mapped_subtitles': 0,
            'mapping_confidence_avg': 0.0
        }
    
    def create_highlighted_video(
        self,
        pdf_path: str,
        audio_path: str,
        subtitle_path: str,
        output_path: str,
        config: VideoConfig
    ) -> str:
        """
        Create highlighted video.
        
        Args:
            pdf_path: Path to PDF file
            audio_path: Path to audio file
            subtitle_path: Path to subtitle file
            output_path: Path for output video
            config: Video configuration
            
        Returns:
            Path to generated video
            
        Raises:
            RuntimeError: If generation fails
        """
        try:
            self._report_progress("Starting video generation...", 0)
            
            # Check if highlight is enabled
            if not config.enable_highlight:
                self._report_progress("Highlight disabled, using standard video generation", 5)
                # Delegate to standard video generation
                return self._create_standard_video(
                    pdf_path, audio_path, subtitle_path, output_path, config
                )
            
            # Step 1: Extract PDF text
            self._report_progress("Extracting text from PDF...", 10)
            pages_text = self._extract_pdf_text(pdf_path, config)
            self.stats['total_pages'] = len(pages_text)
            
            # Step 2: Parse subtitles
            self._report_progress("Parsing subtitles...", 20)
            subtitles = self._parse_subtitles(subtitle_path)
            self.stats['total_subtitles'] = len(subtitles)
            
            # Step 3: Map subtitles to text
            self._report_progress("Mapping subtitles to text...", 30)
            mappings = self._map_subtitles(subtitles, pages_text)
            self.stats['mapped_subtitles'] = len(mappings)
            
            if mappings:
                avg_conf = sum(m.confidence for m in mappings) / len(mappings)
                self.stats['mapping_confidence_avg'] = avg_conf
            
            # Step 4: Generate PDF images (will be done by create_video module)
            # Step 5: Render highlights (will be integrated)
            # Step 6: Create video (will be done by create_video module)
            
            self._report_progress("Preparation complete", 40)
            
            # Return mappings and config for integration with create_video
            # This will be used by the integration layer
            return {
                'pages_text': pages_text,
                'subtitles': subtitles,
                'mappings': mappings,
                'config': config,
                'stats': self.stats
            }
            
        except Exception as e:
            self._report_progress(f"Error: {str(e)}", 0)
            raise RuntimeError(f"Video generation failed: {str(e)}")
    
    def _extract_pdf_text(self, pdf_path: str, config: VideoConfig):
        """Extract text from PDF."""
        try:
            # Determine page range
            import fitz
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            doc.close()
            
            end_page = config.end_page if config.end_page else total_pages
            
            pages_text = self.pdf_extractor.extract_text_with_coordinates(
                pdf_path=pdf_path,
                page_range=(config.start_page, end_page),
                vertical_layout=config.vertical_layout,
                odd_right_even_left=config.odd_right_even_left
            )
            
            if self.debug:
                print(f"Extracted text from {len(pages_text)} pages")
                for page in pages_text:
                    print(f"  Page {page.page_number}: {len(page.characters)} chars")
            
            return pages_text
            
        except Exception as e:
            raise RuntimeError(f"PDF text extraction failed: {str(e)}")
    
    def _parse_subtitles(self, subtitle_path: str):
        """Parse subtitle file."""
        try:
            subtitles = self.subtitle_parser.parse_srt(subtitle_path)
            
            # Validate subtitles
            validation = self.subtitle_parser.validate_subtitles(subtitles)
            
            if not validation['valid']:
                print(f"Warning: Subtitle validation issues: {validation['issues']}")
            
            if validation.get('warnings'):
                print(f"Warning: {validation['warnings']}")
            
            if self.debug:
                print(f"Parsed {len(subtitles)} subtitle segments")
            
            return subtitles
            
        except Exception as e:
            raise RuntimeError(f"Subtitle parsing failed: {str(e)}")
    
    def _map_subtitles(self, subtitles, pages_text):
        """Map subtitles to PDF text."""
        try:
            mappings = self.text_mapper.map_subtitles_to_text(
                subtitles=subtitles,
                pages_text=pages_text,
                fuzzy_match=True
            )
            
            if self.debug:
                print(f"Mapped {len(mappings)}/{len(subtitles)} subtitles")
                if mappings:
                    avg_conf = sum(m.confidence for m in mappings) / len(mappings)
                    print(f"Average confidence: {avg_conf:.2f}")
            
            # Log unmapped subtitles
            mapped_indices = {m.subtitle.index for m in mappings}
            unmapped = [s for s in subtitles if s.index not in mapped_indices]
            
            if unmapped and self.debug:
                print(f"Warning: {len(unmapped)} subtitles could not be mapped")
                for s in unmapped[:5]:  # Show first 5
                    print(f"  [{s.index}] {s.text[:50]}...")
            
            return mappings
            
        except Exception as e:
            raise RuntimeError(f"Text mapping failed: {str(e)}")
    
    def _create_standard_video(
        self,
        pdf_path: str,
        audio_path: str,
        subtitle_path: str,
        output_path: str,
        config: VideoConfig
    ) -> str:
        """
        Create standard video without highlights.
        
        This is a fallback/degradation path.
        Will be implemented by delegating to existing create_video module.
        """
        # This will be implemented in the integration phase
        raise NotImplementedError(
            "Standard video generation will be implemented in integration phase"
        )
    
    def _report_progress(self, message: str, percentage: int):
        """Report progress to callback."""
        if self.progress_callback:
            self.progress_callback(message, percentage)
        elif self.debug:
            print(f"[{percentage}%] {message}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get generation statistics."""
        return self.stats.copy()


def main():
    """Test the coordinator."""
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python video_composition_coordinator.py <pdf> <audio> <subtitle>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    audio_path = sys.argv[2]
    subtitle_path = sys.argv[3]
    
    # Create coordinator
    coordinator = VideoCompositionCoordinator()
    coordinator.debug = True
    
    # Create config
    config = VideoConfig(
        start_page=1,
        end_page=5,
        enable_highlight=True,
        highlight_config=HighlightConfig()
    )
    
    try:
        print("=== Video Composition Coordinator Test ===\n")
        
        result = coordinator.create_highlighted_video(
            pdf_path=pdf_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            output_path="test_output.mp4",
            config=config
        )
        
        print("\n=== Statistics ===")
        stats = coordinator.get_statistics()
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        print("\n=== Result ===")
        print(f"Mappings: {len(result['mappings'])}")
        print(f"Pages: {len(result['pages_text'])}")
        print(f"Subtitles: {len(result['subtitles'])}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
