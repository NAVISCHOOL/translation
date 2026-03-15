#!/usr/bin/env python3
"""
NAVI-Translate: Gemini API 번역 모드
PDF 페이지 이미지를 Gemini Vision에 보내서 OCR 없이 직접 번역합니다.

사용법:
  python src/translate_gemini.py -i data/pdf/후아후아.pdf --pages 1-10
  python src/translate_gemini.py -i data/pdf/후아후아.pdf --pages 1-63 -o translated/gemini/output.json

필요:
  .env 파일에 GEMINI_API_KEY 설정
"""
import json
import argparse
import os
import sys
import time
import base64
from pathlib import Path

# .env 로딩
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from google import genai
from google.genai import types

# ============================================================
# 설정
# ============================================================
GEMINI_MODEL = "gemini-2.0-flash"
RPM_LIMIT = 14  # 무료 15RPM, 여유 두고 14

GLOSSARY_PATH = Path(__file__).parent.parent / "config" / "glossary.json"

def build_system_prompt() -> str:
    """glossary.json에서 용어집을 로드하여 시스템 프롬프트를 동적으로 생성합니다."""
    glossary_lines = ""
    if GLOSSARY_PATH.exists():
        import json as _json
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            glossary = _json.load(f)
        glossary_lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
    else:
        glossary_lines = "(용어집 파일 없음)"

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


def translate_page_with_gemini(client, image_path: str) -> str:
    """Gemini Vision으로 이미지 속 일본어를 한국어로 번역합니다."""
    
    with open(image_path, "rb") as f:
        image_data = f.read()
    
    image_b64 = base64.b64encode(image_data).decode("utf-8")
    
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            {
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    {"text": "이 이미지에 있는 일본어 텍스트를 한국어로 번역해주세요.\n"
                             "반드시 아래 형식으로 출력하세요:\n"
                             "ORIGINAL:\n(원문 일본어 텍스트)\n"
                             "TRANSLATED:\n(한국어 번역 텍스트)\n"
                             "세로쓰기도 정확하게 읽어주세요."},
                ]
            }
        ],
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(),
            temperature=0.3,
            max_output_tokens=3000,
        ),
    )
    
    text = response.text.strip() if response.text else ""
    
    # ORIGINAL: / TRANSLATED: 파싱
    original = ""
    translated = text
    if "ORIGINAL:" in text and "TRANSLATED:" in text:
        parts = text.split("TRANSLATED:", 1)
        original = parts[0].replace("ORIGINAL:", "").strip()
        translated = parts[1].strip()
    
    return original, translated


def translate_pdf_with_gemini(pdf_path: str, page_range: str = None, output_path: str = None):
    """PDF 페이지를 이미지로 추출 후 Gemini로 번역합니다."""
    import fitz
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "여기에_키를_입력하세요":
        print("❌ .env 파일에 GEMINI_API_KEY를 설정해주세요")
        sys.exit(1)
    
    client = genai.Client(api_key=api_key)
    
    # 페이지 범위
    doc = fitz.open(pdf_path)
    if page_range:
        parts = page_range.split("-")
        start_p = int(parts[0])
        end_p = int(parts[1]) if len(parts) > 1 else start_p
        pages = list(range(start_p, min(end_p + 1, len(doc) + 1)))
    else:
        pages = list(range(1, len(doc) + 1))
    
    print(f"📄 Gemini API 번역 시작: {len(pages)}페이지")
    print(f"   모델: {GEMINI_MODEL}")
    print(f"   속도 제한: {RPM_LIMIT} RPM\n")
    
    results = []
    total = len(pages)
    start_time = time.time()
    
    for i, pn in enumerate(pages, 1):
        idx = pn - 1
        if idx >= len(doc):
            continue
        
        # 페이지 이미지 추출
        page = doc[idx]
        pix = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72))
        tmp_img = f"/tmp/gemini_p{pn}.png"
        pix.save(tmp_img)
        
        print(f"  [{i}/{total}] p.{pn} 번역 중...", end=" ", flush=True)
        
        try:
            t0 = time.time()
            original, translated = translate_page_with_gemini(client, tmp_img)
            elapsed = time.time() - t0
            
            preview = translated[:50].replace("\n", " ")
            print(f"✅ ({elapsed:.1f}초) {preview}...")
            
            results.append({
                "page": pn,
                "original": original,
                "translated": translated,
                "time": round(elapsed, 1)
            })
        except Exception as e:
            print(f"❌ 에러: {e}")
            results.append({
                "page": pn,
                "translated": f"[에러: {e}]",
                "time": 0
            })
        
        os.remove(tmp_img)
        
        # RPM 제한 (4초 간격 = ~15RPM)
        if i < total:
            time.sleep(60 / RPM_LIMIT)
    
    doc.close()
    
    total_time = time.time() - start_time
    
    # 저장
    if not output_path:
        output_path = f"translated/antigravity/gemini_{page_range or 'all'}.json"
    
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
    print(f"🎉 Gemini 번역 완료!")
    print(f"📝 {total}페이지, 총 {total_time:.0f}초")
    print(f"📄 JSON: {out}")
    print(f"📄 TXT:  {txt_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini API 번역")
    parser.add_argument("--input", "-i", required=True, help="PDF 파일 경로")
    parser.add_argument("--pages", "-p", help="페이지 범위 (예: 1-10)")
    parser.add_argument("--output", "-o", help="출력 JSON 경로")
    args = parser.parse_args()
    
    translate_pdf_with_gemini(args.input, args.pages, args.output)
