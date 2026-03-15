#!/usr/bin/env python3
"""
NAVI-Translate: PDF 텍스트 추출기
이미 OCR 처리된 PDF에서 일본어 텍스트를 페이지별로 추출합니다.
"""
import fitz  # PyMuPDF
import json
import argparse
import re
from pathlib import Path


def extract_text_from_pdf(pdf_path: str, start_page: int = None, end_page: int = None) -> list[dict]:
    """
    OCR 처리된 PDF에서 페이지별 텍스트를 추출합니다.
    
    Args:
        pdf_path: PDF 파일 경로
        start_page: 시작 페이지 (1-indexed, None이면 처음부터)
        end_page: 끝 페이지 (1-indexed, None이면 끝까지)
    
    Returns:
        [{"page": 1, "text": "..."}, ...]
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    # 1-indexed → 0-indexed 변환
    start_idx = (start_page - 1) if start_page else 0
    end_idx = end_page if end_page else total_pages
    
    # 범위 클램핑
    start_idx = max(0, min(start_idx, total_pages - 1))
    end_idx = max(start_idx + 1, min(end_idx, total_pages))
    
    pages = []
    for i in range(start_idx, end_idx):
        page = doc[i]
        text = page.get_text("text")
        
        # 기본 정리: 연속 공백 제거, 빈 줄 정리
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        if text:  # 빈 페이지 스킵
            pages.append({
                "page": i + 1,
                "text": text,
                "char_count": len(text)
            })
    
    doc.close()
    return pages


def save_pages(pages: list[dict], output_dir: str):
    """페이지별 텍스트를 개별 파일과 전체 JSON으로 저장합니다."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # 전체 JSON 저장
    json_path = out_path / "extracted_pages.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
    
    # 전체 텍스트 하나로 합치기
    full_text_path = out_path / "full_text_jp.txt"
    with open(full_text_path, "w", encoding="utf-8") as f:
        for p in pages:
            f.write(f"--- ページ {p['page']} ---\n")
            f.write(p["text"])
            f.write("\n\n")
    
    return json_path, full_text_path


def print_summary(pages: list[dict], pdf_path: str):
    """추출 결과 요약을 출력합니다."""
    total_chars = sum(p["char_count"] for p in pages)
    print(f"\n{'='*50}")
    print(f"📄 PDF: {pdf_path}")
    print(f"📃 추출된 페이지: {len(pages)}개")
    print(f"📝 총 글자 수: {total_chars:,}자")
    print(f"📊 페이지당 평균: {total_chars // len(pages) if pages else 0}자")
    print(f"{'='*50}")
    
    # 처음 3페이지 미리보기
    preview_count = min(3, len(pages))
    for p in pages[:preview_count]:
        preview = p["text"][:200].replace("\n", " ")
        print(f"\n[p.{p['page']}] ({p['char_count']}자) {preview}...")
    
    if len(pages) > preview_count:
        print(f"\n... 외 {len(pages) - preview_count}페이지")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NAVI-Translate: PDF 텍스트 추출기")
    parser.add_argument("--input", "-i", required=True, help="OCR PDF 파일 경로")
    parser.add_argument("--output", "-o", default="./extracted", help="출력 디렉터리 (기본: ./extracted)")
    parser.add_argument("--pages", "-p", help="페이지 범위 (예: 1-10, 5-20)")
    
    args = parser.parse_args()
    
    start_page = end_page = None
    if args.pages:
        parts = args.pages.split("-")
        start_page = int(parts[0])
        end_page = int(parts[1]) if len(parts) > 1 else start_page
    
    print(f"🔍 PDF 텍스트 추출 시작: {args.input}")
    pages = extract_text_from_pdf(args.input, start_page, end_page)
    
    if not pages:
        print("⚠️ 추출된 텍스트가 없습니다. PDF에 OCR 레이어가 있는지 확인해주세요.")
    else:
        json_path, full_path = save_pages(pages, args.output)
        print_summary(pages, args.input)
        print(f"\n✅ 저장 완료:")
        print(f"   JSON: {json_path}")
        print(f"   전체: {full_path}")
