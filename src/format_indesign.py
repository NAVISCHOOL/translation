#!/usr/bin/env python3
"""
NAVI-Translate: InDesign 태그 포매터
JSON 번역 결과물 → 인디자인 조판용 태그 텍스트 변환

사용법:
  python src/format_indesign.py \
    --input translated/antigravity/후아후아_v2/pages_1-5.json \
    --output translated/antigravity/후아후아_v2/indesign_ready_p1-5.txt

태그 규칙:
  @부 명칭@          — 편(부) 구분
  #장 제목#          — 장 시작 (각 장 1회)
  $"인용구" - 저자$  — 에피그래프 (장 제목 아래)
  ##소제목           — 1차 중간 제목
  ###세부제목        — 2차 세부 제목
  • 항목              — 불릿 리스트
  (본문은 태그 없이 줄바꿈으로만 구분)
"""
import argparse
import json
import re
import sys
from pathlib import Path


# ============================================================
# 태그 패턴 감지 규칙
# ============================================================

# 부(편) 패턴: "제1부", "1부", "第1部" 등
PART_PATTERN = re.compile(
    r'^(?:제?\s*\d+\s*부|[IVX]+부)\s*[:\s]*(.*)',
    re.IGNORECASE
)

# 장 패턴: "제1장", "서장", "제N장" 등
CHAPTER_PATTERN = re.compile(
    r'^(?:서장|제?\s*\d+\s*장)\s*[:\s]*(.*)',
    re.IGNORECASE
)

# Q&A 패턴
QA_PATTERN = re.compile(r'^Q\d+\s')

# 목차 패턴: 제목 뒤에 숫자(페이지번호)가 붙는 구조
TOC_LINE_PATTERN = re.compile(r'^.+\s+\d{1,3}\s*$')

# 구조 탐지용 키워드
STRUCTURAL_KEYWORDS = {
    "머리말", "맺음말", "후기", "서장", "목차",
    "대담", "대화", "칼럼",
}


def classify_line(line: str, prev_tag: str = "") -> str:
    """번역 텍스트의 한 줄을 분류하여 태그를 반환합니다.

    Returns:
        태그 종류: 'part', 'chapter', 'subheading', 'sub2heading',
                  'epigraph', 'bullet', 'body', 'toc'
    """
    stripped = line.strip()
    if not stripped:
        return "empty"

    # 불릿 리스트
    if stripped.startswith("•") or stripped.startswith("・"):
        return "bullet"

    # 부(편)
    if PART_PATTERN.match(stripped):
        return "part"

    # 장
    if CHAPTER_PATTERN.match(stripped):
        return "chapter"

    # 목차 줄 (제목 + 페이지번호)
    if TOC_LINE_PATTERN.match(stripped) and len(stripped) < 80:
        return "toc"

    # 에피그래프: 장 제목 바로 다음에 오는 인용구
    if prev_tag == "chapter" and (stripped.startswith("「") or stripped.startswith('"')):
        return "epigraph"

    # 구조 키워드 (짧은 줄)
    for kw in STRUCTURAL_KEYWORDS:
        if stripped == kw or stripped.startswith(kw + "\n"):
            return "chapter"

    # 짧고 마침표 없는 줄 → 소제목 후보
    if len(stripped) < 40 and not stripped.endswith(('.', '。', '!', '?', '요', '다', '까')):
        return "subheading"

    return "body"


def format_tagged_line(line: str, tag: str) -> str:
    """분류된 태그에 따라 인디자인 태그를 적용합니다."""
    stripped = line.strip()

    if tag == "part":
        return f"@{stripped}@"

    if tag == "chapter":
        return f"#{stripped}#"

    if tag == "epigraph":
        return f"${stripped}$"

    if tag == "subheading":
        return f"##{stripped}"

    if tag == "sub2heading":
        return f"###{stripped}"

    if tag == "bullet":
        # 이미 •로 시작하면 그대로
        if stripped.startswith("•"):
            return stripped
        return f"• {stripped.lstrip('・').strip()}"

    if tag == "toc":
        return stripped  # 목차는 태그 없이 그대로

    # body, empty
    return stripped


def format_indesign(pages: list[dict], include_page_markers: bool = False) -> str:
    """JSON 번역 결과를 인디자인 태그 포맷으로 변환합니다.

    Args:
        pages: [{page: int, original: str, translated: str}, ...]
        include_page_markers: True면 페이지 경계 주석 포함

    Returns:
        인디자인 태그가 적용된 텍스트
    """
    output_lines = []
    prev_tag = ""

    for entry in sorted(pages, key=lambda x: x["page"]):
        translated = entry.get("translated", "")
        if not translated.strip():
            continue

        if include_page_markers:
            output_lines.append(f"<!-- page {entry['page']} -->")

        lines = translated.split("\n")
        for line in lines:
            if not line.strip():
                output_lines.append("")  # 빈 줄 보존 (단락 구분)
                continue

            tag = classify_line(line, prev_tag)
            formatted = format_tagged_line(line, tag)
            output_lines.append(formatted)
            prev_tag = tag

    return "\n".join(output_lines)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="NAVI-Translate InDesign 태그 포매터",
    )
    parser.add_argument("--input", "-i", required=True,
                        help="번역 JSON 파일 경로")
    parser.add_argument("--output", "-o",
                        help="출력 txt 파일 경로 (기본: input과 같은 디렉토리)")
    parser.add_argument("--page-markers", action="store_true",
                        help="페이지 경계 주석 포함")

    args = parser.parse_args()

    # JSON 로드
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    # 변환
    result = format_indesign(pages, include_page_markers=args.page_markers)

    # 출력 경로
    if args.output:
        output_path = Path(args.output)
    else:
        # 입력 파일 이름에서 자동 생성
        stem = input_path.stem  # e.g. "pages_1-5"
        output_path = input_path.parent / f"indesign_ready_{stem}.txt"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"✅ InDesign 태그 적용 완료: {output_path}")
    print(f"   {len(pages)}페이지, {len(result.splitlines())}줄")


if __name__ == "__main__":
    main()
