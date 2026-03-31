# Style Extraction Implementation Plan

> **For agentic workers:** REQUIRED: Use dev-workflow:subagent-driven-development (if subagents available) or dev-workflow:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract style metadata (color, size, position, bold) from original PDF and apply it to comparison PDF rendering.

**Architecture:** New `extract_page_styles()` function in translate_pipeline.py analyzes PDF text blocks via PyMuPDF + Pillow pixel sampling, then passes enriched data to generate_comparison_pdf.py which applies per-paragraph styling.

**Tech Stack:** PyMuPDF (fitz), Pillow (PIL), difflib (stdlib), fpdf2

**Spec:** `docs/specs/2026-03-18-style-extraction-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/translate_pipeline.py` | Modify | Add `extract_page_styles()` + wire into `cmd_build()` |
| `src/generate_comparison_pdf.py` | Modify | Accept `page_style` dict, render styled text |
| `tests/test_style_extraction.py` | Create | Unit tests for extraction logic |
| `tests/test_comparison_pdf.py` | Create | Unit tests for styled rendering |

---

## Chunk 1: Style Extraction Core

### Task 1: Color Sampling Function

**Files:**
- Create: `tests/test_style_extraction.py`
- Modify: `src/translate_pipeline.py`

- [ ] **Step 1: Write failing test for color sampling**

```python
# tests/test_style_extraction.py
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
import numpy as np

def test_sample_block_color_returns_median_rgb():
    """3x3 grid sampling with background filtering."""
    # Create a 100x50 test image: dark gray text on white background
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    # Draw some dark pixels in center area
    for x in range(20, 80):
        for y in range(10, 40):
            img.putpixel((x, y), (70, 70, 70))

    from src.translate_pipeline import sample_block_color
    bbox = (10, 5, 90, 45)  # x0, y0, x1, y1 in pixel coords
    r, g, b = sample_block_color(img, bbox)
    assert 50 <= r <= 90
    assert 50 <= g <= 90
    assert 50 <= b <= 90


def test_sample_block_color_all_background_returns_default():
    """If all sampled pixels are background, return default black."""
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    from src.translate_pipeline import sample_block_color
    bbox = (0, 0, 100, 50)
    r, g, b = sample_block_color(img, bbox)
    assert (r, g, b) == (40, 40, 40)  # default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/test_style_extraction.py::test_sample_block_color_returns_median_rgb -v`
