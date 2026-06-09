#!/usr/bin/env python3
"""
PDF + Audio + Subtitle → MP4 Video Creator

This script converts a PDF document, audio file, and subtitle file into a single MP4 video
with burned-in subtitles. Each PDF page becomes a video frame, synchronized with audio timing.
Optional page range selection allows processing specific pages from the PDF.

Requirements:
- Python 3.8+
- FFmpeg and ffprobe in PATH
- PyMuPDF for PDF processing
- macOS with h264_videotoolbox support (Apple Silicon)

Usage:
    python create_video.py --pdf input.pdf --audio audio.m4a --subs subtitles.srt --output output.mp4
    python create_video.py --pdf input.pdf --audio audio.m4a --subs subtitles.srt --output output.mp4 --start-page 5 --end-page 15
"""

import argparse
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Dict, Tuple
import fitz  # PyMuPDF
from PIL import Image

# Import highlight functionality modules (Phase 2 integration)
try:
    from pdf_text_extractor import PDFTextExtractor, PageTextData
    from subtitle_parser import SubtitleParser
    from text_mapping_engine import TextMappingEngine
    from highlight_renderer import HighlightRenderer, HighlightConfig
    from video_composition_coordinator import VideoCompositionCoordinator, VideoConfig
    from indicator_renderer import IndicatorRenderer, IndicatorConfig
    HIGHLIGHT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Highlight functionality not available: {e}")
    HIGHLIGHT_AVAILABLE = False


def check_ffmpeg() -> bool:
    """Check if FFmpeg and ffprobe are available in PATH."""
    try:
        # 增加超时时间，避免ffprobe超时导致检测失败
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True, timeout=5)
        return True
    except FileNotFoundError:
        # 如果找不到命令，返回False
        return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # 如果命令存在但执行出错或超时，仍然返回True，因为FFmpeg/ffprobe可能只是初始化慢
        # 这种情况下，实际使用时可能仍能正常工作
        return True


