#!/usr/bin/env python3
"""
NAVI-Translate: 원본 대조 PDF 생성기
원본 일본어 PDF 페이지 이미지와 한국어 번역을 나란히 배치합니다.

사용법:
  python src/generate_comparison_pdf.py \
    --original data/pdf/후아후아_20251210-part-1-ocr.pdf \
    --translation translated/test_v2_p10-11.json \
    --pages 10-11 \
    -o translated/대조본.pdf
"""
import json
import argparse
import os
import tempfile
from pathlib import Path

import fitz  # PyMuPDF - PDF 페이지를 이미지로 변환
from difflib import SequenceMatcher
from fpdf import FPDF


# ============================================================
# 한국어 폰트 탐색
# ============================================================

FUZZY_MATCH_THRESHOLD = 0.5
SIZE_CLASS_TO_PT = {"small": 8, "medium": 10, "large": 13, "xlarge": 16}

FONT_SEARCH_PATHS = [
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
]

FONT_CANDIDATES = {
    "regular": ["NanumSquare_acR.ttf", "NanumSquareR.ttf", "NanumGothic.ttf"],
    "bold": ["NanumSquareEB.ttf", "NanumSquare_acB.ttf", "NanumGothicBold.ttf"],
}


def find_font(style: str = "regular", lang_profile: dict = None) -> str:
    candidates = []
    if lang_profile and "font_candidates" in lang_profile:
        candidates = lang_profile["font_candidates"].get(style, [])
    if not candidates:
        candidates = FONT_CANDIDATES.get(style, FONT_CANDIDATES["regular"])
    for candidate in candidates:
        for search_dir in FONT_SEARCH_PATHS:
            path = os.path.join(search_dir, candidate)
            if os.path.exists(path):
                return path
    raise FileNotFoundError(f"폰트를 찾을 수 없습니다 (style={style}, 후보: {candidates})")


# ============================================================
# PDF 페이지 → 이미지 추출
# ============================================================

def extract_page_images(pdf_path: str, pages: list[int], dpi: int = 150) -> dict[int, str]:
    """PDF 페이지를 임시 PNG 이미지로 추출합니다."""
    doc = fitz.open(pdf_path)
    temp_dir = tempfile.mkdtemp(prefix="navi_pdf_")
    images = {}

    for page_num in pages:
        idx = page_num - 1  # 0-indexed
        if 0 <= idx < len(doc):
            page = doc[idx]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_path = os.path.join(temp_dir, f"page_{page_num}.png")
            pix.save(img_path)
            images[page_num] = img_path

    doc.close()
    return images


# ============================================================
# 대조 PDF 생성
# ============================================================

