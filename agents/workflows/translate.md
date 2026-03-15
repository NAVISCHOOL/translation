---
description: 사용자가 "번역해줘"라고 요청하면 번역 모드를 선택하도록 안내하는 워크플로우
---

# 번역 워크플로우

사용자가 "번역해줘", "번역 진행해" 등 번역 관련 요청을 하면 **먼저 모드를 물어봅니다**:

> 어떤 모드로 번역할까요?
>
> 1. **LLM 모드**
>    - a) **PyMuPDF OCR** → Qwen2.5-14B 로컬 번역 (완전 무료, 오프라인)
>    - b) **Gemini Vision OCR** → Qwen2.5-14B 로컬 번역 또는 Gemini 직접 번역 (무료 API, 고품질 OCR)
> 2. **안티그래비티 모드** — PDF 이미지를 직접 보고 번역 (최고 품질, 대화형)
>
> 페이지 범위도 알려주세요! (예: 1-63 전체, 8 단일 페이지)

---

## 모드 1a: LLM 모드 — PyMuPDF OCR (오프라인)

// turbo-all

1. 전처리 및 번역 실행:
```bash
source .venv/bin/activate && python src/translate.py -i extracted/extracted_pages.json --pages {PAGE_RANGE} -o ./translated/llm/output.txt
```

2. 대조 PDF 생성:
```bash
source .venv/bin/activate && python src/generate_comparison_pdf.py \
  --original data/pdf/후아후아_20251210-part-1-ocr.pdf \
  --translation translated/llm/output.json \
  --pages {PAGE_RANGE} \
  -o translated/llm/대조본.pdf
```

---

## 모드 1b: LLM 모드 — Gemini Vision (고품질 OCR)

// turbo-all

1. Gemini Vision으로 번역 실행:
```bash
source .venv/bin/activate && python src/translate_gemini.py -i data/pdf/후아후아_20251210-part-1-ocr.pdf --pages {PAGE_RANGE}
```

2. 대조 PDF 생성:
```bash
source .venv/bin/activate && python src/generate_comparison_pdf.py \
  --original data/pdf/후아후아_20251210-part-1-ocr.pdf \
  --translation translated/llm/gemini_{PAGE_RANGE}.json \
  --pages {PAGE_RANGE} \
  -o translated/llm/대조본_gemini.pdf
```

---

## 모드 2: 안티그래비티 모드 (PDF 이미지 직접 보기)

// turbo-all

### Step 1. PDF 페이지를 이미지로 추출
```bash
source .venv/bin/activate && python src/prepare_pages.py -i data/pdf/후아후아_20251210-part-1-ocr.pdf --pages {PAGE_RANGE} --mode image
```
출력: `/tmp/antigravity_pages/page_01.png`, `page_02.png`, ...

### Step 2. 이미지 직접 보고 번역
- 추출된 PNG 이미지를 `view_file`로 직접 확인
- OCR 없이 원본 이미지에서 일본어를 읽고 번역
- `config/glossary.json` 용어집 참조

### 번역 규칙
- **100% 한국어만 출력** (일본어/중국어 절대 금지)
- **사이토 히토리 문체**: 하십시오체 + 해요체 혼용
- **번역투 제거**: '~의' 남용 금지, 자연스러운 능동형
- **극한의 단문**: 복문을 2~3개 짧은 단문으로 분리

### Step 3. 번역 결과 저장
결과를 `translated/antigravity/pages_{RANGE}.json` 에 저장

### Step 4. 대조 PDF 생성
저장된 JSON으로 원본/번역 대조 PDF 생성 → `translated/antigravity/대조본.pdf`

---

## 결과물 구조
```
translated/
├── llm/              ← 로컬 LLM (Qwen2.5-14B)
└── antigravity/      ← 안티그래비티 (PDF 이미지 직접)
```
