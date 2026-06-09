#!/usr/bin/env python3
"""
Debug script: diagnose why indicator lines aren't visible.
Run: python debug_indicator.py --pdf in.pdf --audio in.m4a --subs in.srt
"""
import argparse, os, sys, tempfile
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', '-p', required=True)
    parser.add_argument('--audio', '-a', required=True)
    parser.add_argument('--subs', '-s', required=True)
    parser.add_argument('--start-page', type=int, default=1)
    parser.add_argument('--end-page', type=int)
    parser.add_argument('--vertical', action='store_true')
    parser.add_argument('--odd-right-even-left', action='store_true')
    args = parser.parse_args()

    # Step 1: convert single page to image, check dimensions
    from create_video import convert_pdf_to_images
    temp_dir = tempfile.mkdtemp(prefix="debug_indicator_")
    print(f"Temp dir: {temp_dir}")

    extract_text = True
    image_paths, text_data = convert_pdf_to_images(
        pdf_path=args.pdf,
        temp_dir=temp_dir,
        start_page=args.start_page,
        end_page=args.end_page or args.start_page + 1,
        vertical_layout=args.vertical,
        odd_right_even_left=args.odd_right_even_left,
        extract_text_data=extract_text,
        enable_crop=False,
        crop_settings=None,
    )

    print(f"\n=== IMAGES ===")
    print(f"Count: {len(image_paths)}")
    for i, p in enumerate(image_paths):
        img = Image.open(p)
        print(f"  [{i}] {os.path.basename(p)}: {img.size[0]}x{img.size[1]} px, mode={img.mode}")

    print(f"\n=== TEXT DATA ===")
    if not text_data:
        print("  text_data is None or empty!")
    else:
        print(f"Count: {len(text_data)}")
        for td in text_data:
            char_count = len(td.characters)
            if char_count > 0:
                xs = [c.x for c in td.characters]
                ys = [c.y for c in td.characters]
                ws = [c.width for c in td.characters]
                hs = [c.height for c in td.characters]
                print(f"  page_number={td.page_number}, reading_order={td.reading_order}")
                print(f"    chars={char_count}, x=[{min(xs):.0f},{max(xs):.0f}], y=[{min(ys):.0f},{max(ys):.0f}]")
                print(f"    char_w={ws[0]:.1f}, char_h={hs[0]:.1f}")
                print(f"    page_w={td.page_width:.0f}, page_h={td.page_height:.0f}")
                print(f"    first 5 chars: {td.full_text[:5]}")
            else:
                print(f"  page_number={td.page_number}, reading_order={td.reading_order}, chars=0 (EMPTY!)")

    # Step 2: parse subtitles
    from subtitle_parser import SubtitleParser
    parser_srt = SubtitleParser()
    subtitles = parser_srt.parse_srt(args.subs)
    print(f"\n=== SUBTITLES ===")
    print(f"Count: {len(subtitles)}")
    if subtitles:
        print(f"  First: [{subtitles[0].start_time:.1f}s-{subtitles[0].end_time:.1f}s] text='{subtitles[0].text[:40]}' cleaned='{subtitles[0].cleaned_text[:20]}'")
        print(f"  Last:  [{subtitles[-1].start_time:.1f}s-{subtitles[-1].end_time:.1f}s] text='{subtitles[-1].text[:40]}' cleaned='{subtitles[-1].cleaned_text[:20]}'")

    # Step 3: map subtitles to text
    from text_mapping_engine import TextMappingEngine
    mapper = TextMappingEngine()
    mappings = mapper.map_subtitles_to_text(subtitles, text_data, fuzzy_match=True)
    print(f"\n=== MAPPINGS ===")
    print(f"Count: {len(mappings)}")
    if mappings:
        for m in mappings[:3]:
            coord_count = len(m.coordinates)
            print(f"  page={m.page_number}, confidence={m.confidence:.2f}, match={m.match_type}")
            print(f"    time: {m.subtitle.start_time:.1f}s - {m.subtitle.end_time:.1f}s")
            print(f"    text: '{m.subtitle.text[:40]}'")
            print(f"    coordinates: {coord_count} rects")
            for c in m.coordinates[:2]:
                print(f"      Rect(x={c.x:.0f}, y={c.y:.0f}, w={c.width:.0f}, h={c.height:.0f})")

        # Check page_number distribution
        pages_seen = set(m.page_number for m in mappings)
        print(f"  pages seen: {sorted(pages_seen)}")
        text_pages = set(td.page_number for td in text_data)
        print(f"  pages in text_data: {sorted(text_pages)}")
        unmatched = pages_seen - text_pages
        if unmatched:
            print(f"  UNMATCHED pages: {sorted(unmatched)} — these will be skipped!")
    else:
        print("  WARNING: No mappings produced! Check subtitle text vs PDF text.")

    # Step 4: render indicator frames
    from indicator_renderer import IndicatorRenderer, IndicatorConfig
    renderer = IndicatorRenderer(IndicatorConfig(
        color=(255, 0, 0, 255),    # solid red for debug
        line_width=8,               # thicker for visibility
        padding=10,
    ))
    indicator_dir = os.path.join(temp_dir, "indicator")
    os.makedirs(indicator_dir, exist_ok=True)

    frames = renderer.render_indicator_frames(
        image_paths=image_paths,
        mappings=mappings,
        text_data=text_data,
        output_dir=indicator_dir,
    )
    print(f"\n=== INDICATOR FRAMES ===")
    print(f"Count: {len(frames)}")
    if frames:
        for i, (path, dur) in enumerate(frames[:5]):
            exists = os.path.exists(path)
            size = os.path.getsize(path) if exists else 0
            print(f"  [{i}] {os.path.basename(path)}: duration={dur:.2f}s, exists={exists}, size={size}")
            if exists:
                # Check if image actually has red pixels (indicator drawn)
                img = Image.open(path)
                # Sample right side where vertical bar should be
                has_red = False
                pixels = list(img.getdata())
                for px in pixels[:1000]:
                    if px[0] > 200 and px[1] < 50 and px[2] < 50:
                        has_red = True
                        break
                print(f"       has_red_pixels={has_red}, image_size={img.size}")

    if not frames:
        print("  WARNING: No indicator frames generated!")
        print(f"  mappings count was: {len(mappings)}")

    print(f"\n=== DONE ===")
    print(f"Check temp dir for output: {temp_dir}")
    print(f"First indicator frame: {frames[0][0] if frames else 'N/A'}")


if __name__ == '__main__':
    main()
