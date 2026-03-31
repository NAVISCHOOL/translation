# Style Extraction & Comparison PDF Enhancement

**Date:** 2026-03-18
**Status:** Approved (brainstorming complete, spec reviewed)

## Problem

The comparison PDF renders all translated text in a single fixed style (10pt black).
The original PDF uses varying colors, sizes, bold, and spacing to convey structure
(headers, quotes, emphasis, footnotes). This information is lost in translation output.

## Solution

Programmatically extract style metadata from the original PDF and apply it
when rendering the comparison PDF. No changes to the translation MD format or
AI workflow.

**Core principle:** AI translates. Code extracts style. No AI style judgment.

## Prerequisites

- Input PDF must have a text layer (OCR-processed or native text).
  `fitz.Page.get_text("dict")` reads the embedded text layer, not performing OCR.
- If a page has no text layer, style extraction is skipped and defaults are used.
- Current target: `후아후아_20251210-part-1-ocr.pdf` (OCR text layer confirmed).

## Architecture

```
                    existing (unchanged)
                    ┌──────────────────────┐
 PDF ──→ prepare_pages.py ──→ page images ──→ AI translates ──→ MD draft
                    └──────────────────────┘

                    new pipeline step
                    ┌──────────────────────────────────────────┐
 MD ──→ parse ──→ JSON ──→ validate ──→ EXTRACT STYLES ──→ comparison PDF
                    └──────────────────────────────────────────┘
                                            ↑
                                   original PDF + PyMuPDF + Pillow
```

### Style extraction happens inside `translate_pipeline.py` build command,
between validation and comparison PDF generation.

## Extracted Properties

| Property | Method | Confidence |
|----------|--------|------------|
| **color** | PyMuPDF page render → Pillow multi-point RGB sampling in bbox (median) | Verified (p.8 test) |
| **size** | Text block bbox height / line count → font size estimation | Verified |
| **position** | bbox y-coordinate ratio → header / body / footer / right | Verified |
| **spacing** | Adjacent block y-distance (pt → mm conversion: 1pt = 0.3528mm) | Needs testing |
| **bold** | 1st: font flags from get_text("dict"); 2nd: pixel density fallback | Needs testing |

## Text Matching: OCR Block <-> Translation Block

Each translation entry has an `original` field with the Japanese source text.
Text blocks from PyMuPDF have their own text (may contain OCR errors).

**Definition of "block":** A PyMuPDF text block from `get_text("dict")["blocks"]`
where `block["type"] == 0` (text block, not image). Each block has `bbox`, `lines`,
and extracted text content.

**Matching strategy — page-level, not block-level:**

The current JSON has ONE `original` per page (all text concatenated).
Rather than matching the full `original` to individual OCR blocks, we apply a
**page-level dominant style** approach:

```
For each page:
  1. Get all OCR text blocks from get_text("dict")
  2. For each block, extract: color, size, position, bold
  3. Group blocks by role:
     - header blocks (y < 12% of page height)
     - footer blocks (y > 88% of page height)
     - right blocks  (x > 70% of page width)
     - body blocks   (everything else)
  4. Calculate dominant style for body blocks (most common color, median size)
  5. Identify special blocks: title (largest), colored text, bold text
  6. Store as page-level style summary
```

This avoids the 1:N block mapping problem entirely. The comparison PDF applies:
- **Dominant body style** to regular paragraphs
- **Special styles** to lines that fuzzy-match special block text

**Fuzzy matching (for special blocks only):**
- Algorithm: `difflib.SequenceMatcher.ratio()`
- Threshold: `FUZZY_MATCH_THRESHOLD = 0.5` (low, because OCR errors are common)
- Conflict resolution: highest score wins; already-matched blocks excluded (greedy)
- Performance: matching only special blocks (≤5 per page), not all text

**Color sampling method:**
- Render page at 150 DPI via `page.get_pixmap()`
- For each text block bbox:
  - Sample 9 points in a 3x3 grid within the bbox
  - Filter out background-color pixels (brightness > 240)
  - Take median RGB of remaining text-colored pixels
  - If all pixels are background, use default black

## Style Data Structure

Style is extracted per-page. Each translation entry gets a `page_style` dict:

```json
{
  "page": 8,
  "original": "はじめに　みなさん...",
  "translated": "머리말\n\n여러분...",
  "page_style": {
    "dominant": {
      "color_rgb": [70, 70, 70],
      "size_class": "medium",
      "bold": false
    },
    "special_blocks": [
      {
        "text_hint": "はじめに",
        "color_rgb": [70, 70, 70],
        "size_class": "large",
        "bold": true,
        "position": "header"
      },
      {
        "text_hint": "柴村恵美子",
        "color_rgb": [70, 70, 70],
        "size_class": "medium",
        "bold": false,
        "position": "body"
      }
    ]
  }
}
```

