#!/usr/bin/env python3
"""
NAVI-Translate: 로컬 Vision 번역 모드 (Qwen2.5-VL via Ollama)
PDF 페이지 이미지를 로컬 Vision 모델에 보내서 OCR 없이 직접 번역합니다.
인터넷 연결 불필요!

사용법:
  python src/translate_local_vision.py -i data/pdf/후아후아.pdf --pages 1-10
  python src/translate_local_vision.py -i data/pdf/후아후아.pdf --pages 10

필요:
  ollama pull qwen2.5vl:7b
"""
import json
import argparse
import re
import os
import sys
import time
import base64
import requests
from pathlib import Path

# .env 로딩 (LOCAL_VISION_MODEL 오버라이드용)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# ============================================================
# 설정
# ============================================================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = "qwen2.5vl:7b"
VISION_MODEL = os.getenv("LOCAL_VISION_MODEL", DEFAULT_MODEL)

# 용어집 로딩
GLOSSARY_PATH = Path(__file__).parent.parent / "config" / "glossary.json"

def load_glossary() -> dict:
    """config/glossary.json에서 용어집을 로딩합니다."""
    if GLOSSARY_PATH.exists():
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def build_system_prompt() -> str:
    """용어집을 포함한 시스템 프롬프트를 생성합니다."""
    glossary = load_glossary()
    glossary_lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())

    return f"""당신은 일본어→한국어 전문 번역가입니다.

## 역할
- 이미지에 있는 일본어 텍스트를 읽고 한국어로 번역합니다
- 세로쓰기(縦書き)도 정확하게 읽을 수 있습니다

## 출력 규칙
- 100% 한국어(한글+숫자+기본부호)만 출력
- 일본어(ひらがな, カタカナ, 漢字) 절대 금지
- 중국어(简体/繁體) 절대 금지
- AI 메타 발화(인사, 설명, 완료 보고) 금지 — 번역 텍스트만 출력

## 용어집
{glossary_lines}

## 문체
- 사이토 히토리 계열 서적: 따뜻하고 대화체, 해요체 혼용
- 번역투 제거: '~의' 남용 금지, 자연스러운 한국어
- 극한의 단문: 복문을 2~3개 짧은 단문으로 분리"""


SYSTEM_PROMPT = build_system_prompt()

# AI 메타 발화 패턴 (제거 대상)
META_PATTERNS = [
    r"^이미지에?\s*있는.*번역.*",
    r"^이미지의?\s*일본어.*번역.*",
    r"^다음은.*번역.*",
    r"^번역\s*결과.*",
    r"^한국어.*번역.*",
    r".*번역해\s*드리겠습니다.*",
    r".*번역한\s*결과.*",
    r"^---+\s*$",
]


def _remove_sentence_repetition(text: str, min_repeat: int = 3) -> str:
    """같은 문장/구가 min_repeat번 이상 반복되면 첫 1회만 남기고 제거."""
    # 5자 이상의 구가 3번 이상 반복되는 패턴 탐지
    match = re.search(r'(.{5,}?)\1{' + str(min_repeat - 1) + r',}', text)
    if match:
        # 반복 시작 위치까지만 남기고 반복된 구를 1회 포함
        start = match.start()
        repeated = match.group(1)
        text = text[:start] + repeated
    return text


def post_process_translation(text: str) -> str:
    """AI 메타 발화 제거 및 반복 감지/절단."""
    if not text:
        return text

    # 1) AI 메타 프리앰블 제거 (첫 3줄까지만 체크)
    lines = text.split("\n")
    clean_lines = []
    preamble_done = False
    preamble_check_count = 0
    for line in lines:
        if not preamble_done and preamble_check_count < 5:
            stripped = line.strip()
            preamble_check_count += 1
            # 빈 줄이나 구분선은 프리앰블 중이면 스킵
            if not stripped or stripped == "---":
                continue
            # 메타 패턴 매칭
            is_meta = False
            for pat in META_PATTERNS:
                if re.match(pat, stripped):
                    is_meta = True
                    break
            if is_meta:
                continue
            preamble_done = True
        else:
            preamble_done = True
        clean_lines.append(line)

    # 2) 줄 단위 반복 감지: 같은 줄이 3번 이상 연속되면 절단
    result_lines = []
    repeat_count = 0
    prev_line = None
    for line in clean_lines:
        stripped = line.strip()
        if stripped and stripped == prev_line:
            repeat_count += 1
            if repeat_count >= 3:
                break
        else:
            repeat_count = 0
        prev_line = stripped
        result_lines.append(line)

    # 3) 문장 단위 반복 감지 (같은 줄 안에서 반복)
    final_lines = []
    for line in result_lines:
        final_lines.append(_remove_sentence_repetition(line))

    return "\n".join(final_lines).strip()


