#!/bin/bash
# Quick test script for all modules

echo "==================================="
echo "Testing All Modules - Phase 1"
echo "==================================="
echo ""

# Check Python version
echo "1. Checking Python version..."
python3 --version
echo ""

# Check dependencies
echo "2. Checking dependencies..."
python3 -c "import fitz; print('✓ PyMuPDF installed')" 2>/dev/null || echo "✗ PyMuPDF not installed - run: pip install PyMuPDF"
python3 -c "import PIL; print('✓ Pillow installed')" 2>/dev/null || echo "✗ Pillow not installed - run: pip install Pillow"
python3 -c "import pytest; print('✓ pytest installed')" 2>/dev/null || echo "✗ pytest not installed - run: pip install pytest"
python3 -c "import hypothesis; print('✓ hypothesis installed')" 2>/dev/null || echo "✗ hypothesis not installed - run: pip install hypothesis"
echo ""

# Test module imports
echo "3. Testing module imports..."
python3 -c "from pdf_text_extractor import PDFTextExtractor; print('✓ pdf_text_extractor')" || echo "✗ pdf_text_extractor failed"
python3 -c "from subtitle_parser import SubtitleParser; print('✓ subtitle_parser')" || echo "✗ subtitle_parser failed"
python3 -c "from text_mapping_engine import TextMappingEngine; print('✓ text_mapping_engine')" || echo "✗ text_mapping_engine failed"
python3 -c "from highlight_renderer import HighlightRenderer; print('✓ highlight_renderer')" || echo "✗ highlight_renderer failed"
python3 -c "from video_composition_coordinator import VideoCompositionCoordinator; print('✓ video_composition_coordinator')" || echo "✗ video_composition_coordinator failed"
echo ""

# Run property tests
echo "4. Running property-based tests..."
echo "   (This may take a few minutes...)"
echo ""

if command -v pytest &> /dev/null; then
    pytest test_pdf_text_extractor.py -v --tb=short -q
    pytest test_text_mapping_engine.py -v --tb=short -q
    pytest test_highlight_renderer.py -v --tb=short -q
    echo ""
    echo "✓ All tests completed"
else
    echo "✗ pytest not found - skipping tests"
fi

echo ""
echo "==================================="
echo "Phase 1 Module Test Complete"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Review PHASE1_COMPLETION_REPORT.md"
echo "2. Prepare test data (PDF, audio, subtitle files)"
echo "3. Continue with Phase 2 (Tasks 6-12)"
echo ""