Expected: FAIL with ImportError (function doesn't exist yet)

- [ ] **Step 3: Implement `sample_block_color()`**

Add to `src/translate_pipeline.py` after the imports section (~line 27):

```python
from PIL import Image
from statistics import median

def sample_block_color(
    page_img: Image.Image,
    bbox: tuple[float, float, float, float],
    bg_threshold: int = 240,
    default_rgb: tuple[int, int, int] = (40, 40, 40),
) -> tuple[int, int, int]:
    """Sample text color from a bbox region using 3x3 grid.

    Filters out background pixels (brightness > bg_threshold).
    Returns median RGB of text-colored pixels, or default if all background.
    """
    x0, y0, x1, y1 = [int(v) for v in bbox]
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return default_rgb

    samples_r, samples_g, samples_b = [], [], []
    for row in range(3):
        for col in range(3):
            px = x0 + int(w * (col + 1) / 4)
            py = y0 + int(h * (row + 1) / 4)
            px = min(max(px, 0), page_img.width - 1)
            py = min(max(py, 0), page_img.height - 1)
            r, g, b = page_img.getpixel((px, py))[:3]
            brightness = (r + g + b) / 3
            if brightness <= bg_threshold:
                samples_r.append(r)
                samples_g.append(g)
                samples_b.append(b)

    if not samples_r:
        return default_rgb

    return (int(median(samples_r)), int(median(samples_g)), int(median(samples_b)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/test_style_extraction.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_style_extraction.py src/translate_pipeline.py
git commit -m "feat: add sample_block_color() with 3x3 grid sampling"
```

---

### Task 2: Block Classification Functions (size, position, bold)

**Files:**
- Modify: `tests/test_style_extraction.py`
- Modify: `src/translate_pipeline.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_style_extraction.py`:

```python
def test_classify_size_small():
    from src.translate_pipeline import classify_block_size
    assert classify_block_size(estimated_pt=7.5) == "small"

def test_classify_size_medium():
    from src.translate_pipeline import classify_block_size
    assert classify_block_size(estimated_pt=11.0) == "medium"

def test_classify_size_large():
    from src.translate_pipeline import classify_block_size
    assert classify_block_size(estimated_pt=16.0) == "large"

def test_classify_size_xlarge():
    from src.translate_pipeline import classify_block_size
    assert classify_block_size(estimated_pt=24.0) == "xlarge"


def test_classify_position_header():
    from src.translate_pipeline import classify_block_position
    # block center y at 5% of page height → header
    assert classify_block_position(cy=50, cx=300, page_h=1000, page_w=600) == "header"

def test_classify_position_footer():
    from src.translate_pipeline import classify_block_position
    assert classify_block_position(cy=920, cx=300, page_h=1000, page_w=600) == "footer"

def test_classify_position_right():
    from src.translate_pipeline import classify_block_position
    assert classify_block_position(cy=500, cx=500, page_h=1000, page_w=600) == "right"

def test_classify_position_body():
    from src.translate_pipeline import classify_block_position
    assert classify_block_position(cy=500, cx=300, page_h=1000, page_w=600) == "body"


def test_detect_bold_from_flags():
    from src.translate_pipeline import detect_bold
    # flags bit 4 (16) = bold, bit 5 (32) = italic
    assert detect_bold(flags=20) is True   # 16 + 4 = superscript+bold
    assert detect_bold(flags=0) is False
    assert detect_bold(flags=16) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/test_style_extraction.py -v -k "classify or detect"`
Expected: FAIL (functions don't exist)

- [ ] **Step 3: Implement classification functions**

Add to `src/translate_pipeline.py` after `sample_block_color()`:

```python
def classify_block_size(estimated_pt: float) -> str:
    """Classify font size into size_class."""
    if estimated_pt < 9:
        return "small"
    elif estimated_pt <= 13:
        return "medium"
    elif estimated_pt <= 20:
        return "large"
    else:
        return "xlarge"


def classify_block_position(
    cy: float, cx: float, page_h: float, page_w: float
) -> str:
    """Classify block position based on center coordinates."""
    if cy < page_h * 0.12:
        return "header"
    if cy > page_h * 0.88:
        return "footer"
    if cx > page_w * 0.70:
        return "right"
    return "body"


def detect_bold(flags: int) -> bool:
    """Detect bold from PyMuPDF span flags. Bit 4 (value 16) = bold."""
    return bool(flags & 16)
```

- [ ] **Step 4: Run tests**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/test_style_extraction.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_style_extraction.py src/translate_pipeline.py
git commit -m "feat: add block classification (size, position, bold)"
```

---

### Task 3: Page-Level Style Extraction

**Files:**
- Modify: `tests/test_style_extraction.py`
- Modify: `src/translate_pipeline.py`

- [ ] **Step 1: Write failing test for `extract_page_styles()`**

Append to `tests/test_style_extraction.py`:

```python
import os

PDF_PATH = "data/pdf/후아후아_20251210-part-1-ocr.pdf"

@pytest.mark.skipif(
    not os.path.exists(PDF_PATH),
    reason="Test PDF not available"
)
def test_extract_page_styles_page8():
    """Integration test: extract styles from real page 8."""
    from src.translate_pipeline import extract_page_styles

    translations = [
        {"page": 8, "original": "はじめに　みなさん", "translated": "머리말\n여러분"}
    ]
    result = extract_page_styles(PDF_PATH, (8, 8), translations)

    assert len(result) == 1
    entry = result[0]
    assert "page_style" in entry

    ps = entry["page_style"]
    assert "dominant" in ps
    assert "special_blocks" in ps

    # dominant color should be dark (not bright green or red)
    r, g, b = ps["dominant"]["color_rgb"]
    assert r < 150 and g < 150 and b < 150

    # size should be medium (body text)
    assert ps["dominant"]["size_class"] in ("small", "medium")


@pytest.mark.skipif(
    not os.path.exists(PDF_PATH),
    reason="Test PDF not available"
)
def test_extract_page_styles_backward_compatible():
    """Translations without page_style should still work."""
    from src.translate_pipeline import extract_page_styles

    translations = [
        {"page": 8, "original": "test", "translated": "테스트"}
    ]
    result = extract_page_styles(PDF_PATH, (8, 8), translations)
    # Should return list with page_style added, not crash
    assert isinstance(result, list)
    assert result[0]["page"] == 8
    assert result[0]["translated"] == "테스트"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/test_style_extraction.py::test_extract_page_styles_page8 -v`
Expected: FAIL (function doesn't exist)

- [ ] **Step 3: Implement `extract_page_styles()`**

Add to `src/translate_pipeline.py` after the classification functions:

```python
from difflib import SequenceMatcher
from collections import Counter

FUZZY_MATCH_THRESHOLD = 0.5
PT_TO_MM = 0.3528
SIZE_CLASS_TO_PT = {"small": 8, "medium": 10, "large": 13, "xlarge": 16}


def _analyze_page_blocks(page, page_img):
    """Extract style info from all text blocks on a page.

    Returns list of dicts with: text, color_rgb, size_class, position, bold.
    """
    page_h = page.rect.height
    page_w = page.rect.width
    dpi_scale = page_img.width / page_w  # pixel coords = pdf coords * scale

    blocks_info = []
    text_dict = page.get_text("dict")

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:  # text blocks only
            continue

        bbox = block["bbox"]  # (x0, y0, x1, y1) in PDF points
        block_text = ""
        line_count = 0
        span_flags = 0

        for line in block.get("lines", []):
            line_count += 1
            for span in line.get("spans", []):
                block_text += span.get("text", "")
                span_flags = span.get("flags", 0)  # use last span's flags

        block_text = block_text.strip()
        if not block_text:
            continue

        # Center coordinates
        cy = (bbox[1] + bbox[3]) / 2
        cx = (bbox[0] + bbox[2]) / 2

        # Font size estimation from bbox height
        block_height = bbox[3] - bbox[1]
        estimated_pt = (block_height / max(line_count, 1)) * 0.75

        # Pixel bbox for color sampling
        pixel_bbox = (
            bbox[0] * dpi_scale,
            bbox[1] * dpi_scale,
            bbox[2] * dpi_scale,
            bbox[3] * dpi_scale,
        )
        color_rgb = list(sample_block_color(page_img, pixel_bbox))

        blocks_info.append({
            "text": block_text,
            "color_rgb": color_rgb,
            "size_class": classify_block_size(estimated_pt),
            "position": classify_block_position(cy, cx, page_h, page_w),
            "bold": detect_bold(span_flags),
            "estimated_pt": estimated_pt,
        })

    return blocks_info


def _compute_page_style(blocks_info):
    """Compute dominant style and identify special blocks.

    Returns: {"dominant": {...}, "special_blocks": [...]}
    """
    body_blocks = [b for b in blocks_info if b["position"] == "body"]

    if not body_blocks:
        body_blocks = blocks_info  # fallback: use all blocks

    if not body_blocks:
        return {"dominant": {"color_rgb": [40, 40, 40], "size_class": "medium", "bold": False}, "special_blocks": []}

    # Dominant color: most common
    color_counts = Counter(tuple(b["color_rgb"]) for b in body_blocks)
    dominant_color = list(color_counts.most_common(1)[0][0])

    # Dominant size: median
    sizes = [b["estimated_pt"] for b in body_blocks]
    dominant_size = classify_block_size(median(sizes))

    # Dominant bold: majority
    dominant_bold = sum(1 for b in body_blocks if b["bold"]) > len(body_blocks) / 2

    dominant = {
        "color_rgb": dominant_color,
        "size_class": dominant_size,
        "bold": dominant_bold,
    }

    # Special blocks: different from dominant
    special = []
    for b in blocks_info:
        is_special = False
        if tuple(b["color_rgb"]) != tuple(dominant_color):
            is_special = True
        if b["size_class"] != dominant_size and b["size_class"] in ("large", "xlarge"):
            is_special = True
        if b["bold"] and not dominant_bold:
            is_special = True
        if b["position"] in ("header", "footer"):
            is_special = True

        if is_special:
            special.append({
                "text_hint": b["text"][:30],
                "color_rgb": b["color_rgb"],
                "size_class": b["size_class"],
                "bold": b["bold"],
                "position": b["position"],
            })

    return {"dominant": dominant, "special_blocks": special[:10]}  # cap at 10


def extract_page_styles(
    pdf_path: str,
    page_range: tuple[int, int],
    translations: list[dict],
) -> list[dict]:
    """Extract style metadata from original PDF and enrich translations.

    Returns translations with 'page_style' field added to each entry.
    If extraction fails for a page, that entry has no page_style (fallback).
    """
    import fitz
    from PIL import Image
    import io

    doc = fitz.open(pdf_path)
    trans_by_page = {t["page"]: t for t in translations}
    total_blocks = 0
    total_special = 0

    print(f"\n🎨 Extracting styles... ({page_range[1] - page_range[0] + 1} pages)")

    for page_num in range(page_range[0], page_range[1] + 1):
        idx = page_num - 1
        if idx < 0 or idx >= len(doc):
            continue

        entry = trans_by_page.get(page_num)
        if not entry:
            continue

        try:
            page = doc[idx]

            # Check if page has text layer
            if not page.get_text("text").strip():
                print(f"   p.{page_num}: no text layer, skipping")
                continue

            # Render page as image for color sampling
            mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            page_img = Image.open(io.BytesIO(img_data))

            # Analyze blocks
            blocks_info = _analyze_page_blocks(page, page_img)
            page_style = _compute_page_style(blocks_info)

            n_special = len(page_style["special_blocks"])
            total_blocks += len(blocks_info)
            total_special += n_special

            print(f"   p.{page_num}: {len(blocks_info)} blocks, {n_special} special")

            entry["page_style"] = page_style

        except Exception as e:
            print(f"   p.{page_num}: style extraction failed ({e}), using defaults")

    doc.close()
    print(f"   ✅ Style extraction complete ({total_blocks} blocks, {total_special} special)")

    return translations
```

- [ ] **Step 4: Run tests**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/test_style_extraction.py -v`
Expected: ALL PASS (skip if PDF not available)

- [ ] **Step 5: Commit**

```bash
git add tests/test_style_extraction.py src/translate_pipeline.py
git commit -m "feat: add extract_page_styles() with page-level analysis"
```

---

## Chunk 2: Comparison PDF Styling + Integration

### Task 4: Styled Rendering in Comparison PDF

**Files:**
- Create: `tests/test_comparison_pdf.py`
- Modify: `src/generate_comparison_pdf.py`

- [ ] **Step 1: Write failing test for styled rendering**

```python
# tests/test_comparison_pdf.py
import pytest
import os
import json
from pathlib import Path


def test_add_comparison_page_with_style(tmp_path):
    """Page with page_style renders without error."""
    from src.generate_comparison_pdf import ComparisonPDF

    pdf = ComparisonPDF()
    pdf.set_auto_page_break(auto=False)

    # Create a dummy image
    from PIL import Image
    img_path = str(tmp_path / "test.png")
    Image.new("RGB", (400, 600), (255, 255, 255)).save(img_path)

    page_style = {
        "dominant": {"color_rgb": [70, 70, 70], "size_class": "medium", "bold": False},
        "special_blocks": [
            {"text_hint": "머리말", "color_rgb": [70, 70, 70], "size_class": "large", "bold": True, "position": "header"}
        ],
    }
    # Should not raise
    pdf.add_comparison_page(1, img_path, "머리말\n\n본문 텍스트입니다.", page_style)
    out = str(tmp_path / "test.pdf")
    pdf.output(out)
    assert os.path.exists(out)


def test_add_comparison_page_without_style(tmp_path):
    """Page without page_style uses defaults (backward compatible)."""
    from src.generate_comparison_pdf import ComparisonPDF

    pdf = ComparisonPDF()
    pdf.set_auto_page_break(auto=False)

    from PIL import Image
    img_path = str(tmp_path / "test.png")
    Image.new("RGB", (400, 600), (255, 255, 255)).save(img_path)

    # No page_style argument → defaults
    pdf.add_comparison_page(1, img_path, "기본 텍스트")
    out = str(tmp_path / "test.pdf")
    pdf.output(out)
    assert os.path.exists(out)


def test_generate_comparison_pdf_with_styles(tmp_path):
    """Full generate_comparison_pdf with page_style in translations."""
    from src.generate_comparison_pdf import generate_comparison_pdf

    # Need a real PDF for image extraction
    PDF_PATH = "data/pdf/후아후아_20251210-part-1-ocr.pdf"
    if not os.path.exists(PDF_PATH):
        pytest.skip("Test PDF not available")

    translations = [
        {
            "page": 1,
            "original": "test",
            "translated": "테스트",
            "page_style": {
                "dominant": {"color_rgb": [80, 80, 80], "size_class": "large", "bold": True},
                "special_blocks": [],
            },
        }
    ]
    out = str(tmp_path / "styled.pdf")
    generate_comparison_pdf(PDF_PATH, translations, out, (1, 1))
    assert os.path.exists(out)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/test_comparison_pdf.py -v`
Expected: FAIL (signature mismatch)

- [ ] **Step 3: Modify `add_comparison_page()` to accept `page_style`**

Edit `src/generate_comparison_pdf.py`:

Change line 107:
```python
def add_comparison_page(self, page_num: int, image_path: str,
                        translated_text: str, page_style: dict = None):
```

Replace the text rendering section (lines 147-168) with:

```python
        # 번역 텍스트
        self.set_xy(right_x, content_top + 10)

        # Style defaults
        default_color = (40, 40, 40)
        default_size = 10
        is_bold = False

        if page_style and "dominant" in page_style:
            dom = page_style["dominant"]
            default_color = tuple(dom.get("color_rgb", [40, 40, 40]))
            default_size = {"small": 8, "medium": 10, "large": 13, "xlarge": 16}.get(
                dom.get("size_class", "medium"), 10
            )
            is_bold = dom.get("bold", False)

        # Build special block lookup for fuzzy matching
        special_styles = {}
        if page_style:
            for sb in page_style.get("special_blocks", []):
                hint = sb.get("text_hint", "")
                if hint:
                    special_styles[hint] = sb

        self.set_font("Korean", "B" if (is_bold and self.has_bold) else "", default_size)
        self.set_text_color(*default_color)

        for para in translated_text.split('\n'):
            para = para.strip()
            if not para:
                self.ln(3)
                continue

            # Check if paragraph matches a special block
            matched_style = None
            if special_styles:
                from difflib import SequenceMatcher
                best_score = 0
                for hint, style in special_styles.items():
                    score = SequenceMatcher(None, para[:30], hint).ratio()
                    if score > 0.5 and score > best_score:
                        best_score = score
                        matched_style = style

            if matched_style:
                ms_color = tuple(matched_style.get("color_rgb", default_color))
                ms_size = {"small": 8, "medium": 10, "large": 13, "xlarge": 16}.get(
                    matched_style.get("size_class", "medium"), default_size
                )
                ms_bold = matched_style.get("bold", False)
                self.set_font("Korean", "B" if (ms_bold and self.has_bold) else "", ms_size)
                self.set_text_color(*ms_color)
                self.set_xy(right_x, self.get_y())
                self.multi_cell(half_width, 6, para, align="L")
                # Reset to dominant
                self.set_font("Korean", "B" if (is_bold and self.has_bold) else "", default_size)
                self.set_text_color(*default_color)
            elif para.startswith('"') or para.startswith('\u201c') or para.startswith('\u300c'):
                self.set_text_color(80, 60, 120)
                self.set_xy(right_x, self.get_y())
                self.multi_cell(half_width, 6, f"  {para}", align="L")
                self.set_text_color(*default_color)
            else:
                self.set_xy(right_x, self.get_y())
                self.multi_cell(half_width, 6, para, align="L")

            self.ln(1)
```

- [ ] **Step 4: Modify `generate_comparison_pdf()` to pass styles through**

Edit lines 192-202 in `src/generate_comparison_pdf.py`:

```python
    # 번역 텍스트를 페이지별로 직접 매핑
    trans_by_page = {t["page"]: t for t in translations}
    pages_with_images = sorted(images.keys())

    # PDF 생성
    pdf = ComparisonPDF()
    pdf.set_auto_page_break(auto=False)

    for page_num in pages_with_images:
        entry = trans_by_page.get(page_num, {"translated": "(번역 없음)"})
        page_text = entry.get("translated", "(번역 없음)") if isinstance(entry, dict) else entry
        page_style = entry.get("page_style") if isinstance(entry, dict) else None
        pdf.add_comparison_page(page_num, images[page_num], page_text, page_style)
```

- [ ] **Step 5: Run tests**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/test_comparison_pdf.py tests/test_style_extraction.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_comparison_pdf.py src/generate_comparison_pdf.py
git commit -m "feat: styled rendering in comparison PDF with page_style support"
```

---

### Task 5: Wire into Pipeline

**Files:**
- Modify: `src/translate_pipeline.py` (cmd_build function)

- [ ] **Step 1: Modify `cmd_build()` to call `extract_page_styles()`**

In `src/translate_pipeline.py`, find `cmd_build()` (~line 503). Between the validation section (line 556) and the comparison PDF section (line 564), insert:

```python
    # 2.5. Style extraction
    if args.pdf and page_range:
        try:
            pages = extract_page_styles(args.pdf, page_range, pages)
            # Re-save JSON with styles included
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(pages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"\n⚠️ Style extraction failed ({e}), proceeding without styles")
```

- [ ] **Step 2: Update `build_comparison_pdf()` to pass full translation entries**

The existing `build_comparison_pdf()` function (~line 396) reads JSON and calls `generate_comparison_pdf()`. Since JSON now contains `page_style`, no change is needed — the function already loads the full JSON and passes it to `generate_comparison_pdf()`.

Verify this by reading the function — it does `translations = json.load(f)` and passes the full list.

- [ ] **Step 3: Run full integration test**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Manual integration test with real PDF (if available)**

Run:
```bash
cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate"
source .venv/bin/activate
python src/translate_pipeline.py build \
  --input translated/antigravity/translation_draft_후아후아_p1-20.md \
  --pdf data/pdf/후아후아_20251210-part-1-ocr.pdf \
  --pages 1-10 \
  --output /tmp/test_styled_pages.json
```

Expected output includes:
```
🎨 Extracting styles... (10 pages)
   p.1: N blocks, N special
   ...
   ✅ Style extraction complete
```

Visually check the generated PDF for styled text.

- [ ] **Step 5: Commit**

```bash
git add src/translate_pipeline.py
git commit -m "feat: wire style extraction into build pipeline"
```

---

### Task 6: Regression Test

**Files:**
- Modify: `tests/test_style_extraction.py`

- [ ] **Step 1: Write regression test**

Append to `tests/test_style_extraction.py`:

```python
def test_existing_json_without_styles_works():
    """Existing pages_1-20.json (no page_style) loads and works."""
    json_path = "translated/antigravity/pages_1-20.json"
    if not os.path.exists(json_path):
        pytest.skip("Test data not available")

    with open(json_path) as f:
        data = json.load(f)

    # No page_style in existing data
    for entry in data:
        assert "page" in entry
        assert "translated" in entry
        assert "page_style" not in entry  # existing data has no styles
```

- [ ] **Step 2: Run all tests**

Run: `cd "/Users/junseong/Downloads/03. NAVI/03-3. NAVI-PJ/03-4 NAVI-Translate" && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Final commit**

```bash
git add tests/
git commit -m "test: add regression test for backward compatibility"
```
