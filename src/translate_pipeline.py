#!/usr/bin/env python3
"""
NAVI-Translate: 번역 파이프라인 자동화
MD→JSON 변환 + ANTI-JAPANESE 검증 + 대조 PDF 생성 + 세션 로그

사용법:
  # 올인원 빌드 (MD→JSON→검증→대조PDF→로그)
  python src/translate_pipeline.py build \
    --input /tmp/translation_draft.md \
    --pdf data/pdf/후아후아_20251210-part-1-ocr.pdf \
    --pages 1-10 \
    --output translated/antigravity/pages_1-10.json

  # 기존 JSON 검증만
  python src/translate_pipeline.py validate \
    --json translated/antigravity/pages_1-10.json \
    --pages 1-10
"""
import argparse
import json
import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


# ============================================================
# 1. MD 파서 — 에이전트가 작성한 마크다운을 구조화 데이터로 변환
# ============================================================

def parse_translation_md(md_path: str) -> list[dict]:
    """
    마크다운 번역 파일을 파싱합니다.

    형식:
        ## page 1
        original: 일본어 원문
        (여러 줄 가능)
        translated: 한국어 번역
        (여러 줄 가능)
    """
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    pages = []
    # ## page N 으로 분할
    blocks = re.split(r'^## page\s+(\d+)\s*$', content, flags=re.MULTILINE)

    # blocks[0]은 첫 ## page 이전 (빈 문자열 또는 헤더)
    # blocks[1] = page_num, blocks[2] = content, blocks[3] = page_num, ...
    i = 1
    while i < len(blocks) - 1:
        page_num = int(blocks[i].strip())
        page_content = blocks[i + 1].strip()

        # original: / translated: 분리
        original = ""
        translated = ""

        # original: 과 translated: 경계를 찾음
        orig_match = re.search(r'^original:\s*', page_content, re.MULTILINE)
        trans_match = re.search(r'^translated:\s*', page_content, re.MULTILINE)

        if orig_match and trans_match:
            orig_start = orig_match.end()
            trans_key_start = trans_match.start()
            trans_start = trans_match.end()

            original = page_content[orig_start:trans_key_start].strip()
            translated = page_content[trans_start:].strip()
        elif trans_match:
            # original 없이 translated만 있는 경우
            trans_start = trans_match.end()
            translated = page_content[trans_start:].strip()
        else:
            # 둘 다 없으면 전체를 translated로 간주
            translated = page_content

        pages.append({
            "page": page_num,
            "original": original,
            "translated": translated,
        })

        i += 2

    return sorted(pages, key=lambda x: x["page"])


# ============================================================
# 2. ANTI-JAPANESE 검증 — NAVI-Research ANTI-HALLUCINATION 패턴
# ============================================================

# 히라가나 + 카타카나 범위 (한자는 한국어에서도 사용하므로 제외)
JAPANESE_PATTERN = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\uFF66-\uFF9F]+')

# 글로서리에 등록된 용어는 예외 처리 (일본어 원문 키)
def load_glossary_exceptions() -> set[str]:
    """글로서리에 등록된 일본어 원어를 예외 목록으로 로드합니다."""
    glossary_path = PROJECT_ROOT / "config" / "glossary.json"
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)
        return set(glossary.values())  # 한국어 번역어는 허용
    return set()


