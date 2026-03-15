#!/usr/bin/env python3
"""
NAVI-Translate: 원문/번역 페이지별 대조 뷰어 (CLI)

사용법:
  # 전체 대조
  python compare.py -i translated/test_p10-11.json

  # 특정 청크만
  python compare.py -i translated/test_p10-11.json --chunk 1

  # 마크다운 파일로 내보내기
  python compare.py -i translated/test_p10-11.json --export comparison.md
"""
import json
import argparse
import textwrap
from pathlib import Path


def display_comparison(translations: list[dict], chunk_index: int = None, width: int = 80):
    """원문/번역을 나란히 대조 표시합니다."""
    items = translations
    if chunk_index:
        items = [t for t in translations if t["chunk_index"] == chunk_index]
    
    for t in items:
        idx = t["chunk_index"]
        original = t["original"]
        translated = t["translated"]
        time_s = t.get("time_seconds", 0)
        tok_s = t.get("tokens_per_sec", 0)
        
        print(f"\n{'━'*width}")
        print(f"  📖 청크 {idx}  |  ⏱️ {time_s}초  |  ⚡ {tok_s} tok/s")
        print(f"{'━'*width}")
        
        # 원문
        print(f"\n{'─'*width}")
        print(f"  🇯🇵 원문 ({len(original)}자)")
        print(f"{'─'*width}")
        for line in original.split('\n'):
            if line.strip():
                wrapped = textwrap.fill(line.strip(), width=width-4)
                for wl in wrapped.split('\n'):
                    print(f"  {wl}")
        
        # 번역
        print(f"\n{'─'*width}")
        print(f"  🇰🇷 번역 ({len(translated)}자)")
        print(f"{'─'*width}")
        for line in translated.split('\n'):
            if line.strip():
                wrapped = textwrap.fill(line.strip(), width=width-4)
                for wl in wrapped.split('\n'):
                    print(f"  {wl}")
        
        print()


def export_markdown(translations: list[dict], output_path: str):
    """원문/번역 대조를 마크다운 파일로 내보냅니다."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 후아후아의 법칙 — 원문/번역 대조\n\n")
        f.write(f"총 {len(translations)}개 청크\n\n")
        
        for t in translations:
            idx = t["chunk_index"]
            f.write(f"---\n\n")
            f.write(f"## 청크 {idx}\n\n")
            
            f.write(f"### 🇯🇵 원문\n\n")
            f.write(t["original"])
            f.write("\n\n")
            
            f.write(f"### 🇰🇷 번역\n\n")
            f.write(t["translated"])
            f.write("\n\n")
    
    print(f"✅ 마크다운 대조 파일 저장: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="원문/번역 대조 뷰어")
    parser.add_argument("--input", "-i", required=True, help="번역 결과 JSON 파일")
    parser.add_argument("--chunk", "-c", type=int, help="특정 청크 번호만 표시")
    parser.add_argument("--export", "-e", help="마크다운 파일로 내보내기")
    parser.add_argument("--width", "-w", type=int, default=80, help="출력 너비")
    
    args = parser.parse_args()
    
    with open(args.input, "r", encoding="utf-8") as f:
        translations = json.load(f)
    
    if args.export:
        export_markdown(translations, args.export)
    else:
        display_comparison(translations, args.chunk, args.width)