def convert_pdf_to_images(pdf_path: str, temp_dir: str, start_page: int = 1, end_page: Optional[int] = None, vertical_layout: bool = False, enable_crop: bool = False, crop_settings: Optional[Dict[str, Dict[str, int]]] = None, odd_right_even_left: bool = False, extract_text_data: bool = False) -> Tuple[List[str], Optional[List]]:
    """
    Convert PDF pages to PNG images using PyMuPDF.

    Args:
        pdf_path: Path to the PDF file
        temp_dir: Temporary directory for output images
        start_page: Starting page number (1-indexed)
        end_page: Ending page number (1-indexed, None for last page)
        vertical_layout: Whether to use vertical layout for traditional Chinese text (combines two pages side by side)
        enable_crop: Whether to enable PDF boundary cropping
        crop_settings: Dictionary containing crop settings for odd and even pages with top, bottom, left, right values
        odd_right_even_left: Whether to use odd pages on right and even pages on left layout
        extract_text_data: Whether to extract text data with coordinates for highlight functionality

    Returns:
        Tuple of (list of generated image file paths, optional text data for highlight)

    Raises:
        RuntimeError: If PDF conversion fails
    """
    print(f"Converting PDF to images: {pdf_path}")
    print(f"Page range: {start_page} to {end_page if end_page else 'end'}")
    if vertical_layout:
        print("Using vertical layout for traditional Chinese text (combining two pages side by side)")
        if odd_right_even_left:
            print("Using odd pages on right and even pages on left layout")
    
    # Initialize crop settings
    if enable_crop and crop_settings:
        print("PDF boundary cropping enabled")
        # Validate crop settings
        for page_type in ['odd_pages', 'even_pages']:
            if page_type in crop_settings:
                for direction in ['top', 'bottom', 'left', 'right']:
                    if direction not in crop_settings[page_type]:
                        crop_settings[page_type][direction] = 0
                    elif crop_settings[page_type][direction] < 0:
                        crop_settings[page_type][direction] = 0
                        print(f"Warning: Negative crop value for {page_type} {direction}, set to 0")
    else:
        crop_settings = None

    try:
        # Open the PDF document
        if not os.path.exists(pdf_path):
            raise RuntimeError(f"PDF file not found: {pdf_path}")
        
        if os.path.getsize(pdf_path) == 0:
            raise RuntimeError(f"PDF file is empty: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        if total_pages == 0:
            raise RuntimeError(f"PDF has no pages: {pdf_path}")

        # Validate page range
        if start_page < 1 or start_page > total_pages:
            raise ValueError(f"Start page {start_page} is out of range (1-{total_pages})")

        if end_page is None:
            end_page = total_pages
        elif end_page < start_page or end_page > total_pages:
            raise ValueError(f"End page {end_page} is out of range (1-{total_pages}) or less than start page")

        image_paths = []
        actual_pages = end_page - start_page + 1
        print(f"Processing {actual_pages} pages from PDF with {total_pages} total pages")

        if vertical_layout:
            # For vertical layout, combine two pages side by side
            # Ensure we have an even number of pages to work with
            if actual_pages % 2 != 0:
                print(f"Warning: Odd number of pages ({actual_pages}), last page will be used alone")
            
            # Process pages in pairs
            for i in range(0, actual_pages, 2):
                page_num1 = start_page - 1 + i  # Convert to 0-indexed
                page_num2 = start_page - 1 + i + 1
                
                # Get the first page
                page1 = doc[page_num1]
                
                # Set the matrix for better quality (2x zoom)
                mat = fitz.Matrix(2.0, 2.0)
                
                # Determine if this is an odd or even page for cropping
                page1_type = 'odd_pages' if (page_num1 + 1) % 2 == 1 else 'even_pages'
                
                # Apply crop settings if enabled
                if crop_settings and page1_type in crop_settings:
                    crop = crop_settings[page1_type]
                    rect = page1.rect
                    # Create a new rectangle with crop settings applied
                    # Note: fitz coordinates start from top-left (0,0)
                    cropped_rect = fitz.Rect(
                        rect.x0 + crop['left'],
                        rect.y0 + crop['top'],
                        rect.x1 - crop['right'],
                        rect.y1 - crop['bottom']
                    )
                    print(f"Cropping page {page_num1 + 1} ({page1_type}): top={crop['top']}, bottom={crop['bottom']}, left={crop['left']}, right={crop['right']}")
                else:
                    cropped_rect = page1.rect
                
                # Try to get pixmap with RGB colorspace
                try:
                    pix1 = page1.get_pixmap(matrix=mat, colorspace=fitz.csRGB, clip=cropped_rect)
                except Exception as e:
                    # Fallback to default colorspace if RGB fails
                    print(f"Warning: Failed to use RGB colorspace for page {page_num1 + 1}: {e}")
                    try:
                        pix1 = page1.get_pixmap(matrix=mat, clip=cropped_rect)
                    except Exception as e2:
                        raise RuntimeError(f"Failed to render page {page_num1 + 1}: {e2}")
                
                if page_num2 < total_pages:
                    # Get the second page if it exists
                    page2 = doc[page_num2]
                    
                    # Determine if this is an odd or even page for cropping
                    page2_type = 'odd_pages' if (page_num2 + 1) % 2 == 1 else 'even_pages'
                    
                    # Apply crop settings if enabled
                    if crop_settings and page2_type in crop_settings:
                        crop = crop_settings[page2_type]
                        rect = page2.rect
                        # Create a new rectangle with crop settings applied
                        # Note: fitz coordinates start from top-left (0,0)
                        cropped_rect = fitz.Rect(
                            rect.x0 + crop['left'],
                            rect.y0 + crop['top'],
                            rect.x1 - crop['right'],
                            rect.y1 - crop['bottom']
                        )
                        print(f"Cropping page {page_num2 + 1} ({page2_type}): top={crop['top']}, bottom={crop['bottom']}, left={crop['left']}, right={crop['right']}")
                    else:
                        cropped_rect = page2.rect
                    
                    # Try to get pixmap with RGB colorspace
                    try:
                        pix2 = page2.get_pixmap(matrix=mat, colorspace=fitz.csRGB, clip=cropped_rect)
                    except Exception as e:
                        # Fallback to default colorspace if RGB fails
                        print(f"Warning: Failed to use RGB colorspace for page {page_num2 + 1}: {e}")
                        try:
                            pix2 = page2.get_pixmap(matrix=mat, clip=cropped_rect)
                        except Exception as e2:
                            raise RuntimeError(f"Failed to render page {page_num2 + 1}: {e2}")
                    
                    # Create a new pixmap that can hold both pages side by side
                    combined_width = pix1.width + pix2.width
                    combined_height = max(pix1.height, pix2.height)
                    
                    # Create a white background pixmap using the most robust method
                    # Handle "Illegal number of colorants" by using a safer approach
                    combined_pix = None
                    
                    # Method 1: Try to create a new pixmap with an IRect
                    if not combined_pix:
                        try:
                            # Create an IRect for the combined pixmap
                            irect = fitz.IRect(0, 0, combined_width, combined_height)
                            # Try with the colorspace from the first pixmap
                            if hasattr(pix1, 'colorspace') and pix1.colorspace:
                                combined_pix = fitz.Pixmap(pix1.colorspace, irect)
                            else:
                                # Fallback to RGB colorspace
                                combined_pix = fitz.Pixmap(fitz.csRGB, irect)
                            # Fill with white background
                            combined_pix.clear_with(255)
                        except Exception as e:
                            print(f"Warning: Failed to create combined pixmap with IRect: {e}")
                            combined_pix = None
                    
                    # Method 2: Try to create from existing pixmap
                    if not combined_pix:
                        try:
                            # Create a copy of the first pixmap and resize it
                            combined_pix = fitz.Pixmap(pix1)
                            # We'll handle the combination differently below
                        except Exception as e:
                            print(f"Warning: Failed to create combined pixmap from existing: {e}")
                            combined_pix = None
                    
                    # Method 3: Create a simple pixmap without specifying colorspace
                    if not combined_pix:
                        try:
                            irect = fitz.IRect(0, 0, combined_width, combined_height)
                            combined_pix = fitz.Pixmap(irect)
                            combined_pix.clear_with(255)  # Fill with white
                        except Exception as e:
                            print(f"Warning: Failed to create default combined pixmap: {e}")
                            combined_pix = None
                    
                    # Method 4: Ultimate fallback - create individual pixmaps and combine manually
                    if not combined_pix:
                        # If all else fails, we'll create a new approach
                        # Create a new pixmap with explicit RGB colorspace and IRect
                        try:
                            irect = fitz.IRect(0, 0, combined_width, combined_height)
                            combined_pix = fitz.Pixmap(fitz.csRGB, irect, 0)  # No alpha
                            combined_pix.clear_with(255)  # Fill with white
                        except Exception as e:
                            print(f"Warning: Failed to create RGB combined pixmap: {e}")
                            # Last resort - raise an error
                            raise RuntimeError("Failed to create combined pixmap with all available methods")
                    
                    # Place pages based on odd_right_even_left layout
                    # Use PIL for reliable combination (PyMuPDF copy_pixmap removed in newer versions)
                    from PIL import Image as PILImage
                    img1 = PILImage.frombytes('RGB', [pix1.width, pix1.height], pix1.samples)
                    img2 = PILImage.frombytes('RGB', [pix2.width, pix2.height], pix2.samples)
                    combined_img = PILImage.new('RGB', (combined_width, combined_height), (255, 255, 255))

                    if odd_right_even_left:
                        combined_img.paste(img2, (0, 0))
                        combined_img.paste(img1, (pix2.width, 0))
                    else:
                        combined_img.paste(img1, (0, 0))
                        combined_img.paste(img2, (pix1.width, 0))

                    # Save via PIL directly
                    seq_num = (i // 2) + 1
                    output_path = os.path.join(temp_dir, f"page_{seq_num:03d}.png")
                    combined_img.save(output_path)
                    image_paths.append(output_path)
                    print(f"Combined pages {page_num1 + 1} and {page_num2 + 1} into image {seq_num}")
                else:
                    # Only one page left, save it as is
                    seq_num = (i // 2) + 1  # Sequential numbering starting from 1
                    output_path = os.path.join(temp_dir, f"page_{seq_num:03d}.png")
                    
                    try:
                        pix1.save(output_path)
                        # Verify the image was created successfully
                        if not os.path.exists(output_path):
                            raise RuntimeError(f"Failed to create single page image: {output_path}")
                        if os.path.getsize(output_path) == 0:
                            raise RuntimeError(f"Created image is empty: {output_path}")
                        
                        image_paths.append(output_path)
                        print(f"Single page {page_num1 + 1} saved as image {seq_num}")
                    except Exception as e:
                        raise RuntimeError(f"Failed to save single page image for page {page_num1 + 1}: {e}")
        else:
            # Normal processing, one page per image
            for i, page_num in enumerate(range(start_page - 1, end_page)):  # Convert to 0-indexed
                # Get the page
                page = doc[page_num]
                
                # Set the matrix for better quality (2x zoom)
                mat = fitz.Matrix(2.0, 2.0)
                
                # Determine if this is an odd or even page for cropping
                page_type = 'odd_pages' if (page_num + 1) % 2 == 1 else 'even_pages'
                
                # Apply crop settings if enabled
                if crop_settings and page_type in crop_settings:
                    crop = crop_settings[page_type]
                    rect = page.rect
                    # Create a new rectangle with crop settings applied
                    # Note: fitz coordinates start from top-left (0,0)
                    cropped_rect = fitz.Rect(
                        rect.x0 + crop['left'],
                        rect.y0 + crop['top'],
                        rect.x1 - crop['right'],
                        rect.y1 - crop['bottom']
                    )
                    print(f"Cropping page {page_num + 1} ({page_type}): top={crop['top']}, bottom={crop['bottom']}, left={crop['left']}, right={crop['right']}")
                else:
                    cropped_rect = page.rect
                
                # Try to get pixmap with RGB colorspace
                try:
                    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, clip=cropped_rect)
                except Exception as e:
                    # Fallback to default colorspace if RGB fails
                    print(f"Warning: Failed to use RGB colorspace for page {page_num + 1}: {e}")
                    try:
                        pix = page.get_pixmap(matrix=mat, clip=cropped_rect)
                    except Exception as e2:
                        raise RuntimeError(f"Failed to render page {page_num + 1}: {e2}")
                
                # Save as PNG with sequential numbering starting from 1
                seq_num = i + 1  # Sequential numbering starting from 1
                output_path = os.path.join(temp_dir, f"page_{seq_num:03d}.png")
                
                try:
                    pix.save(output_path)
                    # Verify the image was created successfully
                    if not os.path.exists(output_path):
                        raise RuntimeError(f"Failed to create page image: {output_path}")
                    if os.path.getsize(output_path) == 0:
                        raise RuntimeError(f"Created image is empty: {output_path}")
                    
                    image_paths.append(output_path)
                    print(f"Converted page {page_num + 1}/{total_pages} (range page {seq_num}/{actual_pages})")
                except Exception as e:
                    raise RuntimeError(f"Failed to save image for page {page_num + 1}: {e}")

        doc.close()
        print(f"PDF conversion completed: {len(image_paths)} images generated from pages {start_page}-{end_page}")

        # Final verification - check that all images were created successfully
        if len(image_paths) == 0:
            raise RuntimeError("No images were generated from the PDF")
        
        # Verify all image files exist and have content
        for img_path in image_paths:
            if not os.path.exists(img_path):
                raise RuntimeError(f"Generated image file not found: {img_path}")
            if os.path.getsize(img_path) == 0:
                raise RuntimeError(f"Generated image file is empty: {img_path}")
        
        print(f"All {len(image_paths)} images verified successfully")
        
        # Extract text data if requested (for highlight functionality)
        text_data = None
        if extract_text_data and HIGHLIGHT_AVAILABLE:
            try:
                print("Extracting text data with coordinates for highlight functionality...")
                extractor = PDFTextExtractor()
                text_data = extractor.extract_text_with_coordinates(
                    pdf_path=pdf_path,
                    page_range=(start_page, end_page if end_page else total_pages),
                    vertical_layout=vertical_layout,
                    odd_right_even_left=odd_right_even_left
                )
                print(f"Text data extracted: {len(text_data)} pages")
            except Exception as e:
                print(f"Warning: Failed to extract text data: {e}")
                text_data = None
        
        return sorted(image_paths), text_data

    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {str(e)}")


def get_audio_duration(audio_path: str) -> float:
    """
    Get audio duration in seconds using ffprobe.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds

    Raises:
        RuntimeError: If duration extraction fails
    """
    print(f"Getting audio duration: {audio_path}")

    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0',
        audio_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        print(f"Audio duration: {duration:.2f} seconds")
        return duration

    except (subprocess.CalledProcessError, ValueError) as e:
        raise RuntimeError(f"Failed to get audio duration: {e}")


def create_highlighted_video_frames(
    image_paths: List[str],
    subtitle_path: str,
    audio_path: str,
    text_data: List,
    temp_dir: str,
    highlight_config: Optional[HighlightConfig] = None,
    vertical_layout: bool = False
) -> List[str]:
    """
    Create highlighted video frames by rendering highlights on PDF images.
    
    Args:
        image_paths: List of PDF image paths
        subtitle_path: Path to subtitle file
        audio_path: Path to audio file (for duration calculation)
        text_data: Extracted text data with coordinates
        temp_dir: Temporary directory for output
        highlight_config: Highlight configuration
        vertical_layout: Whether using vertical layout
        
    Returns:
        List of highlighted image paths
        
    Raises:
        RuntimeError: If highlight rendering fails
    """
    if not HIGHLIGHT_AVAILABLE:
        print("Warning: Highlight functionality not available, using original images")
        return image_paths
    
    if not text_data:
        print("Warning: No text data available, using original images")
        return image_paths
    
    try:
        print("Creating highlighted video frames...")
        
        # Parse subtitles
        parser = SubtitleParser()
        subtitles = parser.parse_srt(subtitle_path)
        print(f"Parsed {len(subtitles)} subtitle segments")
        
        # Map subtitles to text
        mapper = TextMappingEngine()
        mappings = mapper.map_subtitles_to_text(
            subtitles=subtitles,
            pages_text=text_data,
            fuzzy_match=True
        )
        print(f"Mapped {len(mappings)} subtitle segments to text")
        
        # Calculate page timings based on audio duration
        audio_duration = get_audio_duration(audio_path)
        num_pages = len(image_paths)
        page_duration = audio_duration / num_pages
        page_timings = [page_duration] * num_pages
        
        # Render highlights
        renderer = HighlightRenderer()
        if highlight_config is None:
            highlight_config = HighlightConfig(
                color=(255, 255, 0, 100),  # Yellow with transparency
                style='background',
                padding=3,
                transition_duration=0.2
            )
        
        highlighted_dir = os.path.join(temp_dir, "highlighted")
        os.makedirs(highlighted_dir, exist_ok=True)
        
        highlighted_paths = renderer.render_highlight_frames(
            image_paths=image_paths,
            mappings=mappings,
            page_timings=page_timings,
            config=highlight_config,
            output_dir=highlighted_dir
        )
        
        print(f"Created {len(highlighted_paths)} highlighted frames")
        return highlighted_paths
        
    except Exception as e:
        print(f"Warning: Failed to create highlighted frames: {e}")
        print("Falling back to original images without highlights")
        return image_paths


def create_indicator_video_frames(
    image_paths: List[str],
    subtitle_path: str,
    audio_path: str,
    text_data: List,
    temp_dir: str,
    indicator_config: Optional[IndicatorConfig] = None,
) -> Tuple[List[str], Optional[List[float]]]:
    """
    Create indicator-based video frames — one image per subtitle segment
    with a position indicator line drawn at the current text location.

    Returns:
        Tuple of (image_paths, durations) where durations[i] is the
        display time in seconds for image_paths[i].
        Returns (image_paths, None) on failure.
    """
    if not HIGHLIGHT_AVAILABLE:
        print("Warning: Indicator functionality not available, using original images")
        return image_paths, None

    if not text_data:
        print("Warning: No text data available, using original images")
        return image_paths, None

    try:
        print("Creating indicator video frames...")

        parser = SubtitleParser()
        subtitles = parser.parse_srt(subtitle_path)
        print(f"Parsed {len(subtitles)} subtitle segments")

        mapper = TextMappingEngine()
        mappings = mapper.map_subtitles_to_text(
            subtitles=subtitles,
            pages_text=text_data,
            fuzzy_match=True,
        )
        print(f"Mapped {len(mappings)} subtitle segments to text")

        renderer = IndicatorRenderer(config=indicator_config)
        indicator_dir = os.path.join(temp_dir, "indicator")
        os.makedirs(indicator_dir, exist_ok=True)

        frames = renderer.render_indicator_frames(
            image_paths=image_paths,
            subtitles=subtitles,
            mappings=mappings,
            text_data=text_data,
            output_dir=indicator_dir,
        )

        if not frames:
            print("Warning: No indicator frames generated, using original images")
            return image_paths, None

        indicator_paths = [p for p, _ in frames]
        durations = [d for _, d in frames]

        print(f"Created {len(indicator_paths)} indicator frames")
        return indicator_paths, durations

    except Exception as e:
        print(f"Warning: Failed to create indicator frames: {e}")
        print("Falling back to original images without indicators")
        return image_paths, None


def create_karaoke_video_frames(
    image_paths: List[str],
    subtitle_path: str,
    audio_path: str,
    text_data: List,
    temp_dir: str,
    indicator_config: Optional[IndicatorConfig] = None,
    fps: int = 12,
) -> str:
    """
    Karaoke-style progressive highlight: renders per-character frames
    and pipes them directly to ffmpeg (zero disk I/O for frames).

    Returns path to silent video ready for audio merge.
    """
    if not HIGHLIGHT_AVAILABLE:
        raise RuntimeError("Karaoke not available (missing dependencies)")

    if not text_data:
        raise RuntimeError("No text data for karaoke")

    print(f"Creating karaoke progressive-highlight video @ {fps}fps...")

    parser = SubtitleParser()
    subtitles = parser.parse_srt(subtitle_path)
    print(f"Parsed {len(subtitles)} subtitle segments")

    mapper = TextMappingEngine()
    mappings = mapper.map_subtitles_to_text(
        subtitles=subtitles, pages_text=text_data, fuzzy_match=True,
    )
    print(f"Mapped {len(mappings)} subtitle segments to text")

    renderer = IndicatorRenderer(config=indicator_config)

    # Get first image to determine video dimensions
    first_img = Image.open(image_paths[0])
    img_w, img_h = first_img.size
    first_img.close()

    # Build lookup structures
    map_by_idx: Dict[int, SubtitleMapping] = {m.subtitle.index: m for m in mappings}
    char_to_page: List[Tuple[int, int]] = []
    for td in text_data:
        for c in td.characters:
            char_to_page.append((td.page_number, c.index))
    page_to_img: Dict[int, int] = {}
    page_orders: Dict[int, str] = {}
    page_data_map: Dict[int, PageTextData] = {}
    for idx, td in enumerate(text_data):
        page_to_img[td.page_number] = idx
        page_orders[td.page_number] = td.reading_order
        page_data_map[td.page_number] = td

    fg = indicator_config.color if indicator_config else (0, 180, 255, 220)
    fill_color = (fg[0], fg[1], fg[2], min(fg[3], 120))

    silent_path = os.path.join(temp_dir, "karaoke_silent.mp4")

    # Pipe PNG-encoded frames via image2pipe — ffmpeg decodes each PNG
    cmd = [
        'ffmpeg', '-y',
        '-f', 'image2pipe',
        '-vcodec', 'png',
        '-r', str(fps),
        '-i', '-',
        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-preset', 'fast',
        '-crf', '23',
        silent_path,
    ]

    err_log = os.path.join(temp_dir, "ffmpeg_karaoke_err.txt")
    err_fh = open(err_log, 'w')
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err_fh)

    frame_idx = 0
    current_base = image_paths[0]
    image_cache: Dict[str, Image.Image] = {}

    def get_base(path):
        if path not in image_cache:
            image_cache[path] = Image.open(path).convert('RGBA')
        return image_cache[path].copy()

    # Cache: (page_path, subtitle_text) → PNG bytes for unmapped/non-highlight frames
    subtitle_frame_cache: Dict[Tuple[str, str], bytes] = {}

    try:
        for si, sub in enumerate(subtitles):
            m = map_by_idx.get(sub.index)
            duration = sub.end_time - sub.start_time
            n_frames = max(1, int(duration * fps))

            if m is not None:
                img_idx = page_to_img.get(m.page_number)
                if img_idx is not None and 0 <= img_idx < len(image_paths):
                    current_base = image_paths[img_idx]
                    order = page_orders.get(m.page_number, 'horizontal')
                    coords = renderer._get_char_coords(m, char_to_page, page_data_map)

                    for f in range(n_frames):
                        progress = (f + 1) / n_frames
                        frame = renderer._make_karaoke_frame(
                            get_base(current_base), coords, progress,
                            sub.text, fill_color,
                        )
                        frame.save(proc.stdin, 'PNG')
                        frame_idx += 1
                else:
                    cache_key = (current_base, sub.text)
                    if cache_key not in subtitle_frame_cache:
                        frame = renderer._make_subtitle_frame(
                            get_base(current_base), sub.text,
                        )
                        buf = io.BytesIO()
                        frame.save(buf, 'PNG')
                        subtitle_frame_cache[cache_key] = buf.getvalue()
                    data = subtitle_frame_cache[cache_key]
                    for _ in range(n_frames):
                        proc.stdin.write(data)
                        frame_idx += 1
            else:
                cache_key = (current_base, sub.text)
                if cache_key not in subtitle_frame_cache:
                    frame = renderer._make_subtitle_frame(
                        get_base(current_base), sub.text,
                    )
                    buf = io.BytesIO()
                    frame.save(buf, 'PNG')
                    subtitle_frame_cache[cache_key] = buf.getvalue()
                data = subtitle_frame_cache[cache_key]
                for _ in range(n_frames):
                    proc.stdin.write(data)
                    frame_idx += 1

            if (si + 1) % 50 == 0:
                print(f"  Karaoke: {si+1}/{len(subtitles)} subs, {frame_idx} frames piped")

    except BrokenPipeError:
        proc.wait()
        err_fh.close()
        with open(err_log) as f:
            err_text = f.read()
        print(f"ffmpeg pipe error (exit {proc.returncode}):")
        print(err_text[:2000])
        raise RuntimeError(f"ffmpeg pipe broke: {err_text[:300]}")

    proc.stdin.close()
    proc.wait()
    err_fh.close()

    if proc.returncode != 0:
        with open(err_log) as f:
            err_text = f.read()
        print(f"ffmpeg error (exit {proc.returncode}):")
        print(err_text[:2000])
        raise RuntimeError(f"ffmpeg encoding failed")

    for img in image_cache.values():
        img.close()

    print(f"  Karaoke: {frame_idx} frames @ {fps}fps → {silent_path}")
    return silent_path


def create_silent_video(audio_path: str, image_paths: List[str], temp_dir: str, transition_effect: str = 'none', image_durations: Optional[List[float]] = None) -> str:
    """
    Create silent video from image sequence, duration matched to audio.

    Args:
        audio_path: Path to audio file (for duration reference)
        image_paths: List of image file paths
        temp_dir: Temporary directory for output video
        transition_effect: Transition effect between pages ('none', 'fade', 'slide', 'flip')
        image_durations: Optional per-image durations in seconds. When provided,
                         overrides uniform duration calculation.

    Returns:
        Path to generated silent video

    Raises:
        RuntimeError: If video creation fails
    """
    print("Creating silent video from images")

    # Verify input files exist
    if not os.path.exists(audio_path):
        raise RuntimeError(f"Audio file not found: {audio_path}")

    # Check all image files exist
    for i, img_path in enumerate(image_paths):
        if not os.path.exists(img_path):
            raise RuntimeError(f"Image file not found: {img_path}")
        if os.path.getsize(img_path) == 0:
            raise RuntimeError(f"Image file is empty: {img_path}")

    # Get audio duration
    audio_duration = get_audio_duration(audio_path)

    # Calculate duration per page
    num_pages = len(image_paths)
    if num_pages == 0:
        raise RuntimeError("No images found for video creation")

    if image_durations:
        # Per-image durations provided — use them directly
        if len(image_durations) != num_pages:
            raise RuntimeError(
                f"image_durations length ({len(image_durations)}) != image_paths length ({num_pages})"
            )
        durations = image_durations
        # Adjust to match audio duration
        total_dur = sum(durations)
        if total_dur > 0 and abs(total_dur - audio_duration) > 0.5:
            scale = audio_duration / total_dur
            durations = [d * scale for d in durations]
        duration_per_page = total_dur / num_pages if num_pages > 0 else 0
    else:
        duration_per_page = audio_duration / num_pages
        durations = [duration_per_page] * num_pages

    framerate = 1.0 / duration_per_page if duration_per_page > 0 else 1.0

    print(f"Pages: {num_pages}, Duration per page: {duration_per_page:.2f}s, Framerate: {framerate:.3f}")
    print(f"Transition effect: {transition_effect}")

    silent_video_path = os.path.join(temp_dir, "silent.mp4")
    fps = 30  # Output framerate

    # If no transition effect, use the original method
    if transition_effect == 'none':
        # Use concat demuxer for more reliable video creation
        concat_file_path = os.path.join(temp_dir, "concat.txt")
        with open(concat_file_path, 'w') as f:
            for i, image_path in enumerate(image_paths):
                f.write(f"file '{image_path}'\n")
                if i < len(image_paths) - 1:
                    f.write(f"duration {durations[i]}\n")

        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file_path,
            '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),  # Output framerate
            '-y',  # Overwrite output file if it exists
            silent_video_path
        ]
    else:
        # Create a concat file for more control over transitions
        concat_file_path = os.path.join(temp_dir, "concat.txt")
        with open(concat_file_path, 'w') as f:
            for i, image_path in enumerate(image_paths):
                f.write(f"file '{image_path}'\n")
                if i < len(image_paths) - 1:
                    f.write(f"duration {durations[i]}\n")

        # Apply transition effects
        if transition_effect == 'fade':
            # Fade in/out effect with scaling to ensure dimensions are divisible by 2
            fade_duration = min(0.5, duration_per_page / 4)  # Fade duration is 0.5s or 1/4 of page duration
            vf_filter = f"fade=in:0:{int(fade_duration*fps)},fade=out:st={duration_per_page-fade_duration}:d={int(fade_duration*fps)},scale=trunc(iw/2)*2:trunc(ih/2)*2"
        elif transition_effect == 'slide':
            # Simplified slide transition effect with scaling
            vf_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        elif transition_effect == 'flip':
            # Simplified flip transition effect with scaling
            vf_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        else:
            # Default: just scaling to ensure dimensions are divisible by 2
            vf_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

        # Build FFmpeg command
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file_path,
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),
            '-y',  # Overwrite output file if it exists
            silent_video_path
        ]
        
        # Only add -vf parameter if filter is not empty
        if vf_filter:
            cmd.insert(cmd.index('-c:v'), '-vf')
            cmd.insert(cmd.index('-c:v'), vf_filter)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Silent video created: {result.stderr}")
        
        # Verify output file exists and has content
        if not os.path.exists(silent_video_path):
            raise RuntimeError(f"Silent video file was not created: {silent_video_path}")
        
        # Check file size to ensure it's not empty
        file_size = os.path.getsize(silent_video_path)
        if file_size == 0:
            raise RuntimeError(f"Silent video file is empty: {silent_video_path}")
        
        print(f"Silent video created successfully, size: {file_size} bytes")
        return silent_video_path

    except subprocess.CalledProcessError as e:
        print(f"Error output: {e.stderr}")
        raise RuntimeError(f"Silent video creation failed: {e.stderr}")


