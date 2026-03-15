#!/usr/bin/env python3
"""
NAVI-Translate: 안티그래비티 번역 준비 스크립트
PDF 페이지를 이미지로 추출하여 안티그래비티가 직접 볼 수 있도록 합니다.

사용법:
  # 이미지 모드 (안티그래비티용) - PDF에서 직접 이미지 추출
  python src/prepare_pages.py -i data/pdf/후아후아.pdf --pages 1-10 --mode image

  # 텍스트 모드 (기존) - OCR 텍스트 전처리
  python src/prepare_pages.py -i extracted/extracted_pages.json --pages 1-10 --mode text
"""
import json
import argparse
import os
import re
import sys
from pathlib import Path


def prepare_images(pdf_path: str, page_range: str = None, dpi: int = 200, output_dir: str = None):
    """PDF 페이지를 PNG 이미지로 추출합니다."""
    import fitz
    
    doc = fitz.open(pdf_path)
    out_dir = output_dir or "/tmp/antigravity_pages"
    os.makedirs(out_dir, exist_ok=True)
    
    # 페이지 범위
    if page_range:
        parts = page_range.split("-")
        start_p = int(parts[0])
        end_p = int(parts[1]) if len(parts) > 1 else start_p
        pages = range(start_p, end_p + 1)
    else:
        pages = range(1, len(doc) + 1)
    
    for pn in pages:
        idx = pn - 1
        if 0 <= idx < len(doc):
            page = doc[idx]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_path = os.path.join(out_dir, f"page_{pn:02d}.png")
            pix.save(img_path)
            print(f"  p.{pn:>2} → {img_path}")
    
    # 텍스트 레이어 추출 (정합성 검증용 ground truth)
    page_texts = {}
    for pn in pages:
        idx = pn - 1
        if 0 <= idx < len(doc):
            page = doc[idx]
            text = page.get_text("text").strip()
            # 공백/줄바꿈 정리 (세로쓰기 PDF 대응)
            text_clean = re.sub(r'\s+', '', text)
            page_texts[str(pn)] = text_clean

    texts_path = os.path.join(out_dir, "page_texts.json")
    with open(texts_path, "w", encoding="utf-8") as f:
        json.dump(page_texts, f, ensure_ascii=False, indent=2)
    
    doc.close()
    print(f"\n✅ {len(list(pages))}페이지 이미지 추출 완료: {out_dir}/")
    print(f"📝 페이지별 텍스트 추출: {texts_path}")
    print(f"💡 안티그래비티가 view_file로 각 이미지를 직접 보고 번역합니다")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="안티그래비티 번역 준비 — PDF→이미지 추출")
    parser.add_argument("--input", "-i", required=True, help="PDF 파일 경로")
    parser.add_argument("--pages", "-p", help="페이지 범위 (예: 1-10)")
    parser.add_argument("--dpi", type=int, default=150, help="이미지 해상도 (기본: 150, 고해상도: 200)")
    parser.add_argument("--output-dir", "-o", help="출력 디렉토리 (기본: /tmp/antigravity_pages/)")
    args = parser.parse_args()
    
    prepare_images(args.input, args.pages, args.dpi, args.output_dir)