def validate_translations(pages: list[dict], expected_range: tuple[int, int] = None, pdf_path: str = None) -> dict:
    """
    번역 결과를 다중 검증합니다.
    (NAVI-Research 7중 QA 패턴에서 영감)

    검증 항목:
    1. 일본어 잔존 감지 (히라가나/카타카나)
    2. 원문 완성도 (축약/요약 감지)
    3. 페이지간 연결성 (문장 끊김 감지)
    4. 용어집 일관성 (glossary.json 반영 확인)
    5. 페이지 누락 체크
    6. 페이지 정합성 (1:1 매칭) — PDF 텍스트 레이어 대조

    Returns:
        {"ok": bool, "errors": [...], "warnings": [...], "qa_summary": {...}}
    """
    errors = []
    warnings = []
    qa_scores = {}

    # ── 1. 일본어 잔존 + 빈 번역 ──
    jp_remnant_count = 0
    empty_count = 0
    for entry in pages:
        pn = entry["page"]
        text = entry.get("translated", "")

        if not text.strip():
            errors.append(f"p.{pn}: 번역 텍스트가 비어 있습니다")
            empty_count += 1
            continue

        matches = JAPANESE_PATTERN.findall(text)
        if matches:
            for m in matches:
                errors.append(f"p.{pn}: 일본어 잔존 감지: '{m}' → 한국어로 교체 필요")
            jp_remnant_count += len(matches)

    qa_scores["일본어_잔존"] = 0 if jp_remnant_count == 0 else jp_remnant_count

    # ── 2. 원문 완성도 검증 (축약 감지) ──
    MIN_CONTENT_LENGTH = 50
    truncated_pages = []
    for entry in pages:
        pn = entry["page"]
        orig = entry.get("original", "")
        trans = entry.get("translated", "")

        if len(trans) > 80 and len(orig) < MIN_CONTENT_LENGTH:
            warnings.append(f"p.{pn}: 원문이 너무 짧음 ({len(orig)}자) — 누락 가능성")
            truncated_pages.append(pn)

        if len(orig) > 0 and len(trans) > 50:
            ratio = len(orig) / len(trans)
            if ratio < 0.3:
                warnings.append(f"p.{pn}: 원문/번역 비율 이상 ({ratio:.0%}) — 원문 축약 의심")
                if pn not in truncated_pages:
                    truncated_pages.append(pn)

    qa_scores["원문_완성도"] = f"{len(truncated_pages)}건 의심"

    # ── 3. 페이지간 연결성 (문장 끊김 감지) ──
    broken_connections = []
    content_pages = [p for p in sorted(pages, key=lambda x: x["page"])
                     if len(p.get("original", "")) > 50]

    for i in range(len(content_pages) - 1):
        curr = content_pages[i]
        next_p = content_pages[i + 1]

        # 연속 페이지만 검사
        if next_p["page"] != curr["page"] + 1:
            continue

        curr_orig = curr.get("original", "")
        next_orig = next_p.get("original", "")

        # 현재 페이지가 문장 중간에 끊겼는지 (마침표/물음표/느낌표로 안 끝남)
        if curr_orig and not curr_orig.rstrip().endswith(("。", "！", "？", ")", "）", "」", "』", "…")):
            # 다음 페이지가 소문자나 조사로 시작하면 연결 끊김
            next_start = next_orig.lstrip()[:5] if next_orig else ""
            if next_start and not next_start[0].isupper():
                broken_connections.append(
                    f"p.{curr['page']}→p.{next_p['page']}: 문장 연결 끊김 의심 "
                    f"(끝: '...{curr_orig[-10:]}' → 시작: '{next_start}...')"
                )

    for bc in broken_connections:
        warnings.append(bc)
    qa_scores["페이지_연결성"] = f"{len(broken_connections)}건 끊김"

    # ── 4. 용어집 일관성 검증 ──
    glossary_path = PROJECT_ROOT / "config" / "glossary.json"
    glossary_issues = []
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)

        for entry in pages:
            pn = entry["page"]
            orig = entry.get("original", "")
            trans = entry.get("translated", "")

            for jp_term, kr_term in glossary.items():
                # 원문에 일본어 용어가 있는데 번역에 대응 한국어가 없으면
                if jp_term in orig and kr_term not in trans:
                    glossary_issues.append(
                        f"p.{pn}: '{jp_term}'→'{kr_term}' 미반영"
                    )

        for gi in glossary_issues[:10]:  # 최대 10개만 표시
            warnings.append(f"용어집: {gi}")
        if len(glossary_issues) > 10:
            warnings.append(f"용어집: ...외 {len(glossary_issues) - 10}건")

    qa_scores["용어집_일관성"] = f"{len(glossary_issues)}건 불일치"

    # ── 5. 페이지 누락 체크 ──
    if expected_range:
        expected_pages = set(range(expected_range[0], expected_range[1] + 1))
        actual_pages = {p["page"] for p in pages}
        missing = expected_pages - actual_pages
        if missing:
            errors.append(f"누락된 페이지: {sorted(missing)}")
        extra = actual_pages - expected_pages
        if extra:
            warnings.append(f"범위 외 페이지: {sorted(extra)}")

    # ── 6. 페이지 정합성 검증 (1:1 매칭) ──
    # ⚠️ PDF OCR 텍스트 레이어 품질이 낮을 수 있으므로:
    #   - 주요 기준: 글자수 비율 (OCR 품질 무관하게 대략적 길이는 맞음)
    #   - 보조 기준: SequenceMatcher 유사도 (참고용, OCR 노이즈 감안)
    alignment_issues = []
    if pdf_path and expected_range:
        try:
            import fitz
            from difflib import SequenceMatcher

            doc = fitz.open(pdf_path)
            for entry in pages:
                pn = entry["page"]
                idx = pn - 1
                if 0 <= idx < len(doc):
                    pdf_text = doc[idx].get_text("text").strip()
                    pdf_text_clean = re.sub(r'\s+', '', pdf_text)
                    orig_clean = re.sub(r'\s+', '', entry.get("original", ""))

                    if not pdf_text_clean or not orig_clean:
                        continue

                    pdf_len = len(pdf_text_clean)
                    orig_len = len(orig_clean)

                    # 글자수 비율 (주요 기준)
                    len_ratio = orig_len / max(pdf_len, 1)

                    if len_ratio > 2.0:
                        alignment_issues.append(
                            f"p.{pn}: ❌ 글자수 비율 {len_ratio:.1f}x — "
                            f"다음 페이지 내용 혼입 확실 "
                            f"(PDF:{pdf_len}자, 드래프트:{orig_len}자)"
                        )
                    elif len_ratio > 1.5:
                        alignment_issues.append(
                            f"p.{pn}: ⚠️ 글자수 비율 {len_ratio:.1f}x — "
                            f"다음 페이지 내용 혼입 의심"
                        )
                    elif len_ratio < 0.3 and pdf_len > 30:
                        alignment_issues.append(
                            f"p.{pn}: ⚠️ 원문 누락 의심 — "
                            f"PDF {pdf_len}자 대비 드래프트 {orig_len}자만 기록"
                        )

            doc.close()
        except ImportError:
            warnings.append("PyMuPDF 미설치 — 정합성 검증 건너뜀")
        except Exception as e:
            warnings.append(f"정합성 검증 오류: {e}")

    for ai in alignment_issues:
        if "❌" in ai:
            errors.append(ai)
        else:
            warnings.append(ai)

    qa_scores["페이지_정합성"] = (
        f"{len(alignment_issues)}건 불일치"
        if alignment_issues else "✅ 전체 통과"
    )

    # ── QA 요약 ──
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "page_count": len(pages),
        "qa_summary": qa_scores,
    }


