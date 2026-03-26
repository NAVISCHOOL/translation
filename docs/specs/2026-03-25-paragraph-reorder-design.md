# Paragraph Reorder Design

## Problem
우주소원_ko 대조본에서 번역 텍스트의 단락 순서가 원본 PDF의 시각적 순서와 다름.
AI 번역가가 논리적 순서로 재배열하여, 대조본 좌(원본이미지)↔우(번역) 비교가 어려움.

- 영향 범위: 143개 본문 페이지 중 8개 (5.6%)
- 주요 패턴: 챕터 시작 페이지 (장번호 vs 제목 순서), 표지 페이지

## Solution

### 1. 자동 보정 스크립트 (`src/reorder_paragraphs.py`)

**입력**: pages_*.json + 원본 PDF
**출력**: 단락 순서가 보정된 pages_*.json

**알고리즘**:
1. PyMuPDF `get_text('blocks')` → 텍스트 블록을 좌표순 추출 (위→아래, 왼→오른)
2. 인접 블록 병합 → "시각적 단락" 목록 생성
3. JSON `original` 각 단락 ↔ 시각적 단락 fuzzy-match (SequenceMatcher)
4. 매칭 신뢰도 > 0.4 → 시각적 순서로 `original` + `translated` 동시 재배열
5. 매칭 실패 → skip + warning

**안전장치**:
- `--dry-run` (기본값): 변경 미리보기만
- `--apply`: 실제 적용, `.bak` 백업 생성
- 텍스트 내용 불변, 순서만 변경

### 2. 번역 워크플로우 규칙 추가

`agents/workflows/translate.md`에 추가:
> 원본 PDF의 시각적 순서(위→아래)를 그대로 유지하여 번역할 것.
> 논리적 재배열 금지.

### 3. 대조본 재생성

보정된 JSON으로 `대조본_*.pdf`를 다시 생성.

## Decision: 장 번호 위치
PDF 시각적 순서 그대로 (제목이 먼저 나오면 제목 먼저, 번호가 먼저면 번호 먼저).
