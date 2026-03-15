#!/usr/bin/env python3
"""
NAVI-Translate: 안티그래비티 번역 결과 저장 스크립트
안티그래비티가 번역한 결과를 표준 JSON/TXT 형식으로 저장합니다.

사용법 (안티그래비티가 실행):
  python src/save_translation.py --pages 10-20 --output translated/antigravity_output.json
  
  stdin으로 JSON 데이터를 받습니다:
  [{"page": 10, "translated": "번역된 텍스트..."}, ...]
"""
import json
import argparse
import sys
from pathlib import Path


def save_translations(translations: list[dict], output_path: str):
    """번역 결과를 표준 형식으로 저장합니다."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    
    # JSON 저장 (원문/번역 대조)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)
    
    # TXT 저장 (번역만)
    txt_path = out.with_suffix(".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for t in translations:
            f.write(f"--- p.{t['page']} ---\n")
            f.write(t.get("translated", ""))
            f.write("\n\n")
    
    print(f"✅ 번역 저장 완료:")
    print(f"   JSON: {out}")
    print(f"   TXT:  {txt_path}")
    print(f"   총 {len(translations)}페이지")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="안티그래비티 번역 결과 저장")
    parser.add_argument("--output", "-o", default="./translated/antigravity_output.json")
    parser.add_argument("--input-file", "-f", help="번역 결과 JSON 파일 경로")
    args = parser.parse_args()
    
    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            translations = json.load(f)
    else:
        # stdin에서 읽기
        translations = json.load(sys.stdin)
    
    save_translations(translations, args.output)