When `page_style` is absent, comparison PDF uses current defaults (10pt black).

## Position Classification Thresholds

Based on page dimensions (ratio-based, works for any page size):

| Position | Condition |
|----------|-----------|
| header   | block center y < 12% of page height |
| footer   | block center y > 88% of page height |
| right    | block center x > 70% of page width |
| body     | everything else |

## Size Classification

Based on estimated font size from bbox height and line count:

| size_class | font_size_range | comparison_pdf_pt |
|------------|----------------|-------------------|
| small      | < 9pt          | 8                 |
| medium     | 9-13pt         | 10                |
| large      | 14-20pt        | 13                |
| xlarge     | > 20pt         | 16                |

Font size estimation: `block_bbox_height / line_count * 0.75` (approximate).
These are starting values; will be tuned during implementation.

## Bold Detection (2-stage)

1. **Primary:** Check `span["flags"]` from `get_text("dict")` — bit 4 (16) = bold
2. **Fallback:** If flags unavailable, compare pixel density of text region vs
   known regular text on same page. Denser = bold.

## Files to Modify

### 1. `src/translate_pipeline.py`

**Add function: `extract_page_styles(pdf_path, page_range, translations)`**

```python
def extract_page_styles(
    pdf_path: str,
    page_range: tuple[int, int],
    translations: list[dict]
) -> list[dict]:
    """Extract style metadata from original PDF and enrich translations.

    Returns translations with 'page_style' field added to each entry.
    If extraction fails for a page, that entry has no page_style (fallback).
    """
```

**Modify: `cmd_build()`**
- Insert `extract_page_styles()` call between validation and comparison PDF generation
- Pass enriched translations to `build_comparison_pdf()`

### 2. `src/generate_comparison_pdf.py`

**Modify function signatures:**

```python
# Before:
def add_comparison_page(self, page_num: int, image_path: str, translated_text: str):

# After:
def add_comparison_page(self, page_num: int, image_path: str,
                        translated_text: str, page_style: dict = None):
```

```python
# Before (in generate_comparison_pdf):
trans_by_page = {t["page"]: t["translated"] for t in translations}

# After:
trans_by_page = {t["page"]: t for t in translations}
# ...
entry = trans_by_page.get(page_num, {"translated": "(번역 없음)"})
page_text = entry.get("translated", "(번역 없음)")
page_style = entry.get("page_style")
pdf.add_comparison_page(page_num, images[page_num], page_text, page_style)
```

**Rendering logic in `add_comparison_page()`:**
- Default: current behavior (10pt black)
- With `page_style`:
  - Apply `dominant.color_rgb` and `dominant.size_class` to all paragraphs
  - For paragraphs that fuzzy-match a `special_blocks[].text_hint`, apply that block's style
  - Quote detection (current `"` prefix logic) is preserved as additional styling

**Backward compatibility:**
- `generate_comparison_pdf()` function signature unchanged (accepts `list[dict]`)
- `__main__` CLI path: reads JSON without `page_style` → works as before
- `page_style=None` → all current defaults applied

## Console Output

```
🎨 Extracting styles... (10 pages)
   p.1: 3 blocks, 1 special
   p.2: 5 blocks, 2 special (1 colored)
   ...
   ✅ Style extraction complete (48 blocks, 8 special)
```

## Dependencies

- **PyMuPDF (fitz)** — already installed
- **Pillow (PIL)** — already installed
- **difflib** — stdlib (SequenceMatcher for fuzzy matching)

No new dependencies required.

## Scope & Constraints

- **New translations only** by default
- **`--restyle` flag:** deferred to future iteration (not in MVP)
- **Horizontal text only** (current format is horizontal)
- **Graceful fallback**: if extraction fails for any page, use defaults + log warning
- **No MD format changes**: AI workflow and translation rules unchanged
- **Performance**: ~1-2s per page (acceptable for 10-page chunks)

## Testing Strategy

1. **Unit test**: extract styles from page 8, verify "柴村恵美子" color ≈ RGB(70,70,70)
2. **Unit test**: fuzzy matching with OCR-error text (score > 0.5 = match)
3. **Unit test**: position classification with known bbox coordinates
4. **Integration test**: full pipeline build on pages 1-10, verify PDF generated
5. **Schema test**: enriched JSON has valid `page_style` structure
6. **Regression test**: existing pages_1-20.json (no `page_style`) works unchanged

## Verification Criteria

- [ ] Page 8 "柴村恵美子" extracted as dark color (~RGB 70,70,70), not green
- [ ] Title text classified as "large" or "xlarge"
- [ ] Page numbers classified as "footer"
- [ ] Unmatched blocks render with default style (no crash)
- [ ] Existing pages_1-20.json works without page_style field (backward compatible)
- [ ] Generated PDF page count matches input
- [ ] color_rgb values within valid range (0-255)
