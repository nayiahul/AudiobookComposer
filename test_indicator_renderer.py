#!/usr/bin/env python3
"""Tests for Indicator Renderer"""

import pytest
from indicator_renderer import IndicatorRenderer, IndicatorConfig
from text_mapping_engine import SubtitleMapping, Rect
from subtitle_parser import SubtitleSegment
from pdf_text_extractor import PageTextData
import tempfile
import os
from PIL import Image


def _make_test_image(w=200, h=200):
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "test.png")
    img = Image.new('RGB', (w, h), color=(255, 248, 220))
    img.save(path)
    return path, tmpdir


def _make_sub(index=1, start=0.0, end=3.0, text="test text", cleaned="testtext"):
    return SubtitleSegment(index=index, start_time=start, end_time=end,
                           text=text, cleaned_text=cleaned)


def _make_mapping(sub=None, page=1, coords=None):
    if coords is None:
        coords = [Rect(x=20, y=50, width=60, height=15)]
    if sub is None:
        sub = _make_sub()
    return SubtitleMapping(
        subtitle=sub, page_number=page,
        char_start_index=0, char_end_index=8,
        coordinates=coords, confidence=1.0, match_type='exact',
    )


def _make_text_data(page_num=1, reading_order='horizontal'):
    return PageTextData(
        page_number=page_num, characters=[],
        reading_order=reading_order, page_width=100, page_height=100,
    )


class TestIndicatorConfig:
    def test_default_values(self):
        cfg = IndicatorConfig()
        assert cfg.color == (0, 180, 255, 220)
        assert cfg.line_width == 8

    def test_custom_config(self):
        cfg = IndicatorConfig(color=(0, 255, 0, 128), line_width=6, padding=10)
        assert cfg.color == (0, 255, 0, 128)
        assert cfg.line_width == 6
        assert cfg.padding == 10


class TestIndicatorRenderer:
    def test_renders_frame_with_subtitle_text(self):
        img_path, tmpdir = _make_test_image()
        renderer = IndicatorRenderer()
        sub = _make_sub(start=0.0, end=3.0)
        mapping = _make_mapping(sub=sub)
        text_data = [_make_text_data(page_num=1, reading_order='horizontal')]

        frames = renderer.render_indicator_frames(
            image_paths=[img_path],
            subtitles=[sub],
            mappings=[mapping],
            text_data=text_data,
            output_dir=tmpdir,
        )

        assert len(frames) == 1
        out_path, duration = frames[0]
        assert duration == pytest.approx(3.0)
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0
        result = Image.open(out_path)
        assert result.size == (200, 200)

    def test_output_image_preserves_dimensions(self):
        img_path, tmpdir = _make_test_image(w=320, h=240)
        renderer = IndicatorRenderer()
        sub = _make_sub()
        mapping = _make_mapping(sub=sub)
        text_data = [_make_text_data()]

        frames = renderer.render_indicator_frames(
            image_paths=[img_path], subtitles=[sub],
            mappings=[mapping], text_data=text_data, output_dir=tmpdir,
        )
        result = Image.open(frames[0][0])
        assert result.size == (320, 240)

    def test_gap_before_first_subtitle(self):
        img_path, tmpdir = _make_test_image()
        renderer = IndicatorRenderer()
        sub = _make_sub(start=1.5, end=4.2)
        mapping = _make_mapping(sub=sub)
        text_data = [_make_text_data()]

        frames = renderer.render_indicator_frames(
            image_paths=[img_path], subtitles=[sub],
            mappings=[mapping], text_data=text_data, output_dir=tmpdir,
        )

        # gap filler (0→1.5s) + indicator frame (1.5→4.2s)
        assert len(frames) == 2
        assert frames[0][1] == pytest.approx(1.5)
        assert frames[1][1] == pytest.approx(2.7)
        # gap frame uses base image directly
        assert frames[0][0] == img_path

    def test_unmapped_subtitle_gets_subtitle_only_frame(self):
        img_path, tmpdir = _make_test_image()
        renderer = IndicatorRenderer()
        sub = _make_sub(start=0.0, end=3.0)
        text_data = [_make_text_data()]

        frames = renderer.render_indicator_frames(
            image_paths=[img_path], subtitles=[sub],
            mappings=[], text_data=text_data, output_dir=tmpdir,
        )

        # One frame: subtitle text only, no indicator line
        assert len(frames) == 1
        assert os.path.exists(frames[0][0])
        # Should be a new file (not base image) since subtitle text is overlaid
        assert frames[0][0] != img_path

    def test_total_duration_matches_subtitle_timeline(self):
        """All subtitles contribute to total duration — no scaling drift."""
        img_path, tmpdir = _make_test_image()
        renderer = IndicatorRenderer()
        s1 = _make_sub(index=1, start=0.0, end=3.0)
        s2 = _make_sub(index=2, start=3.0, end=7.0)
        s3 = _make_sub(index=3, start=7.0, end=10.0)
        m1 = _make_mapping(sub=s1)
        # s2 unmapped, s3 mapped
        m3 = _make_mapping(sub=s3)
        text_data = [_make_text_data()]

        frames = renderer.render_indicator_frames(
            image_paths=[img_path], subtitles=[s1, s2, s3],
            mappings=[m1, m3], text_data=text_data, output_dir=tmpdir,
        )

        total = sum(d for _, d in frames)
        assert total == pytest.approx(10.0)  # 3+4+3 = 10s, exact match

    def test_vertical_reading_order(self):
        img_path, tmpdir = _make_test_image()
        renderer = IndicatorRenderer()
        sub = _make_sub()
        mapping = _make_mapping(sub=sub)
        text_data = [_make_text_data(reading_order='vertical')]

        frames = renderer.render_indicator_frames(
            image_paths=[img_path], subtitles=[sub],
            mappings=[mapping], text_data=text_data, output_dir=tmpdir,
        )
        assert len(frames) == 1
        assert os.path.exists(frames[0][0])

    def test_empty_subtitles(self):
        img_path, tmpdir = _make_test_image()
        renderer = IndicatorRenderer()
        frames = renderer.render_indicator_frames(
            image_paths=[img_path], subtitles=[],
            mappings=[], text_data=[_make_text_data()], output_dir=tmpdir,
        )
        assert len(frames) == 1
        assert frames[0][1] == 0

    def test_page_out_of_range_falls_back_to_subtitle_only(self):
        img_path, tmpdir = _make_test_image()
        renderer = IndicatorRenderer()
        sub = _make_sub(start=0.0, end=3.0)
        mapping = _make_mapping(sub=sub, page=5)  # page 5 not in lookup
        text_data = [_make_text_data(page_num=1)]

        frames = renderer.render_indicator_frames(
            image_paths=[img_path], subtitles=[sub],
            mappings=[mapping], text_data=text_data, output_dir=tmpdir,
        )
        # Still produces a frame (subtitle text only), not zero
        assert len(frames) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