def check_ollama_ready():
    """Ollama 서버 접속 및 모델 존재 여부를 확인합니다."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.ConnectionError:
        print("❌ Ollama 서버에 연결할 수 없습니다.")
        print("   brew services start ollama  또는  ollama serve  로 시작해주세요.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ollama 서버 확인 실패: {e}")
        sys.exit(1)

    models = resp.json().get("models", [])
    model_names = [m.get("name", "") for m in models]

    # qwen2.5vl:7b -> "qwen2.5vl:7b" 형태로 체크
    found = any(VISION_MODEL in name for name in model_names)
    if not found:
        print(f"❌ 모델 '{VISION_MODEL}'이 설치되어 있지 않습니다.")
        print(f"   ollama pull {VISION_MODEL}  로 설치해주세요.")
        print(f"   현재 설치된 모델: {', '.join(model_names) or '(없음)'}")
        sys.exit(1)

    print(f"✅ Ollama 서버 연결 OK, 모델: {VISION_MODEL}")


def translate_page_with_local_vision(image_path: str) -> str:
    """Ollama Vision 모델로 이미지 속 일본어를 한국어로 번역합니다."""

    with open(image_path, "rb") as f:
        image_data = f.read()

    image_b64 = base64.b64encode(image_data).decode("utf-8")

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": "이 이미지에 있는 일본어 텍스트를 한국어로 번역해주세요. "
                           "반드시 한국어만 출력하세요. 세로쓰기도 정확하게 읽어주세요.",
                "images": [image_b64],
            },
        ],
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 1500,
            "repeat_penalty": 1.2,
            "repeat_last_n": 256,
        },
    }

    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=300,  # 로컬 모델은 느릴 수 있으므로 5분
    )
    resp.raise_for_status()

    result = resp.json()
    content = result.get("message", {}).get("content", "")
    return post_process_translation(content)


def translate_pdf_with_local_vision(
    pdf_path: str,
    page_range: str = None,
    output_path: str = None,
    dpi: int = 200,
):
    """PDF 페이지를 이미지로 추출 후 로컬 Vision 모델로 번역합니다."""
    import fitz

    check_ollama_ready()

    # 페이지 범위
    doc = fitz.open(pdf_path)
    if page_range:
        parts = page_range.split("-")
        start_p = int(parts[0])
        end_p = int(parts[1]) if len(parts) > 1 else start_p
        pages = list(range(start_p, min(end_p + 1, len(doc) + 1)))
    else:
        pages = list(range(1, len(doc) + 1))

    print(f"\n📄 로컬 Vision 번역 시작: {len(pages)}페이지")
    print(f"   모델: {VISION_MODEL}")
    print(f"   DPI: {dpi}")
    print(f"   인터넷: ❌ 불필요 (오프라인 모드)\n")

    results = []
    total = len(pages)
    start_time = time.time()

    for i, pn in enumerate(pages, 1):
        idx = pn - 1
        if idx >= len(doc):
            continue

        # 페이지 이미지 추출
        page = doc[idx]
        scale = dpi / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        tmp_img = f"/tmp/local_vision_p{pn}.png"
        pix.save(tmp_img)

        print(f"  [{i}/{total}] p.{pn} 번역 중...", end=" ", flush=True)

        try:
            t0 = time.time()
            translated = translate_page_with_local_vision(tmp_img)
            elapsed = time.time() - t0

            preview = translated[:50].replace("\n", " ")
            print(f"✅ ({elapsed:.1f}초) {preview}...")

            results.append({
                "page": pn,
                "translated": translated,
                "time": round(elapsed, 1),
            })
        except requests.Timeout:
            print(f"⏰ 타임아웃 (5분 초과)")
            results.append({
                "page": pn,
                "translated": "[에러: 타임아웃]",
                "time": 0,
            })
        except Exception as e:
            print(f"❌ 에러: {e}")
            results.append({
                "page": pn,
                "translated": f"[에러: {e}]",
                "time": 0,
            })

        # 임시 이미지 삭제
        if os.path.exists(tmp_img):
            os.remove(tmp_img)

    doc.close()

    total_time = time.time() - start_time

    # 저장
    if not output_path:
        output_path = f"translated/llm/local_vision_{page_range or 'all'}.json"

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # TXT도 저장
    txt_path = out.with_suffix(".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(f"--- p.{r['page']} ---\n")
            f.write(r.get("translated", ""))
            f.write("\n\n")

    print(f"\n{'='*50}")
    print(f"🎉 로컬 Vision 번역 완료!")
    print(f"📝 {total}페이지, 총 {total_time:.0f}초")
    print(f"📄 JSON: {out}")
    print(f"📄 TXT:  {txt_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="로컬 Vision 모델 번역 (Qwen2.5-VL via Ollama)"
    )
    parser.add_argument("--input", "-i", required=True, help="PDF 파일 경로")
    parser.add_argument("--pages", "-p", help="페이지 범위 (예: 1-10, 10)")
    parser.add_argument("--output", "-o", help="출력 JSON 경로")
    parser.add_argument("--dpi", type=int, default=200, help="이미지 DPI (기본: 200)")
    args = parser.parse_args()

    translate_pdf_with_local_vision(args.input, args.pages, args.output, args.dpi)