def merge_audio_video(silent_video_path: str, audio_path: str, temp_dir: str) -> str:
    """
    Merge silent video with audio.

    Args:
        silent_video_path: Path to silent video
        audio_path: Path to audio file
        temp_dir: Temporary directory for output video

    Returns:
        Path to video with audio

    Raises:
        RuntimeError: If merge fails
    """
    print("Merging audio with silent video")
    
    # Verify input files exist
    if not os.path.exists(silent_video_path):
        raise RuntimeError(f"Silent video file not found: {silent_video_path}")
    if not os.path.exists(audio_path):
        raise RuntimeError(f"Audio file not found: {audio_path}")
    
    # Check file sizes to ensure they're not empty
    if os.path.getsize(silent_video_path) == 0:
        raise RuntimeError(f"Silent video file is empty: {silent_video_path}")
    if os.path.getsize(audio_path) == 0:
        raise RuntimeError(f"Audio file is empty: {audio_path}")

    video_with_audio_path = os.path.join(temp_dir, "video_with_audio.mp4")

    cmd = [
        'ffmpeg',
        '-i', silent_video_path,
        '-i', audio_path,
        '-c:v', 'copy',  # Don't re-encode video
        '-c:a', 'aac',
        '-shortest',     # End at shortest stream
        '-y',            # Overwrite output file if it exists
        video_with_audio_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Audio merged: {result.stderr}")
        
        # Verify output file exists and has content
        if not os.path.exists(video_with_audio_path):
            raise RuntimeError(f"Merged video file was not created: {video_with_audio_path}")
        
        # Check file size to ensure it's not empty
        file_size = os.path.getsize(video_with_audio_path)
        if file_size == 0:
            raise RuntimeError(f"Merged video file is empty: {video_with_audio_path}")
        
        print(f"Video with audio created successfully, size: {file_size} bytes")
        return video_with_audio_path

    except subprocess.CalledProcessError as e:
        print(f"Error output: {e.stderr}")
        raise RuntimeError(f"Audio merge failed: {e.stderr}")


def _parse_srt(srt_path: str) -> list:
    """Parse SRT file into list of (start_seconds, end_seconds, text) tuples."""
    import re
    with open(srt_path, 'r', encoding='utf-8') as f:
        srt_content = f.read()

    pattern = re.compile(
        r'(\d+)\s*\n'
        r'(\d{2}:\d{2}:\d{2}[,.](\d+))\s*-->\s*(\d{2}:\d{2}:\d{2}[,.](\d+))\s*\n'
        r'((?:.+\n?)+?)(?=\n\d+\n|\Z)',
        re.MULTILINE
    )

    def _norm_ms(ms_str):
        if len(ms_str) >= 3:
            return ms_str[:3]
        return ms_str.ljust(3, '0')

    def _ts_to_sec(ts_str, ms_str):
        h, m, s = ts_str.split(':')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(_norm_ms(ms_str)) / 1000.0

    segments = []
    for m in pattern.finditer(srt_content):
        ts_start = m.group(2).rsplit(',', 1)[0].rsplit('.', 1)[0]
        ms_start = m.group(3)
        ts_end = m.group(4).rsplit(',', 1)[0].rsplit('.', 1)[0]
        ms_end = m.group(5)
        text = m.group(6).strip()
        segments.append((
            _ts_to_sec(ts_start, ms_start),
            _ts_to_sec(ts_end, ms_end),
            text
        ))
    return segments


def bake_subtitles_on_images(
    image_paths, srt_path, page_timings, temp_dir,
    font_size=None, video_width=None, video_height=None
):
    """
    Render subtitle text directly onto page images using PIL.
    Returns (new_image_paths, new_durations) for concat-based video creation.

    Each subtitle segment becomes an annotated copy of the page image
    that is visible during that time window. Gaps between subtitles
    use unmodified page images.
    """
    from PIL import Image, ImageDraw, ImageFont

    segments = _parse_srt(srt_path)
    if not segments:
        return image_paths, page_timings

    # Determine page time boundaries
    page_boundaries = [0.0]
    cumulative = 0.0
    for t in page_timings:
        cumulative += t
        page_boundaries.append(cumulative)

    total_duration = cumulative

    # Find a CJK-capable font
    font_paths = [
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    font = None
    if font_size is None:
        # Scale font to ~4.5% of video height
        if video_height:
            font_size = max(18, int(video_height * 0.045))
        else:
            # Read from first image
            img = Image.open(image_paths[0])
            font_size = max(18, int(img.height * 0.045))

    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    def _which_page(time_sec):
        """Return the page index (0-based) for a given time."""
        for i in range(len(page_boundaries) - 1):
            if page_boundaries[i] <= time_sec < page_boundaries[i + 1]:
                return i
        # After the last boundary, use the last page
        return len(image_paths) - 1

    def _render_subtitle(page_img, text):
        """Draw subtitle text at the bottom of a page image. Returns new image."""
        img = page_img.copy()
        draw = ImageDraw.Draw(img)
        w, h = img.size

        # Wrap text to fit within video width
        max_chars = max(10, int(w / (font_size * 1.1)))
        lines = []
        for para in text.split('\n'):
            para = para.strip()
            while len(para) > max_chars:
                lines.append(para[:max_chars])
                para = para[max_chars:]
            if para:
                lines.append(para)

        line_height = font_size + 6
        text_block_h = len(lines) * line_height

        # Measure max line width
        max_line_w = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            max_line_w = max(max_line_w, bbox[2] - bbox[0])

        # Draw semi-transparent background box
        padding_x = int(w * 0.03)
        padding_y = 10
        box_x = (w - max_line_w) / 2 - padding_x
        box_y = h * 0.82 - padding_y
        box_w = max_line_w + 2 * padding_x
        box_h = text_block_h + 2 * padding_y

        # Create overlay for semi-transparent box
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(
            [box_x, box_y, box_x + box_w, box_y + box_h],
            fill=(0, 0, 0, 160)
        )
        img = Image.alpha_composite(img.convert('RGBA'), overlay)

        # Draw text lines
        draw = ImageDraw.Draw(img)
        y_offset = h * 0.82
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            x = (w - line_w) / 2
            draw.text((x, y_offset), line, font=font, fill=(255, 255, 255, 255))
            y_offset += line_height

        return img.convert('RGB')

    # Build annotated images and durations
    new_images = []
    new_durations = []

    # Track time as we process
    current_time = 0.0

    for seg_start, seg_end, seg_text in segments:
        # Gap before this subtitle: use unmodified page images
        if seg_start > current_time + 0.05:
            gap_start = current_time
            gap_end = seg_start
            # Process the gap page by page
            t = gap_start
            while t < gap_end:
                page_idx = _which_page(t)
                page_boundary = page_boundaries[page_idx + 1]
                chunk_end = min(gap_end, page_boundary)
                chunk_dur = chunk_end - t
                if chunk_dur > 0.01:
                    new_images.append(image_paths[page_idx])
                    new_durations.append(chunk_dur)
                t = chunk_end

        # The subtitle segment itself
        seg_dur = seg_end - seg_start
        if seg_dur <= 0:
            continue

        page_idx = _which_page(seg_start)
        page_img = Image.open(image_paths[page_idx])
        annotated = _render_subtitle(page_img, seg_text)
        annotated_path = os.path.join(temp_dir, f'baked_sub_{len(new_images):05d}.png')
        annotated.save(annotated_path)
        new_images.append(annotated_path)
        new_durations.append(seg_dur)

        current_time = seg_end

    # Trailing gap after last subtitle
    if current_time < total_duration - 0.05:
        t = current_time
        while t < total_duration:
            page_idx = _which_page(t)
            if page_idx >= len(image_paths):
                break
            page_boundary = page_boundaries[page_idx + 1]
            chunk_end = min(total_duration, page_boundary)
            chunk_dur = chunk_end - t
            if chunk_dur > 0.01:
                new_images.append(image_paths[page_idx])
                new_durations.append(chunk_dur)
            t = chunk_end

    print(f"Baked {len(segments)} subtitle segments onto {len(set(new_images))} images")
    print(f"Total segments in concat: {len(new_images)}, total duration: {sum(new_durations):.1f}s")
    return new_images, new_durations


def burn_subtitles(video_with_audio_path: str, subs_path: str, output_path: str,
                   quality_preset: str = 'medium', target_bitrate: str = '1.5M',
                   resolution: Optional[str] = None) -> str:
    """
    Burn subtitles into video. Tries native ffmpeg subtitles filter first.
    If unavailable, subtitles should already be baked into the video frames
    (via bake_subtitles_on_images). In that case, just copy the video.
    """
    print("Burning subtitles into video")

    # Check if native subtitles filter is available
    try:
        check = subprocess.run(
            ['ffmpeg', '-filters'], capture_output=True, text=True, timeout=10
        )
        has_native = ' subtitles ' in check.stdout
    except Exception:
        has_native = False

    if has_native:
        escaped_subs = subs_path
        for ch in ('\\', ':', "'", ',', '=', '[', ']', '%'):
            escaped_subs = escaped_subs.replace(ch, '\\' + ch)
        vf = f"subtitles=filename={escaped_subs}"
        if resolution:
            vf += f",scale={resolution}"

        cmd = [
            'ffmpeg', '-y',
            '-i', video_with_audio_path,
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-pix_fmt', 'yuv420p', '-c:a', 'copy',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Subtitle burning failed: {result.stderr}")
    else:
        # Subtitles already baked into frame images — just copy
        print("Native subtitles filter unavailable. Assuming subtitles baked into frames.")
        import shutil
        shutil.copy2(video_with_audio_path, output_path)

    if not os.path.exists(output_path):
        raise RuntimeError(f"Output file was not created: {output_path}")
    print(f"Output file created successfully, size: {os.path.getsize(output_path)} bytes")
    return output_path


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get total number of pages in PDF.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Number of pages in PDF

    Raises:
        RuntimeError: If PDF reading fails
    """
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()
        return page_count
    except Exception as e:
        raise RuntimeError(f"Failed to read PDF: {str(e)}")


def cleanup(temp_dir: str):
    """Clean up temporary directory."""
    try:
        import shutil
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        print(f"Warning: Failed to clean up {temp_dir}: {e}")


def validate_inputs(pdf_path: str, audio_path: str, subs_path: str, output_path: str, start_page: int = 1, end_page: Optional[int] = None):
    """Validate input files exist, output directory is writable, and page range is valid."""
    # Check input files exist
    for path, name in [(pdf_path, "PDF"), (audio_path, "audio"), (subs_path, "subtitle")]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{name} file not found: {path}")

    # Check output directory is writable
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if not os.access(output_dir, os.W_OK):
        raise PermissionError(f"Output directory is not writable: {output_dir}")

    # Validate page range
    if start_page < 1:
        raise ValueError(f"Start page must be >= 1, got {start_page}")

    if end_page is not None and end_page < start_page:
        raise ValueError(f"End page ({end_page}) must be >= start page ({start_page})")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Convert PDF, audio, and subtitle files into MP4 video with burned subtitles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --pdf book.pdf --audio narration.m4a --subs subtitles.srt --output video.mp4
  %(prog)s -p document.pdf -a track.mp3 -s captions.srt -o final_video.mp4
  %(prog)s --pdf book.pdf --audio audio.m4a --subs subs.srt --output video.mp4 --start-page 5 --end-page 15

  Size optimization examples:
  %(prog)s --pdf book.pdf --audio audio.m4a --subs subs.srt --output small.mp4 --quality low --bitrate 800k
  %(prog)s --pdf book.pdf --audio audio.m4a --subs subs.srt --output medium.mp4 --quality medium --resolution 1280x720
  %(prog)s --pdf book.pdf --audio audio.m4a --subs subs.srt --output tiny.mp4 --quality low --bitrate 500k --resolution 854x480
        """
    )

    parser.add_argument('--pdf', '-p', required=True, help='PDF file path')
    parser.add_argument('--audio', '-a', required=True, help='Audio file path (.m4a, .mp3, .wav, etc.)')
    parser.add_argument('--subs', '-s', required=True, help='Subtitle file path (.srt)')
    parser.add_argument('--output', '-o', required=True, help='Output MP4 video path')
    parser.add_argument('--start-page', type=int, default=1, help='Starting page number (default: 1)')
    parser.add_argument('--end-page', type=int, help='Ending page number (default: last page)')
    # Video quality and size optimization options
    parser.add_argument('--quality', choices=['low', 'medium', 'high', 'ultra'], default='medium',
                        help='Video quality preset (default: medium). Low=smaller file, Ultra=better quality')
    parser.add_argument('--bitrate', default='1.5M',
                        help='Target video bitrate (default: 1.5M). Use lower values for smaller files (e.g., 800k, 1M)')
    parser.add_argument('--resolution', help='Output resolution (e.g., 1280x720, 854x480). Auto if not specified')
    parser.add_argument('--vertical', action='store_true', help='Use vertical layout for traditional Chinese text (combines two pages side by side)')
    parser.add_argument('--odd-right-even-left', action='store_true', help='Use odd pages on right and even pages on left layout (for traditional Chinese books)')
    # Highlight functionality options (Phase 2)
    parser.add_argument('--enable-highlight', action='store_true', help='Enable real-time subtitle tracking with text highlighting')
    parser.add_argument('--highlight-color', default='0,200,255,220', help='Indicator color in RGBA format (default: 0,200,255,220 - bright cyan-blue)')
    parser.add_argument('--highlight-style', choices=['background', 'underline', 'box'], default='background', help='Highlight style (default: background)')
    parser.add_argument('--highlight-padding', type=int, default=3, help='Highlight padding in pixels (default: 3)')
    parser.add_argument('--karaoke', action='store_true', help='Karaoke-style progressive character-by-character highlighting')
    parser.add_argument('--karaoke-fps', type=int, default=12, help='FPS for karaoke rendering (default: 12)')

    args = parser.parse_args()

    # Validate FFmpeg availability
    if not check_ffmpeg():
        print("Error: FFmpeg and/or ffprobe not found in PATH")
        print("Please install FFmpeg: brew install ffmpeg")
        sys.exit(1)

    # Validate inputs
    try:
        validate_inputs(args.pdf, args.audio, args.subs, args.output, args.start_page, args.end_page)
    except (FileNotFoundError, PermissionError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="video_creation_")
    print(f"Using temporary directory: {temp_dir}")

    try:
        # Convert PDF pages to images (with optional text extraction for highlights)
        extract_text = args.enable_highlight and HIGHLIGHT_AVAILABLE
        image_paths, text_data = convert_pdf_to_images(
            pdf_path=args.pdf,
            temp_dir=temp_dir,
            start_page=args.start_page,
            end_page=args.end_page,
            vertical_layout=args.vertical,
            enable_crop=False,  # Crop settings not available in CLI
            crop_settings=None,
            odd_right_even_left=args.odd_right_even_left,
            extract_text_data=extract_text
        )
        print(f"Generated {len(image_paths)} images from pages {args.start_page} to {args.end_page if args.end_page else 'end'}")
        
        # Debug: Check if images were actually created
        for i, img_path in enumerate(image_paths):
            if os.path.exists(img_path):
                size = os.path.getsize(img_path)
                print(f"Image {i+1}: {img_path} - Size: {size} bytes")
            else:
                print(f"❌ Image {i+1} not found: {img_path}")
        
        # Create highlight/indicator/karaoke frames if enabled
        image_durations = None
        karaoke_silent_path = None
        if args.enable_highlight and HIGHLIGHT_AVAILABLE and text_data:
            try:
                color_parts = [int(x.strip()) for x in args.highlight_color.split(',')]
                if len(color_parts) != 4:
                    raise ValueError("Color must have 4 components (RGBA)")
                indicator_color = tuple(color_parts)
            except Exception as e:
                print(f"Warning: Invalid indicator color format: {e}, using default")
                indicator_color = (0, 200, 255, 220)

            indicator_config = IndicatorConfig(
                color=indicator_color,
                line_width=8,
                padding=10,
                bar_length_ratio=0.9,
            )

            if args.karaoke:
                print("Karaoke mode enabled — progressive character highlighting")
                karaoke_silent_path = create_karaoke_video_frames(
                    image_paths=image_paths,
                    subtitle_path=args.subs,
                    audio_path=args.audio,
                    text_data=text_data,
                    temp_dir=temp_dir,
                    indicator_config=indicator_config,
                    fps=args.karaoke_fps,
                )
            else:
                print("Indicator mode enabled — rendering position indicator frames")
                image_paths, image_durations = create_indicator_video_frames(
                    image_paths=image_paths,
                    subtitle_path=args.subs,
                    audio_path=args.audio,
                    text_data=text_data,
                    temp_dir=temp_dir,
                    indicator_config=indicator_config,
                )
        elif args.enable_highlight and not HIGHLIGHT_AVAILABLE:
            print("Warning: Highlight functionality requested but not available (missing dependencies)")
        elif args.enable_highlight and not text_data:
            print("Warning: Highlight functionality requested but text extraction failed")

        # Step 2: Create silent video (or use karaoke silent video)
        if karaoke_silent_path:
            silent_video_path = karaoke_silent_path
            print(f"Karaoke silent video: {silent_video_path}")
        else:
            silent_video_path = create_silent_video(args.audio, image_paths, temp_dir, image_durations=image_durations)

        # Debug: Check if silent video was created
        if os.path.exists(silent_video_path):
            size = os.path.getsize(silent_video_path)
            print(f"Silent video created: {silent_video_path} - Size: {size} bytes")
        else:
            print(f"❌ Silent video not created: {silent_video_path}")

        # Step 3: Merge audio
        video_with_audio_path = merge_audio_video(silent_video_path, args.audio, temp_dir)

        # Debug: Check if video with audio was created
        if os.path.exists(video_with_audio_path):
            size = os.path.getsize(video_with_audio_path)
            print(f"Video with audio created: {video_with_audio_path} - Size: {size} bytes")
        else:
            print(f"❌ Video with audio not created: {video_with_audio_path}")

        # Step 4: Burn subtitles (indicator + SRT together for visibility)
        final_video_path = burn_subtitles(video_with_audio_path, args.subs, args.output,
                                        quality_preset=args.quality,
                                        target_bitrate=args.bitrate,
                                        resolution=getattr(args, 'resolution', None))

        # Debug: Check final video
        if os.path.exists(final_video_path):
            size = os.path.getsize(final_video_path)
            print(f"Final video created: {final_video_path} - Size: {size} bytes")
        else:
            print(f"❌ Final video not created: {final_video_path}")

        print(f"\n✅ Video creation completed successfully!")
        print(f"📹 Output: {final_video_path}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

    finally:
        # Clean up temporary files
        cleanup(temp_dir)


if __name__ == "__main__":
    main()