# ============================================================
# 3. 대조 PDF 생성 — generate_comparison_pdf.py 호출
# ============================================================

def build_comparison_pdf(json_path: str, pdf_path: str, page_range: tuple[int, int]):
    """대조 PDF를 생성합니다."""
    # 같은 src 디렉토리의 스크립트를 import
    sys.path.insert(0, str(Path(__file__).parent))
    from generate_comparison_pdf import generate_comparison_pdf

    with open(json_path, "r", encoding="utf-8") as f:
        translations = json.load(f)

    output_path = str(Path(json_path).parent / f"대조본_p{page_range[0]}-{page_range[1]}.pdf")
    generate_comparison_pdf(pdf_path, translations, output_path, page_range)
    return output_path


# ============================================================
# 4. 세션 로그 — NAVI-Research prompt-log.json 패턴
# ============================================================

def update_translate_log(session_data: dict):
    """translate-log.json에 세션 기록을 추가합니다."""
    log_path = PROJECT_ROOT / "translated" / "translate-log.json"

    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)
    else:
        log_data = {"sessions": []}

    log_data["sessions"].append(session_data)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    print(f"📋 세션 로그 업데이트: {log_path}")


def update_index_md(session_data: dict):
    """translated/index.md에 번역 이력을 추가합니다."""
    index_path = PROJECT_ROOT / "translated" / "index.md"

    if not index_path.exists():
        header = """# 📚 번역 세션 기록

| # | 날짜 | PDF | 페이지 | 모드 | 결과 |
|---|------|-----|--------|------|------|
"""
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(header, encoding="utf-8")

    content = index_path.read_text(encoding="utf-8")
    # 기존 행 개수로 번호 매기기
    row_count = content.count("| ") // 6  # 헤더 행(2) 제외

    new_row = (
        f"| {row_count} "
        f"| {session_data['timestamp'][:10]} "
        f"| {session_data['pdf']} "
        f"| {session_data['pages']} "
        f"| {session_data['mode']} "
        f"| [{session_data.get('output_name', '대조본')}]({session_data.get('output_rel', '')}) |\n"
    )

    with open(index_path, "a", encoding="utf-8") as f:
        f.write(new_row)

    print(f"📝 인덱스 업데이트: {index_path}")


