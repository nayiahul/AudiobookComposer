#!/usr/bin/env python3
"""
Highlight Renderer Engine

Renders highlight effects on PDF images based on subtitle timing.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw
import os
from text_mapping_engine import SubtitleMapping, Rect


@dataclass
class HighlightConfig:
    """Highlight rendering configuration"""
    color: Tuple[int, int, int, int] = (255, 255, 0, 100)  # RGBA yellow semi-transparent
    style: str = 'background'  # 'background', 'underline', 'box'
    padding: int = 2  # Pixels
    transition_duration: float = 0.1  # Seconds


class HighlightRenderer:
    """
    Renders highlight effects on images.
    
    Supports:
    - Multiple highlight styles
    - Vertical and horizontal text
    - Time-synchronized rendering
    - Performance optimization
    """
    
    def __init__(self, config: Optional[HighlightConfig] = None):
        self.config = config or HighlightConfig()
        self.debug = False
        self._image_cache = {}
    
    def render_highlight_frames(
        self,
        image_paths: List[str],
        mappings: List[SubtitleMapping],
        page_timings: List[float],
        output_dir: str
    ) -> List[str]:
        """
        Render highlighted video frames.
        
        Args:
            image_paths: List of PDF image paths
            mappings: List of subtitle mappings
            page_timings: Duration of each page in seconds
            output_dir: Output directory for highlighted images
            
        Returns:
            List of highlighted image paths
        """
        os.makedirs(output_dir, exist_ok=True)
        
        highlighted_paths = []
        current_time = 0.0
        
        for page_idx, (image_path, duration) in enumerate(zip(image_paths, page_timings)):
            page_number = page_idx + 1
            
            # Find mappings for this page
            page_mappings = [m for m in mappings if m.page_number == page_number]
            
            # Find active subtitles for this time range
            page_end_time = current_time + duration
            active_mappings = [
                m for m in page_mappings
                if m.subtitle.start_time < page_end_time and m.subtitle.end_time > current_time
            ]
            
            if active_mappings:
                # Render with highlights
                output_path = os.path.join(output_dir, f"highlighted_{page_idx:03d}.png")
                self._render_single_frame(image_path, active_mappings, output_path)
                highlighted_paths.append(output_path)
            else:
                # No highlights, use original
                highlighted_paths.append(image_path)
            
            current_time = page_end_time
        
        if self.debug:
            print(f"Rendered {len(highlighted_paths)} frames with highlights")
        
        return highlighted_paths
    
    def _render_single_frame(
        self,
        image_path: str,
        mappings: List[SubtitleMapping],
        output_path: str
    ):
        """Render a single frame with highlights."""
        # Load image
        img = Image.open(image_path).convert('RGBA')
        
        # Create overlay for highlights
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Draw highlights for each mapping
        for mapping in mappings:
            for rect in mapping.coordinates:
                self._draw_highlight(draw, rect, self.config)
        
        # Composite overlay onto image
        img = Image.alpha_composite(img, overlay)
        
        # Convert back to RGB and save
        img = img.convert('RGB')
        img.save(output_path, 'PNG')
    
    def _draw_highlight(
        self,
        draw: ImageDraw.ImageDraw,
        rect: Rect,
        config: HighlightConfig
    ):
        """Draw a single highlight rectangle."""
        # Apply padding
        x = rect.x - config.padding
        y = rect.y - config.padding
        width = rect.width + 2 * config.padding
        height = rect.height + 2 * config.padding
        
        if config.style == 'background':
            # Semi-transparent background
            draw.rectangle(
                [x, y, x + width, y + height],
                fill=config.color
            )
        elif config.style == 'underline':
            # Underline
            line_y = y + height
            draw.line(
                [x, line_y, x + width, line_y],
                fill=config.color[:3] + (255,),  # Full opacity for line
                width=2
            )
        elif config.style == 'box':
            # Box outline
            draw.rectangle(
                [x, y, x + width, y + height],
                outline=config.color[:3] + (255,),  # Full opacity for outline
                width=2
            )
    
    def render_time_synchronized_frames(
        self,
        image_paths: List[str],
        mappings: List[SubtitleMapping],
        page_timings: List[float],
        fps: int,
        output_dir: str
    ) -> List[str]:
        """
        Render frames with precise time synchronization.
        
        Generates one frame per time step based on FPS.
        
        Args:
            image_paths: List of PDF image paths
            mappings: List of subtitle mappings
            page_timings: Duration of each page
            fps: Frames per second
            output_dir: Output directory
            
        Returns:
            List of frame paths
        """
        os.makedirs(output_dir, exist_ok=True)
        
        frame_paths = []
        frame_duration = 1.0 / fps
        current_time = 0.0
        frame_idx = 0
        
        # Calculate total duration
        total_duration = sum(page_timings)
        
        # Build page time ranges
        page_times = []
        t = 0.0
        for duration in page_timings:
            page_times.append((t, t + duration))
            t += duration
        
        while current_time < total_duration:
            # Find current page
            page_idx = self._find_page_at_time(current_time, page_times)
            
            if page_idx < 0 or page_idx >= len(image_paths):
                break
            
            image_path = image_paths[page_idx]
            page_number = page_idx + 1
            
            # Find active subtitles at this time
            active_mappings = [
                m for m in mappings
                if m.page_number == page_number
                and m.subtitle.start_time <= current_time < m.subtitle.end_time
            ]
            
            # Render frame
            output_path = os.path.join(output_dir, f"frame_{frame_idx:06d}.png")
            
            if active_mappings:
                self._render_single_frame(image_path, active_mappings, output_path)
            else:
                # Copy original image
                img = Image.open(image_path)
                img.save(output_path, 'PNG')
            
            frame_paths.append(output_path)
            
            current_time += frame_duration
            frame_idx += 1
        
        if self.debug:
            print(f"Rendered {len(frame_paths)} time-synchronized frames")
        
        return frame_paths
    
    def _find_page_at_time(
        self,
        time: float,
        page_times: List[Tuple[float, float]]
    ) -> int:
        """Find which page is active at given time."""
        for idx, (start, end) in enumerate(page_times):
            if start <= time < end:
                return idx
        return len(page_times) - 1  # Last page
    
    def clear_cache(self):
        """Clear image cache."""
        self._image_cache.clear()


def main():
    """Test the highlight renderer."""
    print("Highlight Renderer - Test Mode")
    print("This module requires image and mapping data to test.")
    
    # Create test config
    config = HighlightConfig(
        color=(255, 255, 0, 100),
        style='background',
        padding=3
    )
    
    print(f"Config: color={config.color}, style={config.style}, padding={config.padding}")


if __name__ == "__main__":
    main()
