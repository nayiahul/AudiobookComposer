#!/usr/bin/env python3
"""
Indicator Renderer

Draws position indicators and karaoke-style progressive character
highlights on PDF page images. Supports vertical (right-side bar)
and horizontal (underline) text layouts.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from PIL import Image, ImageDraw, ImageFont
import io
import os

from text_mapping_engine import SubtitleMapping, Rect
from pdf_text_extractor import PageTextData
from subtitle_parser import SubtitleSegment


ZOOM = 2.0  # PDF → image coordinate scale factor


@dataclass
class IndicatorConfig:
    style: str = 'side_bar'
    color: Tuple[int, int, int, int] = (0, 180, 255, 220)
    line_width: int = 8
    padding: int = 6
    bar_length_ratio: float = 0.9


class IndicatorRenderer:

    def __init__(self, config: Optional[IndicatorConfig] = None):
        self.config = config or IndicatorConfig()
        self._subtitle_font = None
        self._font_size = 0

    # ── font ──────────────────────────────────────────────

    def _get_subtitle_font(self, image_height: int) -> ImageFont.FreeTypeFont:
        font_size = max(22, int(image_height * 0.04))
        if self._subtitle_font is not None and font_size == self._font_size:
            return self._subtitle_font
        font_paths = [
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    self._subtitle_font = ImageFont.truetype(fp, font_size)
                    self._font_size = font_size
                    return self._subtitle_font
                except Exception:
                    continue
        self._subtitle_font = ImageFont.load_default()
        self._font_size = font_size
        return self._subtitle_font

    # ── indicator mode ────────────────────────────────────

    def render_indicator_frames(
        self,
        image_paths: List[str],
        subtitles: List[SubtitleSegment],
        mappings: List[SubtitleMapping],
        text_data: List[PageTextData],
        output_dir: str,
    ) -> List[Tuple[str, float]]:
        """One frame per subtitle with static indicator line + bottom text."""
        os.makedirs(output_dir, exist_ok=True)
        if not subtitles:
            return [(image_paths[0], 0)]

        map_by_idx: Dict[int, SubtitleMapping] = {m.subtitle.index: m for m in mappings}

        page_to_img: Dict[int, int] = {}
        page_orders: Dict[int, str] = {}
        for idx, td in enumerate(text_data):
            page_to_img[td.page_number] = idx
            page_orders[td.page_number] = td.reading_order

        frames: List[Tuple[str, float]] = []
        prev_end = 0.0
        current_base = image_paths[0]
        indicator_count = 0
        skipped = 0

        for sub in subtitles:
            m = map_by_idx.get(sub.index)
            gap = sub.start_time - prev_end
            if gap > 0.01:
                frames.append((current_base, gap))
            duration = sub.end_time - sub.start_time

            if m is not None:
                img_idx = page_to_img.get(m.page_number)
                if img_idx is not None and 0 <= img_idx < len(image_paths):
                    current_base = image_paths[img_idx]
                    order = page_orders.get(m.page_number, 'horizontal')
                    out = os.path.join(output_dir, f"ind_{sub.index:06d}.png")
                    self._render_indicator_frame(current_base, m.coordinates, order, sub.text, out)
                    frames.append((out, duration))
                    indicator_count += 1
                else:
                    skipped += 1
                    out = os.path.join(output_dir, f"sub_{sub.index:06d}.png")
                    self._render_subtitle_only(current_base, sub.text, out)
                    frames.append((out, duration))
            else:
                out = os.path.join(output_dir, f"sub_{sub.index:06d}.png")
                self._render_subtitle_only(current_base, sub.text, out)
                frames.append((out, duration))

            prev_end = sub.end_time

        print(f"  Indicator: {indicator_count}/{len(subtitles)} with lines, {skipped} skipped")
        return frames

    # ── karaoke mode ──────────────────────────────────────

    def render_karaoke_frames(
        self,
        image_paths: List[str],
        subtitles: List[SubtitleSegment],
        mappings: List[SubtitleMapping],
        text_data: List[PageTextData],
        output_dir: str,
        fps: int = 12,
    ) -> List[str]:
        """Per-frame progressive character highlighting at uniform fps."""
        os.makedirs(output_dir, exist_ok=True)
        if not subtitles:
            return []

        map_by_idx: Dict[int, SubtitleMapping] = {m.subtitle.index: m for m in mappings}

        # Build global character index for per-char coordinate lookup
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

        fg = self.config.color
        fill_color = (fg[0], fg[1], fg[2], min(fg[3], 120))

        frame_paths: List[str] = []
        frame_idx = 0
        current_base = image_paths[0]

        for si, sub in enumerate(subtitles):
            m = map_by_idx.get(sub.index)
            duration = sub.end_time - sub.start_time
            n_frames = max(1, int(duration * fps))

            if m is not None:
                img_idx = page_to_img.get(m.page_number)
                if img_idx is not None and 0 <= img_idx < len(image_paths):
                    current_base = image_paths[img_idx]
                    order = page_orders.get(m.page_number, 'horizontal')
                    char_coords = self._get_char_coords(m, char_to_page, page_data_map)
                    for f in range(n_frames):
                        progress = (f + 1) / n_frames
                        out = os.path.join(output_dir, f"frame_{frame_idx:08d}.png")
                        self._render_karaoke_frame(
                            current_base, char_coords, order,
                            progress, sub.text, out, fill_color,
                        )
                        frame_paths.append(out)
                        frame_idx += 1
                else:
                    for _ in range(n_frames):
                        out = os.path.join(output_dir, f"frame_{frame_idx:08d}.png")
                        self._render_subtitle_only(current_base, sub.text, out)
                        frame_paths.append(out)
                        frame_idx += 1
            else:
                for _ in range(n_frames):
                    out = os.path.join(output_dir, f"frame_{frame_idx:08d}.png")
                    self._render_subtitle_only(current_base, sub.text, out)
                    frame_paths.append(out)
                    frame_idx += 1

            if (si + 1) % 50 == 0:
                print(f"  Karaoke: {si+1}/{len(subtitles)} subs, {frame_idx} frames")

        print(f"  Karaoke: {frame_idx} frames @ {fps}fps, {len(mappings)}/{len(subtitles)} highlighted")
        return frame_paths

    # ── public helpers for pipe-based karaoke ─────────────────

    def _make_karaoke_frame(
        self,
        base_img: Image.Image,
        char_coords: List[Tuple[float, float, float, float]],
        progress: float,
        subtitle_text: str,
        fill_color: Tuple[int, int, int, int],
    ) -> Image.Image:
        """Draw progressive highlight + subtitle text on base image. Returns new Image."""
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        num_read = int(len(char_coords) * progress)
        pad = 1
        for i, (cx, cy, cw, ch) in enumerate(char_coords):
            if i >= num_read:
                break
            draw.rectangle(
                [cx - pad, cy - pad, cx + cw + pad, cy + ch + pad],
                fill=fill_color,
            )
        img = Image.alpha_composite(base_img, overlay)
        return self._draw_subtitle_text(img, subtitle_text)

    def _make_subtitle_frame(
        self, base_img: Image.Image, subtitle_text: str,
    ) -> Image.Image:
        """Draw subtitle text only (no highlight) on base image."""
        return self._draw_subtitle_text(base_img, subtitle_text)

    def _get_char_coords(
        self, mapping: SubtitleMapping,
        char_to_page: List[Tuple[int, int]],
        page_data_map: Dict[int, PageTextData],
    ) -> List[Tuple[float, float, float, float]]:
        coords = []
        for i in range(mapping.char_start_index, mapping.char_end_index):
            if i >= len(char_to_page):
                break
            pn, ci = char_to_page[i]
            pd = page_data_map.get(pn)
            if pd and ci < len(pd.characters):
                c = pd.characters[ci]
                coords.append((c.x * ZOOM, c.y * ZOOM, c.width * ZOOM, c.height * ZOOM))
        return coords

    def _render_karaoke_frame(
        self, image_path: str,
        char_coords: List[Tuple[float, float, float, float]],
        reading_order: str,
        progress: float,
        subtitle_text: str,
        output_path: str,
        fill_color: Tuple[int, int, int, int],
    ):
        img = Image.open(image_path).convert('RGBA')
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        num_read = int(len(char_coords) * progress)
        pad = 1
        for i, (cx, cy, cw, ch) in enumerate(char_coords):
            if i >= num_read:
                break
            draw.rectangle(
                [cx - pad, cy - pad, cx + cw + pad, cy + ch + pad],
                fill=fill_color,
            )

        img = Image.alpha_composite(img, overlay)
        img = self._draw_subtitle_text(img, subtitle_text)
        img = img.convert('RGB')
        img.save(output_path, 'PNG')

    # ── shared rendering helpers ──────────────────────────

    def _render_indicator_frame(
        self, image_path: str, coordinates: List[Rect],
        reading_order: str, subtitle_text: str, output_path: str,
    ):
        img = Image.open(image_path).convert('RGBA')
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for rect in self._merge_rects(coordinates, reading_order):
            self._draw_indicator(draw, rect, reading_order)
        img = Image.alpha_composite(img, overlay)
        img = self._draw_subtitle_text(img, subtitle_text)
        img.save(output_path, 'PNG')

    def _render_subtitle_only(self, image_path: str, subtitle_text: str, output_path: str):
        img = Image.open(image_path).convert('RGBA')
        img = self._draw_subtitle_text(img, subtitle_text)
        img = img.convert('RGB')
        img.save(output_path, 'PNG')

    def _draw_subtitle_text(self, img: Image.Image, text: str) -> Image.Image:
        w, h = img.size
        font = self._get_subtitle_font(h)
        max_chars = max(8, int(w / (self._font_size * 1.3)))
        cleaned = text.replace('\n', ' ').strip()
        lines = []
        while len(cleaned) > max_chars:
            lines.append(cleaned[:max_chars])
            cleaned = cleaned[max_chars:]
        if cleaned:
            lines.append(cleaned)

        draw = ImageDraw.Draw(img)
        line_h = self._font_size + 8
        text_block_h = len(lines) * line_h + 16
        max_lw = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            max_lw = max(max_lw, bbox[2] - bbox[0])

        pad_x = int(w * 0.04)
        pad_y = 12
        box_x = (w - max_lw) // 2 - pad_x
        box_y = int(h * 0.86)
        box_w = max_lw + 2 * pad_x
        box_h = text_block_h + pad_y

        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=(0, 0, 0, 170))
        img = Image.alpha_composite(img, overlay)

        draw = ImageDraw.Draw(img)
        y = box_y + pad_y // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            lw = bbox[2] - bbox[0]
            x = (w - lw) // 2
            draw.text((x, y), line, fill=(255, 255, 255), font=font)
            y += line_h
        return img

    def _merge_rects(self, coordinates: List[Rect], reading_order: str) -> List[Rect]:
        if not coordinates or reading_order != 'vertical':
            return coordinates
        sorted_rects = sorted(coordinates, key=lambda r: (r.x, r.y))
        merged = []
        cur = [sorted_rects[0]]
        cur_x = sorted_rects[0].x
        for r in sorted_rects[1:]:
            avg_w = (r.width + cur[0].width) / 2
            if abs(r.x - cur_x) < avg_w * 1.5:
                cur.append(r)
            else:
                merged.append(self._rect_union(cur))
                cur = [r]
                cur_x = r.x
        merged.append(self._rect_union(cur))
        return merged

    @staticmethod
    def _rect_union(rects: List[Rect]) -> Rect:
        if len(rects) == 1:
            return rects[0]
        mx = min(r.x for r in rects)
        my = min(r.y for r in rects)
        return Rect(x=mx, y=my,
                     width=max(r.x + r.width for r in rects) - mx,
                     height=max(r.y + r.height for r in rects) - my)

    def _draw_indicator(self, draw: ImageDraw.ImageDraw, rect: Rect, reading_order: str):
        cfg = self.config
        x, y = rect.x * ZOOM, rect.y * ZOOM
        w, h = rect.width * ZOOM, rect.height * ZOOM
        if reading_order == 'vertical':
            bx = x + w + cfg.padding * ZOOM
            bt = y + h * (1 - cfg.bar_length_ratio) / 2
            bb = y + h * (1 + cfg.bar_length_ratio) / 2
            draw.line([(bx, bt), (bx, bb)], fill=cfg.color, width=cfg.line_width)
        else:
            by = y + h + cfg.padding * ZOOM
            bl = x + w * (1 - cfg.bar_length_ratio) / 2
            br = x + w * (1 + cfg.bar_length_ratio) / 2
            draw.line([(bl, by), (br, by)], fill=cfg.color, width=cfg.line_width)
