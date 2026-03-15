#!/usr/bin/env python3
"""
NAVI-Translate: 한국어 번역 PDF 생성기
번역된 텍스트를 깔끔한 가로쓰기 한국어 PDF로 변환합니다.

사용법:
  python src/generate_pdf.py -i translated/output.json -o translated/후아후아_번역.pdf
  python src/generate_pdf.py -i translated/output.json --dual  # 원문/번역 대조 PDF
"""
import json
import argparse
import os
from pathlib import Path
from fpdf import FPDF


# ============================================================
# 한국어 폰트 탐색
# ============================================================

FONT_SEARCH_PATHS = [
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
]

FONT_CANDIDATES = {
    "regular": ["NanumSquare_acR.ttf", "NanumSquareR.ttf", "NanumGothic.ttf", "AppleGothic.ttf"],
    "bold": ["NanumSquareEB.ttf", "NanumSquare_acB.ttf", "NanumGothicBold.ttf"],
}


def find_font(style: str = "regular") -> str:
    """시스템에서 한국어 폰트를 찾습니다."""
    for candidate in FONT_CANDIDATES.get(style, FONT_CANDIDATES["regular"]):
        for search_dir in FONT_SEARCH_PATHS:
            path = os.path.join(search_dir, candidate)
            if os.path.exists(path):
                return path
    raise FileNotFoundError(
        f"한국어 폰트를 찾을 수 없습니다. "
        f"나눔스퀘어 폰트를 ~/Library/Fonts/에 설치해주세요."
    )


# ============================================================
# PDF 생성기
# ============================================================

class KoreanPDF(FPDF):
    """한국어 지원 PDF 클래스"""
    
    def __init__(self, title: str = "후아후아의 법칙"):
        super().__init__()
        self.title_text = title
        self._setup_fonts()
    
    def _setup_fonts(self):
        """한국어 폰트를 등록합니다."""
        regular_path = find_font("regular")
        self.add_font("Korean", "", regular_path)
        
        try:
            bold_path = find_font("bold")
            self.add_font("Korean", "B", bold_path)
            self.has_bold = True
        except FileNotFoundError:
            self.has_bold = False
    
    def header(self):
        """페이지 헤더"""
        self.set_font("Korean", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, self.title_text, align="C")
        self.ln(12)
    
    def footer(self):
        """페이지 푸터"""
        self.set_y(-15)
        self.set_font("Korean", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"- {self.page_no()} -", align="C")
    
    def add_title_page(self, title: str, subtitle: str = "", author: str = ""):
        """표지 페이지를 추가합니다."""
        self.add_page()
        self.ln(60)
        
        # 제목
        style = "B" if self.has_bold else ""
        self.set_font("Korean", style, 28)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 14, title, align="C")
        
        if subtitle:
            self.ln(8)
            self.set_font("Korean", "", 14)
            self.set_text_color(100, 100, 100)
            self.multi_cell(0, 8, subtitle, align="C")
        
        if author:
            self.ln(20)
            self.set_font("Korean", "", 12)
            self.set_text_color(80, 80, 80)
            self.multi_cell(0, 8, author, align="C")
        
        # 번역 정보
        self.ln(40)
        self.set_font("Korean", "", 10)
        self.set_text_color(150, 150, 150)
        self.multi_cell(0, 6, "NAVI-Translate 로컬 번역 (Qwen2.5-14B)", align="C")
    
    def add_chapter_title(self, title: str):
        """장 제목을 추가합니다."""
        self.ln(8)
        style = "B" if self.has_bold else ""
        self.set_font("Korean", style, 16)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 10, title)
        self.ln(4)
        # 구분선
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)
    
    def add_section_title(self, title: str):
        """소제목을 추가합니다."""
        self.ln(4)
        style = "B" if self.has_bold else ""
        self.set_font("Korean", style, 13)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 8, title)
        self.ln(2)
    
    def add_body_text(self, text: str):
        """본문 텍스트를 추가합니다."""
        self.set_font("Korean", "", 11)
        self.set_text_color(40, 40, 40)
        
        paragraphs = text.split('\n')
        for para in paragraphs:
            para = para.strip()
            if not para:
                self.ln(4)
                continue
            
            # 인용구 감지 (큰따옴표로 시작)
            if para.startswith('"') or para.startswith('"') or para.startswith('「'):
                self.set_text_color(80, 60, 120)
                self.set_font("Korean", "", 11)
                self.multi_cell(0, 7, f"  {para}", align="L")
                self.set_text_color(40, 40, 40)
            else:
                self.multi_cell(0, 7, para, align="L")
            self.ln(2)
    
    def add_original_text(self, text: str):
        """원문 텍스트를 추가합니다 (대조용, 회색 작은 글씨)."""
        self.set_font("Korean", "", 8)
        self.set_text_color(160, 160, 160)
        self.multi_cell(0, 5, f"[원문] {text[:200]}...")
        self.ln(4)


def parse_indesign_tags(text: str) -> list[dict]:
    """인디자인 태그를 파싱하여 구조화된 콘텐츠로 변환합니다."""
    blocks = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('@') and line.endswith('@'):
            blocks.append({"type": "part_title", "text": line.strip('@')})
        elif line.startswith('#') and not line.startswith('##'):
            blocks.append({"type": "chapter_title", "text": line.strip('#').strip()})
        elif line.startswith('##') and not line.startswith('###'):
            blocks.append({"type": "section_title", "text": line.strip('#').strip()})
        elif line.startswith('$') and line.endswith('$'):
            blocks.append({"type": "quote", "text": line.strip('$').strip()})
        else:
            blocks.append({"type": "body", "text": line})
    
    return blocks


def generate_translation_pdf(translations: list[dict], output_path: str, 
                              title: str = "후아후아의 법칙",
                              dual: bool = False):
    """번역 결과를 PDF로 생성합니다."""
    pdf = KoreanPDF(title=title)
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # 표지
    pdf.add_title_page(
        title=title,
        subtitle="사이토 히토리 · 시바무라 에미코",
        author="번역: NAVI-Translate (나비스쿨)"
    )
    
    # 본문
    for t in translations:
        pdf.add_page()
        
        translated = t.get("translated", "")
        blocks = parse_indesign_tags(translated)
        
        for block in blocks:
            if block["type"] == "part_title":
                pdf.add_chapter_title(block["text"])
            elif block["type"] == "chapter_title":
                pdf.add_chapter_title(block["text"])
            elif block["type"] == "section_title":
                pdf.add_section_title(block["text"])
            else:
                pdf.add_body_text(block["text"])
        
        # 대조 모드: 원문도 표시
        if dual and "original" in t:
            pdf.ln(8)
            pdf.set_draw_color(220, 220, 220)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
            pdf.add_original_text(t["original"])
    
    # 저장
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    print(f"✅ PDF 생성 완료: {out}")
    print(f"   📄 {pdf.page_no()}페이지")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NAVI-Translate: 한국어 번역 PDF 생성기")
    parser.add_argument("--input", "-i", required=True, help="번역 결과 JSON 파일")
    parser.add_argument("--output", "-o", default="./translated/후아후아_번역.pdf", help="출력 PDF 경로")
    parser.add_argument("--title", "-t", default="후아후아의 법칙", help="책 제목")
    parser.add_argument("--dual", "-d", action="store_true", help="원문/번역 대조 모드")
    
    args = parser.parse_args()
    
    with open(args.input, "r", encoding="utf-8") as f:
        translations = json.load(f)
    
    print(f"📖 PDF 생성 시작: {len(translations)}개 청크")
    generate_translation_pdf(translations, args.output, args.title, args.dual)
