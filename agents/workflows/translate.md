---
description: 사용자가 "번역해줘"라고 요청하면 PDF와 페이지 범위를 물어보고 안티그래비티 번역을 진행하는 워크플로우
---

# 번역 워크플로우

사용자가 "번역해줘", "번역 진행해" 등 번역 관련 요청을 하면 아래 형식으로 **PDF와 페이지 범위를 물어봅니다**:

> 어떤걸 번역 해드릴까요? 그리고 페이지 범위를 알려주세요!
>
> | 번호 | PDF | 페이지 |
> |:---:|------|:---:|
> | 00 | 후아후아_20251210-part-1-ocr.pdf | 63p |
>
> (예: 00pdf 1-63 전체, 00pdf 10 단일)

⚠️ `data/pdf/` 폴더의 PDF 목록을 검색해서 번호를 자동 매핑합니다.
사용자가 **"00Pdf, 1-10페이지"** 같은 형식으로 답변하면 즉시 번역을 시작합니다.

---

## 번역 진행

### Step 1. PDF 페이지를 이미지+텍스트로 추출
```bash
source .venv/bin/activate && python src/prepare_pages.py -i data/pdf/{PDF_FILE} --pages {PAGE_RANGE}
```
작은 글씨가 많은 PDF라면 `--dpi 200` 옵션을 추가하세요.

출력:
- 이미지: `/tmp/antigravity_pages/page_01.png`, `page_02.png`, ...
- 텍스트: `/tmp/antigravity_pages/page_texts.json` (정합성 검증용 ground truth + 소형/가로 텍스트 메타데이터)

### Step 2. 이미지 직접 보고 번역

🔴 **페이지 매핑 필수 규칙** — 1:1 정합성 보장

1. **PDF 페이지 번호를 사용할 것** — 책 하단의 "p.2", "p.6" 같은 *책 내부 번호*가 아니라, 이미지 파일명의 번호(`page_05.png` = page 5)를 따를 것
2. **이미지에 보이는 텍스트만 기록할 것** — 문장이 다음 페이지로 이어져도, 현재 이미지에 보이는 부분까지만 original에 기록. 나머지는 다음 페이지 original에 기록
3. **`page_texts.json` 참조할 것** — Step 1에서 추출된 텍스트를 참고하여 페이지 경계 확인. 드래프트 원문 글자수가 PDF 글자수의 1.5배를 초과하면 경계 오류 의심

🔴 **번역 품질 규칙**

- **Zero Omission (무결점 번역)**: 이미지에 보이는 모든 텍스트를 번역. 본문, 헤더, 푸터, 각주, 로고 텍스트 포함. 작은 글씨도 빠짐없이.
- **Self-Correction**: 초안 작성 후, 생각(thought) 과정에서 "작은 텍스트, 로고, 헤더, 푸터를 빠뜨리지 않았는가?" 반드시 자문하고 검증.

⚠️ **10페이지 청크 규칙** — 컨텍스트 오버플로 방지

전체 페이지를 **10페이지 단위**로 나눠서 번역합니다:
- 각 청크 시작 시 `config/glossary.json` 용어집을 **다시 읽고** 프롬프트에 포함
- 추출된 PNG 이미지를 `Read` 도구로 **5장씩 병렬** 확인
- OCR 없이 원본 이미지에서 일본어를 읽고 번역
- 한 청크(10p) 번역 완료 → **즉시 Step 3으로 가서 MD 저장** → 다음 청크 진행

```
63페이지 예시:
  청크 1: p.1-10   → 번역 → MD 저장
  청크 2: p.11-20  → 번역 → MD 저장 (append)
  청크 3: p.21-30  → 번역 → MD 저장 (append)
  ...
  청크 7: p.61-63  → 번역 → MD 저장 (append)
```

이렇게 하면 컨텍스트에 최대 10페이지분의 이미지만 유지되어 **품질이 균일**합니다.

⚠️ **50페이지 초과 시 대화 분할**

총 페이지가 50p를 넘으면 **대화 세션을 나눠서** 진행합니다:
- 세션 1: p.1-50 → `translated/antigravity/translation_draft_{PDF명}_p1-50.md`에 저장
- 세션 2: p.51-100 → 같은 MD 파일에 append
- 각 세션 시작 시 **"번역해줘, 00pdf, 51-100"** 형식으로 이어가기
- Step 4(파이프라인)는 **마지막 세션에서 한 번만** 실행

### 번역 규칙
- **100% 한국어만 출력** (일본어/중국어 절대 금지)
- **사이토 히토리 문체**: 하십시오체 + 해요체 혼용
- **번역투 제거**: '~의' 남용 금지, 자연스러운 능동형
- **극한의 단문**: 복문을 2~3개 짧은 단문으로 분리

🔴 **기호 변환 규칙** (`config/symbol_map.json` 참조)

| 구분 | 기호 | 처리 |
|------|------|------|
| 보존 | `「」` `『』` `…` | 그대로 유지 |
| 변환 | `、`→`,` `。`→`.` `！`→`!` `？`→`?` `（）`→`()` `・`→`·` `〜`→`~` | 반각으로 변환 |
| 금지 | `「」`→`""` `""` `''` | 절대 금지 — 큰따옴표/스마트 따옴표로 바꾸지 말 것 |
| 금지 | 책 페이지 번호 | 번역문에 포함하지 말 것 (예: 끝에 단독 숫자 "42") |

### Step 3: 초안 저장

번역 MD 파일 포맷:
```markdown
## page N
original: (일본어 원문 — 해당 이미지에 보이는 텍스트만)
translated: (한국어 번역)
```

저장 경로: `translated/antigravity/translation_draft_[pdf-name]_p[start]-[end].md`

### Step 4. 파이프라인 빌드 (검증 + JSON + 대조 PDF + 로그)

```bash
source .venv/bin/activate && python src/translate_pipeline.py build \
  --input translated/antigravity/translation_draft_{PDF명}_{RANGE}.md \
  --pdf data/pdf/{PDF_FILE} \
  --pages {PAGE_RANGE} \
  --output translated/antigravity/pages_{RANGE}.json
```

이 한 커맨드가 자동으로:
1. ✅ MD → 안전한 JSON 변환 (이스케이프 오류 0)
2. ✅ ANTI-JAPANESE 검증 (일본어 잔존 감지)
3. ✅ **페이지 정합성 검증** (1:1 매칭 — 글자수 비율 비교)
4. ✅ **소형·가로 텍스트 커버리지 검증** (작은 글씨/가로 텍스트 누락 감지)
5. ✅ 대조 PDF 생성
6. ✅ translate-log.json 세션 기록
7. ✅ translated/index.md 이력 업데이트

### Step 5. 검증 실패 시 수정

파이프라인이 ANTI-JAPANESE 오류를 보고하면:
1. 에러 메시지에서 해당 페이지와 잔존 일본어 확인
2. `translated/antigravity/translation_draft_*.md`에서 해당 페이지만 수정
3. Step 4 다시 실행
4. **최대 3회 재시도** — 3회 실패 시 사용자에게 수동 확인 요청

---

## 결과물 구조
```
translated/
├── index.md                              ← 번역 이력 테이블 (자동 업데이트)
├── translate-log.json                    ← 세션 로그 (자동 생성)
└── antigravity/                          ← 모든 결과물 집중
    ├── translation_draft_*_p1-63.md      ← 번역 드래프트 (원문+번역 쌍)
    ├── pages_1-63.json                   ← 번역 데이터 JSON
    └── 대조본_p1-63.pdf                  ← 원문/번역 대조 PDF
```
