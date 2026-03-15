#!/usr/bin/env python3
"""
NAVI-Translate: Ollama 기반 일본어→한국어 번역기
사이토 히토리 전용 시스템 프롬프트를 사용하여 로컬에서 번역합니다.

사용법:
  # 1단계: PDF 추출 (이미 완료)
  python extract_pdf.py -i 후아후아.pdf -o ./extracted

  # 2단계: 번역 (특정 페이지)
  python translate.py -i extracted/extracted_pages.json --pages 10-11

  # 2단계: 전체 번역
  python translate.py -i extracted/extracted_pages.json

  # 전처리만 확인
  python translate.py -i extracted/extracted_pages.json --pages 10-11 --preprocess-only
"""
import json
import re
import argparse
import time
import requests
from pathlib import Path


# ============================================================
# 시스템 프롬프트 (사이토 히토리 v3.0)
# ============================================================

SYSTEM_PROMPT = """당신은 도서출판 나비스쿨(Nabischool)의 수석 번역가입니다.
일본어 원문을 즉시 조판용 한국어 번역고로 출력합니다.

## 번역 원칙
1. 제로 첨삭: 원문에 없는 내용 추가 금지, 어떤 내용도 생략 금지
2. 번역투 제거: 'の(~의)' 남용, 무생물 주어 수동태, 불필요한 사역동사 → 자연스러운 한국어 능동형으로 치환
3. 극한의 단문: 일본어 복문을 2~3개 짧은 단문으로 쪼개서 가독성 확보
4. 접속사 절제: '그래서, 그리고, 하지만' 남발 금지

## 사이토 히토리 문체 규칙
- 진리/철학 선언 → 하십시오체(~습니다, ~합니다)
- 다정한 권유 → 해요체(~해 보세요, ~어떨까요?, ~거든요)
- 자연물 비유 → 산문시처럼 유려하게
- 대화/확언 → 큰따옴표(" ")
- 속마음/핵심키워드 → 작은따옴표(' ')

## 핵심 용어집 (절대 변경 금지)
- ふわふわ → 후아후아 (의역 금지, 고유명사)
- 一人さん → 히토리 선생님 ('씨/님' 직역 금지)
- 上気元 → 신나는 기분 ('상기원' 한자 음역 금지)
- 神 → 하늘 (종교색 배제)
- 器 → 그릇
- 天国言葉 → 천국의 언어
- 修行 → 수행 ('고행/훈련' 금지)
{glossary_extra}

## OCR 복원 규칙
- 세로쓰기로 인한 글자 사이 공백을 문맥에 맞게 이어붙여 복원
- 파편화된 문장을 완전한 문장으로 복원 후 번역


## ⚠️ 출력 언어 규칙 (최우선)
- 출력은 반드시 100% 한국어(한글+숫자+기본부호)만 사용할 것
- 일본어(ひらがな, カタカナ, 漢字) 절대 금지
- 중국어(简体/繁體) 절대 금지 — 중국어로 번역하지 말 것!
- はじめに → '머리말', おわりに → '맺음말', ひまわり畑 → '해바라기 밭'
- 일본 고유명사도 한국어 표기: ふわふわ→후아후아, 一人さん→히토리 선생님

## 절대 금지
- AI의 메타 발화(인사, 설명, 완료 보고) 출력 금지
- 오직 번역 텍스트만 출력할 것"""


# ============================================================
# OCR 전처리 (강화 버전 v2.0)
# ============================================================