def auto_git_push(session_data: dict, output_path: str, pdf_output: str):
    """결과물을 리포지토리에 자동 커밋 및 푸시합니다."""
    print(f"\n🚀 Git 자동 업로드 시도 중...")
    
    files_to_add = [
        str(PROJECT_ROOT / "translated" / "translate-log.json"),
        str(PROJECT_ROOT / "translated" / "index.md"),
        output_path
    ]
    if pdf_output:
        files_to_add.append(pdf_output)

    try:
        # 안전하게 따옴표로 묶고 강제 추가 (ignored 파일도 포함)
        add_command = "git add -f " + " ".join(f'"{f}"' for f in files_to_add)
        subprocess.run(add_command, shell=True, check=True, cwd=str(PROJECT_ROOT))
        
        pdf_name = session_data.get("pdf", "문서")
        pages = session_data.get("pages", "all")
        commit_msg = f"Auto-translate: {pdf_name} (pages: {pages})"
        
        # 변경 사항이 있는지 확인
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if not status.stdout.strip():
            print("   ⚠️ 커밋할 새 변경 사항이 없습니다.")
            return

        subprocess.run(["git", "commit", "-m", commit_msg], check=True, cwd=str(PROJECT_ROOT))
        subprocess.run(["git", "push"], check=True, cwd=str(PROJECT_ROOT))
        
        print(f"   ✅ Git 자동 푸시 완료: {commit_msg}")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Git 작업 중 오류 발생 (진행은 계속됨): {e}")


# ============================================================
# CLI 명령
# ============================================================

