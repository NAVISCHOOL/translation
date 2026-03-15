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
import sys
from pathlib import Path


def prepare_images(pdf_path: str, page_range: str = None, dpi: int = 200):
    """PDF 페이지를 PNG 이미지로 추출합니다."""
    import fitz
    
    doc = fitz.open(pdf_path)
    out_dir = "/tmp/antigravity_pages"
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
    
    doc.close()
    print(f"\n✅ {len(list(pages))}페이지 이미지 추출 완료: {out_dir}/")
    print(f"💡 안티그래비티가 view_file로 각 이미지를 직접 보고 번역합니다")


def prepare_text(input_path: str, page_range: str = None):
    """OCR 텍스트를 전처리합니다. (기존 방식)"""
    sys.path.insert(0, str(Path(__file__).parent))
    from translate import preprocess_vertical_ocr
    
    with open(input_path, "r", encoding="utf-8") as f:
        all_pages = json.load(f)
    
    if page_range:
        parts = page_range.split("-")
        start_p = int(parts[0])
        end_p = int(parts[1]) if len(parts) > 1 else start_p
        pages = [p for p in all_pages if start_p <= p["page"] <= end_p]
    else:
        pages = all_pages
    
    results = []
    for p in pages:
        cleaned = preprocess_vertical_ocr(p["text"])
        results.append({
            "page": p["page"],
            "original_chars": p.get("char_count", len(p["text"])),
            "cleaned_chars": len(cleaned.strip()),
            "text": cleaned.strip()
        })
        print(f"  p.{p['page']:>2}: {len(cleaned.strip()):>4}자")
    
    output = "/tmp/antigravity_translate_input.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {len(results)}페이지 텍스트 준비 완료: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="안티그래비티 번역 준비")
    parser.add_argument("--input", "-i", required=True, help="PDF 파일 또는 추출 JSON")
    parser.add_argument("--pages", "-p", help="페이지 범위 (예: 1-10)")
    parser.add_argument("--mode", "-m", default="image", choices=["image", "text"],
                        help="image: PDF→이미지 (권장), text: OCR 텍스트 전처리")
    parser.add_argument("--dpi", type=int, default=200, help="이미지 해상도 (기본: 200)")
    args = parser.parse_args()
    
    if args.mode == "image":
        prepare_images(args.input, args.pages, args.dpi)
    else:
        prepare_text(args.input, args.pages)