# OCR에서 자주 오인식되는 한자 교정 테이블
OCR_KANJI_FIXES = {
    '屎色': '景色',    # 경치
    '祉界': '世界',    # 세계
    '科揚': '高揚',    # 고양
    '不思談': '不思議',  # 불가사의
    '氾樟': '記憶',    # 기억 (문맥상)
    '言策': '言葉',    # 말
    '言菓': '言葉',    # 말
    '言業': '言葉',    # 말
    '言盆': '言霊',    # 언령
    '言盤': '言霊',    # 언령
    '言塁': '言霊',    # 언령
    '言儘': '言霊',    # 언령
    '言莱': '言葉',    # 말
    '言菜': '言葉',    # 말
    '最嵩': '最高',    # 최고
    '木翡': '本書',    # 이 책
    '本宙': '本書',    # 이 책
    '瀧神': '龍神',    # 용신
    '甑神': '龍神',    # 용신
    '紺神': '龍神',    # 용신
    '削神': '龍神',    # 용신
    '罷神': '龍神',    # 용신
    '雌神': '龍神',    # 용신
    '縣神': '龍神',    # 용신
    '間神': '龍神',    # 용신
    '龍神梯': '龍神様',  # 용신님
    '龍神贔': '龍神様',  # 용신님
    '神栂森徊': '',    # OCR 노이즈 (목차 주변)
    '久しぷり': '久しぶり',  # 오랜만
    '選ぴ': '選び',    # 선택
    '学ぴ': '学び',    # 배움
    '飛ぴ': '飛び',    # 날다
    '撮彩': '撮影',    # 촬영
    '批界': '世界',    # 세계
    '匪界': '世界',    # 세계
    '泄界': '世界',    # 세계
    '序虹': '序章',    # 서장
    '序江': '序章',    # 서장
    '序窃': '序章',    # 서장
    '序m': '序章',     # 서장
    '序が': '序章',    # 서장
    '第1袋': '第1章',   # 제1장
    '第l迂': '第1章',   # 제1장
    '第1迂': '第1章',   # 제1장
    '第1迄': '第1章',   # 제1장
    '第1堂': '第1章',   # 제1장
    '第1武': '第1章',   # 제1장
    '第1窪': '第1章',   # 제1장
    '第1菜': '第1章',   # 제1장
    '第1京': '第1章',   # 제1장
    '第9京': '第1章',   # 제1장
    '第1a': '第1章',    # 제1장
    '第l~': '第1章',    # 제1장
    '第l!': '第1章',    # 제1장
    '第l迁': '第1章',   # 제1장
}

# 챕터 헤더 패턴 (제거용 - 번역에서 별도 처리)
CHAPTER_HEADER_PATTERNS = [
    r'序章\s*龍?神?様?は?[「『]?ふわふわ[」』]?\s*が?大好き\w*',
    r'第\d章\s*明る＜?楽しい[「『]?ふわふわ[」』]?\w*の?言[霊盆盤塁莱菜葉]+',
    r'船神様は\w*ふわふわ\w*が大好き\w*',
    r'前神\w*ふわふわ\w*が大好き\w*',
    r'開神様は\w*ふわふわ\w*が大好き\w*',
    r'皿神\w*は\w*ふわふわ\w*が大好き\w*',
    r'明る＜楽しい[「『りr]?ふわふ[わか初ね]\w*の?言[霊盆盤塁莱菜葉孟]+',
]