def cmd_build(args):
    """올인원 빌드: MD→JSON→검증→대조PDF→로그"""
    import time
    start_time = time.time()

    # 페이지 범위 파싱
    page_range = None
    if args.pages:
        parts = args.pages.split("-")
        page_range = (int(parts[0]), int(parts[1]) if len(parts) > 1 else int(parts[0]))

    # 1. MD → JSON 변환
    if args.input:
        print(f"📖 마크다운 파싱: {args.input}")
        pages = parse_translation_md(args.input)
        print(f"   {len(pages)}페이지 파싱 완료")

        # JSON 저장
        output_path = args.output
        if not output_path:
            if page_range:
                output_path = f"translated/antigravity/pages_{page_range[0]}-{page_range[1]}.json"
            else:
                output_path = "translated/antigravity/pages.json"

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(pages, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON 저장: {out}")
    elif args.json:
        output_path = args.json
        with open(output_path, "r", encoding="utf-8") as f:
            pages = json.load(f)
    else:
        print("❌ --input (MD파일) 또는 --json (기존 JSON) 중 하나를 지정하세요")
        sys.exit(1)

    # 2. ANTI-JAPANESE 검증
    print(f"\n🔍 ANTI-JAPANESE 검증 중...")
    result = validate_translations(pages, page_range, pdf_path=args.pdf)

    if result["warnings"]:
        for w in result["warnings"]:
            print(f"   ⚠️  {w}")

    if not result["ok"]:
        print(f"\n❌ 검증 실패! {len(result['errors'])}개 오류:")
        for e in result["errors"]:
            print(f"   🚫 {e}")
        print(f"\n💡 해당 페이지의 번역을 수정한 후 다시 실행하세요.")
        sys.exit(1)

    print(f"   ✅ 검증 통과 ({result['page_count']}페이지, 일본어 잔존 0)")

    # QA 요약 출력
    if result.get("qa_summary"):
        print(f"\n📊 QA 요약:")
        for key, val in result["qa_summary"].items():
            print(f"   {key}: {val}")

    # 3. 대조 PDF 생성
    pdf_output = None
    if args.pdf and page_range:
        print(f"\n📄 대조 PDF 생성 중...")
        pdf_output = build_comparison_pdf(str(output_path), args.pdf, page_range)

    # 4. 세션 로그
    elapsed = time.time() - start_time
    pdf_name = Path(args.pdf).name if args.pdf else "unknown"
    # 출력 경로 계산
    if pdf_output:
        try:
            output_rel = str(Path(pdf_output).relative_to(PROJECT_ROOT / "translated"))
        except ValueError:
            output_rel = Path(pdf_output).name
        output_name = Path(pdf_output).name
    else:
        output_rel = ""
        output_name = ""

    session = {
        "id": f"pages_{page_range[0]}-{page_range[1]}" if page_range else "unknown",
        "timestamp": datetime.now().isoformat(),
        "pdf": pdf_name,
        "pages": args.pages or "all",
        "mode": "antigravity",
        "page_count": len(pages),
        "total_time_sec": round(elapsed, 1),
        "validation": {
            "japanese_remnants": 0,
            "missing_pages": 0,
        },
        "output": str(output_path),
        "output_name": output_name,
        "output_rel": output_rel,
    }

    update_translate_log(session)
    update_index_md(session)
    auto_git_push(session, output_path, pdf_output)

    # 최종 보고
    print(f"\n{'='*50}")
    print(f"🎉 파이프라인 완료!")
    print(f"   📄 JSON: {output_path}")
    if pdf_output:
        print(f"   📄 대조 PDF: {pdf_output}")
    print(f"   ⏱️  소요시간: {elapsed:.1f}초")
    print(f"{'='*50}")


def cmd_validate(args):
    """기존 JSON 파일 검증"""
    with open(args.json, "r", encoding="utf-8") as f:
        pages = json.load(f)

    page_range = None
    if args.pages:
        parts = args.pages.split("-")
        page_range = (int(parts[0]), int(parts[1]) if len(parts) > 1 else int(parts[0]))

    print(f"🔍 검증 중: {args.json}")
    result = validate_translations(pages, page_range, pdf_path=getattr(args, 'pdf', None))

    if result["warnings"]:
        for w in result["warnings"]:
            print(f"   ⚠️  {w}")

    if result["ok"]:
        print(f"✅ 검증 통과 ({result['page_count']}페이지)")
    else:
        print(f"\n❌ 검증 실패! {len(result['errors'])}개 오류:")
        for e in result["errors"]:
            print(f"   🚫 {e}")
        sys.exit(1)


# ============================================================
# Main
# ============================================================

def main():
    """CLI 엔트리포인트 — pyproject.toml [project.scripts]에서 호출"""
    parser = argparse.ArgumentParser(
        description="NAVI-Translate 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
명령:
  build     MD→JSON→검증→대조PDF→로그 (올인원)
  validate  기존 JSON 검증만

예시:
  python src/translate_pipeline.py build \\
    --input /tmp/translation_draft.md \\
    --pdf data/pdf/후아후아.pdf \\
    --pages 1-10

  python src/translate_pipeline.py validate \\
    --json translated/antigravity/pages_1-10.json \\
    --pages 1-10
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # build
    p_build = sub.add_parser("build", help="올인원 빌드")
    p_build.add_argument("--input", "-i", help="번역 마크다운 파일 경로")
    p_build.add_argument("--json", "-j", help="기존 JSON 파일 경로 (MD 대신)")
    p_build.add_argument("--pdf", "-p", help="원본 PDF 파일 경로")
    p_build.add_argument("--pages", help="페이지 범위 (예: 1-10)")
    p_build.add_argument("--output", "-o", help="출력 JSON 경로")

    # validate
    p_val = sub.add_parser("validate", help="JSON 검증")
    p_val.add_argument("--json", "-j", required=True, help="JSON 파일 경로")
    p_val.add_argument("--pages", help="예상 페이지 범위 (예: 1-10)")
    p_val.add_argument("--pdf", "-p", help="원본 PDF (정합성 검증용)")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "validate":
        cmd_validate(args)


if __name__ == "__main__":
    main()

