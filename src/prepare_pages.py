#!/usr/bin/env python3
"""
NAVI-Translate: 안티그래비티 번역 준비 스크립트
PDF 페이지를 이미지로 추출하여 안티그래비티가 직접 볼 수 있도록 합니다.

사용법:
  python src/prepare_pages.py -i data/pdf/후아후아.pdf --pages 1-10
"""
import json
import argparse
import os
import re
import sys
from pathlib import Path


def extract_text_metadata(doc, pages, small_threshold: float = 9.0) -> dict:
    """
    PyMuPDF의 dict 모드로 소형 텍스트 및 가로 텍스트 메타데이터를 추출합니다.

    Args:
        doc: fitz.Document 객체
        pages: 페이지 번호 range (1-based)
        small_threshold: 소형 텍스트 기준 폰트 크기 (pt)

    Returns:
        {page_num_str: {"full_text": ..., "small_texts": [...], "horizontal_texts": [...]}}
    """
    result = {}
    for pn in pages:
        idx = pn - 1
        if not (0 <= idx < len(doc)):
            continue

        page = doc[idx]
        # 기본 전체 텍스트 (공백 제거)
        full_text = re.sub(r'\s+', '', page.get_text("text").strip())

        small_texts = []
        horizontal_texts = []

        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # 텍스트 블록만
                continue
            for line in block.get("lines", []):
                # 텍스트 방향: dir = (cos, sin)
                line_dir = line.get("dir", (1, 0))
                is_horizontal = abs(line_dir[0]) > abs(line_dir[1])

                for span in line.get("spans", []):
                    span_text = re.sub(r'\s+', '', span.get("text", ""))
                    if len(span_text) <= 1:
                        continue
                    # 숫자만으로 된 텍스트 스킵 (페이지 번호 등)
                    if re.fullmatch(r'\d+', span_text):
                        continue

                    font_size = span.get("size", 12.0)

                    if font_size < small_threshold and span_text not in small_texts:
                        small_texts.append(span_text)

                    if is_horizontal and span_text not in horizontal_texts:
                        horizontal_texts.append(span_text)

        result[str(pn)] = {
            "full_text": full_text,
            "small_texts": small_texts,
            "horizontal_texts": horizontal_texts,
        }

    return result


def prepare_images(pdf_path: str, page_range: str = None, dpi: int = 150, output_dir: str = None):
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

    # 텍스트 레이어 추출 (정합성 검증용 ground truth + 소형/가로 텍스트 메타데이터)
    page_texts = extract_text_metadata(doc, pages)

    texts_path = os.path.join(out_dir, "page_texts.json")
    with open(texts_path, "w", encoding="utf-8") as f:
        json.dump(page_texts, f, ensure_ascii=False, indent=2)

    doc.close()
    print(f"\n✅ {len(list(pages))}페이지 이미지 추출 완료: {out_dir}/")
    print(f"📝 페이지별 텍스트 추출: {texts_path}")
    print(f"💡 안티그래비티가 Read 도구로 각 이미지를 직접 보고 번역합니다")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="안티그래비티 번역 준비 — PDF→이미지 추출")
    parser.add_argument("--input", "-i", required=True, help="PDF 파일 경로")
    parser.add_argument("--pages", "-p", help="페이지 범위 (예: 1-10)")
    parser.add_argument("--dpi", type=int, default=150, help="이미지 해상도 (기본: 150, 작은 글씨 검증: 200)")
    parser.add_argument("--output-dir", "-o", help="출력 디렉토리 (기본: /tmp/antigravity_pages/)")
    args = parser.parse_args()
    
    prepare_images(args.input, args.pages, args.dpi, args.output_dir)
