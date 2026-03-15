---
description: 사용자가 "번역해줘"라고 요청하면 페이지 범위를 물어보고 안티그래비티 번역을 진행하는 워크플로우
---

# 번역 워크플로우

사용자가 "번역해줘", "번역 진행해" 등 번역 관련 요청을 하면 **페이지 범위를 물어봅니다**:

> 어떤 걸 번역해드릴까요? 📖
>
> - 현재 PDF: `후아후아_20251210-part-1-ocr.pdf` (63페이지)
> - 페이지 범위를 알려주세요! (예: 1-63 전체, 8 단일 페이지)

---

## 번역 진행

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
└── antigravity/      ← 번역 결과
```