def preprocess_vertical_ocr(text: str) -> str:
    """세로쓰기 OCR에서 발생한 오류를 체계적으로 정리합니다. (v2.0)"""
    
    # === 1단계: 세로쓰기 글자 분리 복원 (공백 제거를 먼저!) ===
    # 일본어 문자 사이의 공백 제거 (히라가나, 카타카나, 한자)
    text = re.sub(
        r'(?<=[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uFF01-\uFF9F])'
        r'\s+'
        r'(?=[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uFF01-\uFF9F])',
        '', text
    )
    # 일본어 문자와 구두점 사이의 공백 제거
    text = re.sub(
        r'(?<=[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])'
        r'\s+'
        r'(?=[、。！？「」『』（）\u300C\u300D\u300E\u300F])',
        '', text
    )
    text = re.sub(
        r'(?<=[、。！？「」『』（）\u300C\u300D\u300E\u300F])'
        r'\s+'
        r'(?=[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])',
        '', text
    )
    # 일본어 문자와 숫자 사이의 공백 제거
    text = re.sub(
        r'(?<=[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])\s+(?=\d)',
        '', text
    )
    text = re.sub(
        r'(?<=\d)\s+(?=[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])',
        '', text
    )
    
    # === 2단계: OCR 한자 오인식 교정 (공백 제거 후에 해야 매칭됨!) ===
    for wrong, correct in OCR_KANJI_FIXES.items():
        text = text.replace(wrong, correct)
    
    # === 3단계: 챕터 헤더 감지 및 태그 변환 ===
    for pattern in CHAPTER_HEADER_PATTERNS:
        text = re.sub(pattern, '', text)
    
    # === 4단계: 페이지 끝 숫자 제거 (예: "7", "8" 등 단독 숫자 줄) ===
    text = re.sub(r'\n\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)
    
    # === 5단계: 노이즈 문자 제거 ===
    # OCR 아티팩트 문자들
    text = re.sub(r'[¥●◎■□▲△▼▽★☆※＠゜]+', '', text)
    # 의미 없는 기호열 (점, 하이픈, 슬래시 등이 3개 이상)
    text = re.sub(r'[・\-―—ー=＝\.。，,;；:：\'"\'\"]{3,}', '', text)
    # 단독 라틴 문자/숫자 노이즈 (문맥 없이 나타나는 것들)
    text = re.sub(r'\b[a-zA-Z]{1,2}\b(?!\w)', '', text)
    # 특수 OCR 노이즈 패턴
    text = re.sub(r'[\^~`]+', '', text)
    text = re.sub(r'(?:害|＄|苓|控)・', '', text)  # 특정 노이즈
    
    # === 6단계: 줄 정리 ===
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # 빈 줄 스킵
        if not stripped:
            cleaned_lines.append('')
            continue
        # 일본어가 없는 3자 이하 줄 제거
        if len(stripped) <= 3 and not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', stripped):
            continue
        # 순수 기호/노이즈만 있는 줄 제거
        if re.match(r'^[\s\d\W]+$', stripped) and not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', stripped):
            continue
        cleaned_lines.append(stripped)
    
    result = '\n'.join(cleaned_lines).strip()
    # 최종 정리: 연속 빈 줄 제거
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


def chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """텍스트를 번역 가능한 청크로 분할합니다."""
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        if not para.strip():
            continue
        if len(current_chunk) + len(para) + 2 > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


# ============================================================
# Ollama 번역 엔진
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/chat"

# 번역 후 일본어 잔류 자동 교체 테이블
JP_TO_KR_POSTPROCESS = {
    'はじめに': '머리말',
    'おわりに': '맺음말',
    'ひまわり畑': '해바라기 밭',
    'ひまわり': '해바라기',
    'ふわふわ': '후아후아',
    '一人さん': '히토리 선생님',
    '斎藤一人': '사이토 히토리',
    '柴村恵美子': '시바무라 에미코',
    '龍神様': '용신님',
    '龍神': '용신',
    '本書': '이 책',
    '言霊': '언령',
    '天国言葉': '천국의 언어',
    '地獄言葉': '지옥의 언어',
    '上気元': '신나는 기분',
    '序章': '서장',
    '第1章': '제1장',
    '第2章': '제2장',
    '第3章': '제3장',
}


def postprocess_translation(text: str) -> str:
    """번역 결과에서 남은 일본어를 한국어로 교체합니다."""
    for jp, kr in JP_TO_KR_POSTPROCESS.items():
        text = text.replace(jp, kr)
    return text


def load_glossary(glossary_path: str = None) -> str:
    """glossary.json을 시스템 프롬프트용 텍스트로 변환합니다."""
    if glossary_path is None:
        # 기본 경로: config/glossary.json
        base = Path(__file__).parent.parent / "config" / "glossary.json"
        if not base.exists():
            return ""
        glossary_path = str(base)
    
    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)
        lines = [f"- {jp} → {kr}" for jp, kr in glossary.items()]
        return "\n## 추가 용어집 (glossary.json)\n" + "\n".join(lines)
    except Exception:
        return ""


def build_system_prompt(glossary_path: str = None) -> str:
    """용어집을 포함한 시스템 프롬프트를 빌드합니다."""
    glossary_extra = load_glossary(glossary_path)
    return SYSTEM_PROMPT.format(glossary_extra=glossary_extra)


