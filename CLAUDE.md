# CLAUDE.md — NAVI-Translate 프로젝트 규칙

## 프로젝트 개요
다국어 원서 PDF를 한국어로 번역하고 대조 PDF를 자동 생성하는 파이프라인.
PDF 페이지를 이미지로 추출 → AI가 직접 보고 번역 → 검증 → 대조 PDF 생성.
지원 언어: 일본어(ja-ko), 독일어(de-ko), 영어(en-ko 향후)

## 활성 코드 (수정 대상)
- `src/translate_pipeline.py` — 핵심 파이프라인 (MD→JSON→검증→대조PDF→로그)
- `src/prepare_pages.py` — PDF 페이지 이미지 추출
- `src/generate_comparison_pdf.py` — 원문/번역 대조 PDF 생성
- `src/reorder_paragraphs.py` — 번역 단락 순서 보정 (PDF 시각적 순서 기준)

## 레거시 코드 (참조만, 수정 금지)
- `src/_legacy/` — OCR 교정 테이블 등 참조 가치 있음. 삭제하지 말 것

## 언어 프로파일
- `config/languages/ja-ko.json` — 일본어→한국어 (후아후아 시리즈)
- `config/languages/de-ko.json` — 독일어→한국어 (우주소원)
- 새 언어 추가 시 JSON 파일만 생성, 코드 수정 불필요

## 번역 규칙 (공통, 엄수)
1. **100% 한국어만 출력** — 원문 스크립트 잔존 금지
2. **번역투 제거** — '~의' 남용 금지, 자연스러운 능동형
3. **극한의 단문** — 복문을 2~3개 짧은 단문으로 분리
4. **시각적 순서 유지** — 원본 페이지 순서 그대로, 논리적 재배열 금지
5. **용어집 준수** — 언어 프로파일의 glossary 참조

## 번역 워크플로우
- 상세 절차: `agents/workflows/translate.md`
- **10페이지 청크 단위**로 번역, 50페이지 초과 시 대화 분할

## 결과물 저장 경로
```
translated/
├── ja-ko/              ← 일본어→한국어
│   ├── 후아후아_v1/     ← 레거시 결과물 (수정 금지)
│   ├── 후아후아_v2~v5/  ← 각 권 번역
│   └── claude-code_후아후아_v2/
├── de-ko/              ← 독일어→한국어
│   └── 우주소원/
├── index.md            ← 번역 이력 (공통)
└── translate-log.json  ← 세션 로그 (공통)
```

## 파이프라인 사용법
```bash
# 올인원 빌드 (--lang 필수!)
python src/translate_pipeline.py build \
  --input translated/ja-ko/후아후아_v2/translation_draft.md \
  --pdf data/pdf/후아후아.pdf \
  --pages 1-10 \
  --lang ja-ko

# 독일어 번역
python src/translate_pipeline.py build \
  --input translated/de-ko/우주소원/translation_draft.md \
  --pdf "data/pdf/우주소원 서비스 - 독일어 원서.pdf" \
  --pages 1-10 \
  --lang de-ko
```

## 커밋 규칙
- 자동 커밋/푸시는 `--auto-push` 플래그가 있을 때만 실행
- `.env` 파일은 절대 커밋하지 말 것
- `src/_legacy/extracted/`는 .gitignore에 포함 — 저작권 데이터

## 언어 규칙
- 사용자와의 대화: 한국어
- 코드, 커밋 메시지, 브랜치명: 영어
