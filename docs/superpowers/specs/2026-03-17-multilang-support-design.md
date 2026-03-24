# 다국어 번역 지원 설계 (Multi-Language Support)

> **날짜:** 2026-03-17
> **상태:** 승인됨

## 목표

현재 일본어→한국어 전용인 NAVI-Translate 파이프라인을 **언어 설정 시스템 기반**으로 리팩토링하여 독일어→한국어 번역도 지원하도록 합니다.

## 핵심 원칙

1. **하위호환 100%**: 기존 일본어 번역 워크플로우는 아무것도 바꾸지 않아도 동작
2. **설정 기반 확장**: 새 언어 추가 시 `config/languages.json`에 항목 추가만으로 대응
3. **언어별 검증 수준**: 일본어(error 레벨), 독일어(warning 레벨) — 오탐 위험에 따라 차등

## 아키텍처

### 언어 설정 파일 (`config/languages.json`)

```json
{
  "ja": {
    "name": "일본어",
    "detection_pattern": "[\\u3040-\\u309F\\u30A0-\\u30FF\\u31F0-\\u31FF\\uFF66-\\uFF9F]+",
    "detection_severity": "error",
    "glossary_file": "glossary.json",
    "sentence_endings": ["。", "！", "？", ")", "）", "」", "』", "…"],
    "len_ratio": {"warn": 1.5, "error": 2.0, "missing": 0.3},
    "style_guide": "사이토 히토리 문체: 따뜻하고 대화체, 해요체 혼용. 극한의 단문."
  },
  "de": {
    "name": "독일어",
    "detection_pattern": "[äöüÄÖÜß]{2,}|(?:[A-Za-zäöüÄÖÜß]+ ){4,}(?:ist|sind|hat|wird|kann|muss|soll)",
    "detection_severity": "warning",
    "glossary_file": "glossary_de.json",
    "sentence_endings": [".", "!", "?", "…"],
    "len_ratio": {"warn": 2.5, "error": 3.5, "missing": 0.2},
    "style_guide": "자연스러운 한국어. 번역투 제거. 단문 위주."
  }
}
```

### 검증 전략

| 언어 | 감지 대상 | 심각도 | 이유 |
|------|----------|--------|------|
| 일본어 | 히라가나/카타카나 | error | 한국어 텍스트에 절대 나타나지 않음 |
| 독일어 | 움라우트 연속 / 4단어+ 독일어 문장 | warning | 라틴 문자 공유로 오탐 가능 |

### 글자수 비율 기준

| 언어 | warn | error | missing |
|------|------|-------|---------|
| 일본어 | 1.5x | 2.0x | 0.3x |
| 독일어 | 2.5x | 3.5x | 0.2x |

## 변경 파일

| 파일 | 변경 유형 |
|------|----------|
| `config/languages.json` | 신규 생성 |
| `config/glossary.json` | 변경 없음 (하위호환) |
| `config/glossary_de.json` | 신규 생성 (빈 용어집) |
| `src/translate_pipeline.py` | 수정 (범용 검증, --lang CLI) |
| `src/generate_comparison_pdf.py` | 수정 (동적 라벨, Windows 폰트) |
| `agents/workflows/translate.md` | 수정 (언어 선택 단계) |
| `README.md` | 수정 (다국어 지원 문서화) |