def translate_with_ollama(chunks: list[str], model: str = "qwen2.5:14b", glossary_path: str = None):
    """Ollama API를 사용하여 청크별로 번역합니다."""
    
    # Ollama 서버 확인
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"✅ Ollama 서버 연결됨. 사용 가능한 모델: {models}")
        if model not in models and f"{model}:latest" not in models:
            print(f"⚠️ 모델 '{model}'이 없습니다. 'ollama pull {model}'을 먼저 실행해주세요.")
            return []
    except requests.ConnectionError:
        print("❌ Ollama 서버가 실행되지 않았습니다. 'brew services start ollama'를 실행해주세요.")
        return []
    
    translations = []
    total = len(chunks)
    
    for i, chunk in enumerate(chunks, 1):
        print(f"\n📝 번역 중: {i}/{total} ({len(chunk)}자)")
        
        system_prompt = build_system_prompt(glossary_path)
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"다음 일본어 원문을 한국어로 완전히 번역해주세요. 반드시 한국어(한글)로만 출력하세요. 일본어, 중국어 절대 금지:\n\n{chunk}"}
            ],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 4096
            }
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=300)
            result = response.json()
            translated = postprocess_translation(result["message"]["content"])
            elapsed = time.time() - start_time
            
            # 토큰 통계
            eval_count = result.get("eval_count", 0)
            eval_duration = result.get("eval_duration", 0)
            tokens_per_sec = eval_count / (eval_duration / 1e9) if eval_duration else 0
            
            translations.append({
                "chunk_index": i,
                "original": chunk,
                "translated": translated,
                "time_seconds": round(elapsed, 1),
                "tokens_per_sec": round(tokens_per_sec, 1)
            })
            
            preview = translated[:100].replace("\n", " ")
            print(f"   ✅ 완료 ({elapsed:.1f}초, {tokens_per_sec:.1f} tok/s): {preview}...")
            
        except Exception as e:
            print(f"   ❌ 번역 실패: {e}")
            translations.append({
                "chunk_index": i,
                "original": chunk,
                "translated": f"[번역 실패: {e}]",
                "time_seconds": 0,
                "tokens_per_sec": 0
            })
    
    return translations


def save_translations(translations: list[dict], output_path: str):
    """번역 결과를 저장합니다."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    
    # 전체 번역 텍스트
    with open(out, "w", encoding="utf-8") as f:
        for t in translations:
            f.write(t["translated"])
            f.write("\n\n")
    
    # JSON (원문 + 번역 대조)
    json_path = out.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)
    
    return out, json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NAVI-Translate: 일본어→한국어 번역기 (Ollama)")
    parser.add_argument("--input", "-i", required=True, help="입력 (extracted_pages.json 또는 .txt)")
    parser.add_argument("--output", "-o", default="./translated/output.txt", help="출력 파일")
    parser.add_argument("--model", "-m", default="qwen2.5:14b", help="Ollama 모델 (기본: qwen2.5:14b)")
    parser.add_argument("--pages", "-p", help="페이지 범위 (예: 10-20)")
    parser.add_argument("--chunk-size", "-c", type=int, default=1500, help="청크 최대 글자 수")
    parser.add_argument("--preprocess-only", action="store_true", help="전처리만 수행")
    
    args = parser.parse_args()
    
    # 입력 로드
    input_path = Path(args.input)
    if input_path.suffix == ".json":
        with open(input_path, "r", encoding="utf-8") as f:
            pages = json.load(f)
        if args.pages:
            parts = args.pages.split("-")
            start_p = int(parts[0])
            end_p = int(parts[1]) if len(parts) > 1 else start_p
            pages = [p for p in pages if start_p <= p["page"] <= end_p]
        raw_text = "\n\n".join(p["text"] for p in pages)
    else:
        with open(input_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    
    # 전처리
    print("🔧 세로쓰기 OCR 전처리 중...")
    cleaned = preprocess_vertical_ocr(raw_text)
    print(f"   원본: {len(raw_text)}자 → 정리 후: {len(cleaned)}자 ({len(raw_text) - len(cleaned)}자 제거)")
    
    if args.preprocess_only:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"✅ 전처리 결과 저장: {out_path}")
        exit(0)
    
    # 청크 분할
    chunks = chunk_text(cleaned, args.chunk_size)
    print(f"📦 {len(chunks)}개 청크로 분할 완료")
    
    # 번역
    translations = translate_with_ollama(chunks, args.model)
    
    if not translations:
        print("❌ 번역 결과가 없습니다.")
        exit(1)
    
    # 저장
    txt_path, json_path = save_translations(translations, args.output)
    
    # 결과 요약
    total_time = sum(t["time_seconds"] for t in translations)
    total_input = sum(len(t["original"]) for t in translations)
    total_output = sum(len(t["translated"]) for t in translations)
    avg_speed = sum(t["tokens_per_sec"] for t in translations) / len(translations) if translations else 0
    
    print(f"\n{'='*50}")
    print(f"🎉 번역 완료!")
    print(f"📝 입력: {total_input:,}자 → 출력: {total_output:,}자")
    print(f"⚡ 평균 속도: {avg_speed:.1f} tok/s")
    print(f"⏱️  총 소요 시간: {total_time:.0f}초 ({total_time/60:.1f}분)")
    print(f"📄 텍스트: {txt_path}")
    print(f"📋 JSON: {json_path}")
    print(f"{'='*50}")
