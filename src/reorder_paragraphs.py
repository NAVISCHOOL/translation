#!/usr/bin/env python3
"""
NAVI-Translate: 번역 JSON 단락 순서 보정기

PDF의 시각적 텍스트 순서(위→아래)에 맞춰
번역 JSON의 original/translated 단락 순서를 재배열합니다.

알고리즘:
  1. PyMuPDF로 PDF 페이지의 전체 텍스트를 시각적 순서로 추출
  2. JSON의 각 단락 앞부분(prefix)이 PDF 전체 텍스트에서 어디에 나오는지 offset 검색
  3. offset 순서로 단락을 재배열 (original + translated 동시)

사용법:
  # dry-run (미리보기만)
  python src/reorder_paragraphs.py \
    --pdf "data/pdf/우주소원 서비스 - 독일어 원서.pdf" \
    --json-dir translated/antigravity/우주소원_ko/

  # 실제 적용
  python src/reorder_paragraphs.py \
    --pdf "data/pdf/우주소원 서비스 - 독일어 원서.pdf" \
    --json-dir translated/antigravity/우주소원_ko/ \
    --apply
"""
import argparse
import json
import glob
import os
import re
import shutil

import fitz  # PyMuPDF


# Minimum prefix length to search for in PDF text
PREFIX_LEN = 40
# Minimum ratio of paragraphs that must be found for reorder to apply
MIN_FOUND_RATIO = 0.7


def get_pdf_page_text(pdf_path: str, page_num: int) -> str:
    """Extract full text from a PDF page in visual reading order."""
    doc = fitz.open(pdf_path)
    if page_num - 1 >= len(doc):
        doc.close()
        return ""
    page = doc[page_num - 1]
    text = page.get_text()
    doc.close()
    return text


def collapse_ws(text: str) -> str:
    """Collapse all whitespace to single space for fuzzy search."""
    return re.sub(r"\s+", " ", text).strip()


def strip_symbols(text: str) -> str:
    """Strip non-alphanumeric symbols for fuzzy comparison."""
    return re.sub(r"[^\w\s]", "", text)