class ComparisonPDF(FPDF):
    """원본/번역 대조 PDF"""

    def __init__(self, lang_profile: dict = None):
        super().__init__(orientation="L", format="A4")  # 가로 방향
        self._lang_profile = lang_profile
        labels = (lang_profile or {}).get("pdf_labels", {})
        self._label_original = labels.get("original", "원문")
        self._label_translated = labels.get("translated", "번역")
        self.title_text = f"{self._label_original}/{self._label_translated} 대조"
        self._setup_fonts()

    def _setup_fonts(self):
        regular_path = find_font("regular", self._lang_profile)
        self.add_font("Korean", "", regular_path)
        try:
            bold_path = find_font("bold", self._lang_profile)
            self.add_font("Korean", "B", bold_path)
            self.has_bold = True
        except FileNotFoundError:
            self.has_bold = False

    def header(self):
        self.set_font("Korean", "", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, self.title_text, align="C")
        self.ln(8)

    def footer(self):
        self.set_y(-12)
        self.set_font("Korean", "", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, f"- {self.page_no()} -", align="C")

    def add_comparison_page(self, page_num: int, image_path: str,
                            translated_text: str, page_style: dict = None):
        """왼쪽: 원본 이미지, 오른쪽: 한국어 번역"""
        self.add_page()

        page_width = self.w - self.l_margin - self.r_margin
        half_width = page_width / 2 - 5
        content_top = self.get_y()

        # --- 왼쪽: 원본 PDF 이미지 ---
        left_x = self.l_margin

        # 라벨
        self.set_xy(left_x, content_top)
        style = "B" if self.has_bold else ""
        self.set_font("Korean", style, 9)
        self.set_text_color(100, 100, 100)
        self.cell(half_width, 6, f"[{self._label_original}] p.{page_num}", align="C")
        self.ln(8)

        # 이미지 배치
        img_y = self.get_y()
        if os.path.exists(image_path):
            # 이미지 비율 유지하며 영역에 맞추기
            self.image(image_path, x=left_x, y=img_y, w=half_width)

        # --- 오른쪽: 한국어 번역 ---
        right_x = self.l_margin + half_width + 10

        # 구분선
        line_x = self.l_margin + half_width + 5
        self.set_draw_color(200, 200, 200)
        self.line(line_x, content_top, line_x, self.h - 15)

        # 라벨
        self.set_xy(right_x, content_top)
        self.set_font("Korean", style, 9)
        self.set_text_color(100, 100, 100)
        self.cell(half_width, 6, f"[{self._label_translated}] p.{page_num}", align="C")

        # 번역 텍스트
        self.set_xy(right_x, content_top + 10)

        # Style defaults
        default_color = (40, 40, 40)
        default_size = 10
        is_bold = False

        if page_style and "dominant" in page_style:
            dom = page_style["dominant"]
            default_color = tuple(dom.get("color_rgb", [40, 40, 40]))
            default_size = SIZE_CLASS_TO_PT.get(
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
                best_score = 0
                for hint, sb_style in special_styles.items():
                    score = SequenceMatcher(None, para[:30], hint).ratio()
                    if score > FUZZY_MATCH_THRESHOLD and score > best_score:
                        best_score = score
                        matched_style = sb_style

            if matched_style:
                ms_color = tuple(matched_style.get("color_rgb", default_color))
                ms_size = SIZE_CLASS_TO_PT.get(
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


def generate_comparison_pdf(
    original_pdf: str,
    translations: list[dict],
    output_path: str,
    page_range: tuple[int, int] = None,
    lang_profile: dict = None,
):
    """원본/번역 대조 PDF를 생성합니다."""

    # 페이지 범위 결정
    if page_range:
        pages = list(range(page_range[0], page_range[1] + 1))
    else:
        doc = fitz.open(original_pdf)
        pages = list(range(1, len(doc) + 1))
        doc.close()

    # 원본 PDF 페이지 이미지 추출
    print(f"🖼️ 원본 PDF 페이지 이미지 추출 중...")
    images = extract_page_images(original_pdf, pages)
    print(f"   {len(images)}페이지 이미지 추출 완료")

    # 번역 텍스트를 페이지별로 직접 매핑
    trans_by_page = {t["page"]: t for t in translations}
    pages_with_images = sorted(images.keys())

    # PDF 생성
    pdf = ComparisonPDF(lang_profile=lang_profile)
    pdf.set_auto_page_break(auto=False)

    for page_num in pages_with_images:
        entry = trans_by_page.get(page_num, {"translated": "(번역 없음)"})
        page_text = entry.get("translated", "(번역 없음)") if isinstance(entry, dict) else entry
        page_style = entry.get("page_style") if isinstance(entry, dict) else None
        pdf.add_comparison_page(page_num, images[page_num], page_text, page_style)

    # 저장
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))

    # 임시 이미지 정리
    for img_path in images.values():
        try:
            os.remove(img_path)
        except OSError:
            pass

    print(f"\n✅ 대조 PDF 생성 완료: {out}")
    print(f"   📄 {pdf.page_no()}페이지 (가로 A4, 원본/번역 나란히)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="원본/번역 대조 PDF 생성")
    parser.add_argument("--original", "-O", required=True, help="원본 일본어 PDF")
    parser.add_argument("--translation", "-T", required=True, help="번역 결과 JSON")
    parser.add_argument("--output", "-o", default="./translated/대조본.pdf", help="출력 PDF")
    parser.add_argument("--pages", "-p", help="페이지 범위 (예: 10-11)")
    parser.add_argument("--lang", default=None, help="언어 프로파일 (예: ja-en, ja-de)")
    parser.add_argument("--dpi", type=int, default=150, help="이미지 해상도 (기본: 150)")

    args = parser.parse_args()

    with open(args.translation, "r", encoding="utf-8") as f:
        translations = json.load(f)

    page_range = None
    if args.pages:
        parts = args.pages.split("-")
        page_range = (int(parts[0]), int(parts[1]) if len(parts) > 1 else int(parts[0]))

    # 언어 프로파일 로드
    lang_profile = None
    if args.lang:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from translate_pipeline import load_lang_profile
        lang_profile = load_lang_profile(args.lang)

    generate_comparison_pdf(args.original, translations, args.output, page_range, lang_profile)