def find_offset(haystack: str, needle_prefix: str) -> int | None:
    """Find the offset of needle_prefix in haystack using collapsed whitespace.

    Returns the position in the collapsed haystack, or None if not found.
    Tries multiple strategies: exact, stripped symbols, shorter prefix.
    """
    h = collapse_ws(haystack)
    n = collapse_ws(needle_prefix)[:PREFIX_LEN]

    if len(n) < 5:
        return None

    # Try exact match first
    pos = h.find(n)
    if pos >= 0:
        return pos

    # Try with symbols stripped (handles ☺, ★, etc. missing from PDF)
    h_stripped = strip_symbols(h)
    n_stripped = strip_symbols(n)
    if len(n_stripped) >= 5:
        pos = h_stripped.find(n_stripped)
        if pos >= 0:
            return pos

    # Try with shorter prefix (half length)
    short = n[: len(n) // 2]
    if len(short) >= 5:
        pos = h.find(short)
        if pos >= 0:
            return pos

    return None


def compute_reorder(
    json_paragraphs: list[str], pdf_text: str
) -> list[int] | None:
    """Compute reorder indices by finding each paragraph's offset in PDF text.

    Returns reorder indices or None if no reordering needed or matching fails.
    """
    n = len(json_paragraphs)
    if n <= 1:
        return None

    # Find offset of each JSON paragraph in the PDF full text
    offsets = []
    for i, para in enumerate(json_paragraphs):
        offset = find_offset(pdf_text, para)
        offsets.append((i, offset))

    # Count how many were found
    found = [(i, o) for i, o in offsets if o is not None]
    if len(found) < n * MIN_FOUND_RATIO:
        return None  # too many unmatched

    # Sort found paragraphs by their offset (visual position)
    found_sorted = sorted(found, key=lambda x: x[1])

    # Build reorder: found paragraphs in visual order,
    # unfound paragraphs inserted near their original neighbors
    unfound = [i for i, o in offsets if o is None]
    found_indices = [i for i, _ in found_sorted]

    # Insert unfound paragraphs at their natural position
    # (between their original predecessor and successor in the found list)
    reorder = list(found_indices)
    for ui in unfound:
        # Find the best insertion point: right before the first found paragraph
        # that was originally after this unfound one
        insert_pos = len(reorder)  # default: end
        for pos, fi in enumerate(reorder):
            if fi > ui:
                insert_pos = pos
                break
        reorder.insert(insert_pos, ui)

    # Check if reorder is different from original
    if reorder == list(range(n)):
        return None  # already in correct order

    return reorder


def reorder_page(page_entry: dict, reorder: list[int]) -> dict:
    """Apply paragraph reordering to a page entry's original and translated."""
    orig_paras = page_entry["original"].split("\n\n")
    trans_paras = page_entry["translated"].split("\n\n")

    if len(orig_paras) == len(reorder):
        page_entry["original"] = "\n\n".join(orig_paras[i] for i in reorder)

    if len(trans_paras) == len(reorder):
        page_entry["translated"] = "\n\n".join(trans_paras[i] for i in reorder)

    return page_entry


def process_json_file(
    json_path: str, pdf_path: str, apply: bool = False
) -> list[dict]:
    """Process a single JSON file, return list of changes."""
    with open(json_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    changes = []
    modified = False

    for entry in pages:
        pn = entry["page"]
        orig = entry.get("original", "")

        if len(orig) < 30 or "빈 페이지" in orig:
            continue

        # Get PDF full text in visual order
        pdf_text = get_pdf_page_text(pdf_path, pn)
        if not pdf_text.strip():
            continue

        # Get JSON paragraphs (split by double newline)
        json_paras = [p for p in orig.split("\n\n") if p.strip()]
        if len(json_paras) < 2:
            continue

        reorder = compute_reorder(json_paras, pdf_text)
        if reorder is None:
            continue

        # Record change details
        old_first = json_paras[0][:50].replace("\n", " ")
        new_first = json_paras[reorder[0]][:50].replace("\n", " ")

        trans_paras = [p for p in entry.get("translated", "").split("\n\n") if p.strip()]
        old_trans_first = trans_paras[0][:40].replace("\n", " ") if trans_paras else ""
        new_trans_first = (
            trans_paras[reorder[0]][:40].replace("\n", " ")
            if trans_paras and reorder[0] < len(trans_paras)
            else ""
        )

        changes.append(
            {
                "page": pn,
                "reorder": reorder,
                "before_orig": old_first,
                "after_orig": new_first,
                "before_trans": old_trans_first,
                "after_trans": new_trans_first,
            }
        )

        if apply:
            reorder_page(entry, reorder)
            modified = True

    if apply and modified:
        bak_path = json_path + ".bak"
        if not os.path.exists(bak_path):
            shutil.copy2(json_path, bak_path)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(pages, f, ensure_ascii=False, indent=2)

    return changes


def main():
    parser = argparse.ArgumentParser(
        description="번역 JSON 단락 순서를 PDF 시각적 순서에 맞춰 보정"
    )
    parser.add_argument("--pdf", required=True, help="원본 PDF 경로")
    parser.add_argument("--json-dir", required=True, help="pages_*.json 디렉토리")
    parser.add_argument(
        "--apply", action="store_true", help="실제 적용 (기본: dry-run)"
    )
    args = parser.parse_args()

    json_files = sorted(glob.glob(os.path.join(args.json_dir, "pages_*.json")))
    if not json_files:
        print(f"❌ JSON 파일을 찾을 수 없습니다: {args.json_dir}/pages_*.json")
        return

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"📐 단락 순서 보정 ({mode})")
    print(f"   PDF: {args.pdf}")
    print(f"   JSON: {len(json_files)}개 파일\n")

    total_changes = 0
    for jf in json_files:
        changes = process_json_file(jf, args.pdf, apply=args.apply)
        if changes:
            fname = os.path.basename(jf)
            for c in changes:
                status = "✅ 적용" if args.apply else "🔍 변경 예정"
                print(
                    f"  {status} p.{c['page']:3d} ({fname}):"
                )
                print(
                    f"       원문: [{c['before_orig']}...] → [{c['after_orig']}...]"
                )
                print(
                    f"       번역: [{c['before_trans']}...] → [{c['after_trans']}...]"
                )
                total_changes += 1

    print(f"\n{'=' * 50}")
    print(f"총 {total_changes}개 페이지 {'보정 완료' if args.apply else '변경 예정'}")
    if not args.apply and total_changes > 0:
        print("   --apply 플래그를 추가하면 실제 적용됩니다")


if __name__ == "__main__":
    main()
