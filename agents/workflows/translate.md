---
description: NAVI-Translate 전체 번역 프로세스 워크플로우 — PDF 원서를 한국어로 번역하고 검증, 대조 PDF, Git 커밋까지 자동화
---

# 📖 NAVI-Translate 전체 번역 프로세스 워크플로우

## 0. 전체 흐름 요약

```
[원서 PDF] → [이미지 추출] → [이미지 읽고 번역] → [MD 저장] → [파이프라인 빌드] → [Git 커밋]
                Step 1           Step 2           Step 3         Step 4            Step 5
```

---

## Phase 1: 번역 준비

### Step 0. 사용자 요청 수신

사용자가 "번역해줘" 등 번역 요청 시 아래 형식으로 **PDF와 페이지 범위를 물어봅니다**:

> 어떤걸 번역 해드릴까요? 그리고 페이지 범위를 알려주세요!
>
> | 번호 | PDF | 총 페이지 | 소스 언어 |
> |:---:|------|:---:|:---:|
> | 00 | 후아후아_20251210-part-1-ocr.pdf | 63p | 🇯🇵 |
> | 01 | 우주소원 서비스 - 독일어 원서.pdf | 160p | 🇩🇪 |
>
> (예: 01pdf 51-100, 00pdf 1-63 전체)

⚠️ `data/` 및 `data/pdf/` 폴더의 PDF 목록을 검색해서 번호를 자동 매핑합니다.
⚠️ 언어는 `config/languages/` 폴더의 프로파일에서 감지합니다. 사용 가능: `ja`(일본어), `de`(독일어)

---

## Phase 2: 번역 실행

// turbo-all

### Step 1. PDF 페이지를 이미지+텍스트로 추출

```powershell
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe src/prepare_pages.py -i "data/{PDF_FILE}" --pages {PAGE_RANGE} --dpi 150 -o "tmp_pages"
```

출력:
- 이미지: `tmp_pages/page_01.png`, `page_02.png`, ...
- 텍스트: `tmp_pages/page_texts.json` (정합성 검증용 ground truth)

### Step 2. 이미지 직접 보고 번역

🔴 **페이지 매핑 필수 규칙** — 1:1 정합성 보장

1. **PDF 페이지 번호를 사용할 것** — 책 하단의 "p.2", "p.6" 같은 *책 내부 번호*가 아니라, 이미지 파일명의 번호(`page_05.png` = page 5)를 따를 것
2. **이미지에 보이는 텍스트만 기록할 것** — 문장이 다음 페이지로 이어져도, 현재 이미지에 보이는 부분까지만 original에 기록
3. **`page_texts.json` 참조할 것** — Step 1에서 추출된 텍스트를 참고하여 페이지 경계 확인

⚠️ **10페이지 청크 규칙** — 컨텍스트 오버플로 방지

전체 페이지를 **10페이지 단위**로 나눠서 번역합니다:
- 각 청크 시작 시 `config/glossary.json` (또는 `glossary_de.json`) 용어집을 **다시 읽고** 프롬프트에 포함
- 추출된 PNG 이미지를 `view_file`로 **5장씩 병렬** 확인
- OCR 없이 원본 이미지에서 원문을 직접 읽고 번역
- 한 청크(10p) 번역 완료 → **즉시 Step 3으로 가서 MD 저장** → 다음 청크 진행

```
160페이지 예시 (세션 분할 포함):
  [세션 1]
    청크 1: p.1-10   → 번역 → MD 저장
    청크 2: p.11-20  → 번역 → MD 저장
    청크 3: p.21-30  → 번역 → MD 저장
    청크 4: p.31-40  → 번역 → MD 저장
    청크 5: p.41-50  → 번역 → MD 저장
    → Step 4 파이프라인 빌드 (p1-10, p11-20, ...)
    → Step 5 Git 커밋

  [세션 2]
    p.51-100 → 동일 과정 반복
  
  [세션 3]
    p.101-160 → 동일 과정 반복
```

⚠️ **50페이지 초과 시 대화 세션 분할**

총 페이지가 50p를 넘으면 **대화 세션을 나눠서** 진행합니다.
각 세션 시작 시 **"번역해줘, 01pdf, 51-100"** 형식으로 이어가기.

### 번역 규칙

| 규칙 | 설명 |
|------|------|
| 언어 | **100% 한국어만 출력** (원문 절대 금지) |
| 문체 | 따뜻하고 대화체, 해요체 혼용 |
| 번역투 제거 | '~의' 남용 금지, 자연스러운 능동형 |
| 단문화 | 복문을 2~3개 짧은 단문으로 분리 |
| 용어집 | `config/glossary.json` 또는 언어별 용어집 자동 적용 |

### Step 3. 번역 결과를 마크다운으로 저장

⚠️ **JSON을 직접 작성하지 말 것!** 아래 형식의 마크다운 파일을 `write_to_file`로 작성합니다:

```markdown
## page 1
original: (원문)
translated: (한국어 번역)

## page 2
original: (원문)
translated: (한국어 번역)
```

### 저장 경로 규칙

결과물은 **`translated/{소스언어}-ko/{도서명}/`** 아래에 저장합니다:

```
translated/
├── de-ko/                          ← 🇩🇪 독일어→한국어
│   └── 우주소원/
│       ├── translation_draft_우주소원_p1-10.md
│       ├── translation_draft_우주소원_p11-20.md
│       └── ...
├── ja-ko/                          ← 🇯🇵 일본어→한국어
│   └── 후아후아_v5/
│       ├── translation_draft_후아후아_p1-10.md
│       └── ...
├── index.md                        ← 번역 이력 테이블 (자동 업데이트)
└── translate-log.json              ← 세션 로그 (자동 생성)
```

**경로 예시:**
- 독일어 원서: `translated/de-ko/우주소원/translation_draft_우주소원_p51-60.md`
- 일본어 원서: `translated/ja-ko/후아후아_v5/translation_draft_후아후아_p1-10.md`

---

## Phase 3: 검증 & 빌드

### Step 4. 파이프라인 빌드 (검증 + JSON + 대조 PDF + 로그)

```powershell
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe src/translate_pipeline.py build `
  --input "translated/{소스언어}-ko/{도서명}/translation_draft_{도서명}_{RANGE}.md" `
  --pdf "data/{PDF_FILE}" `
  --pages {PAGE_RANGE} `
  --lang {LANG_CODE} `
  --output "translated/{소스언어}-ko/{도서명}/pages_{RANGE}.json"
```

이 한 커맨드가 자동으로:
1. ✅ MD → 안전한 JSON 변환 (이스케이프 오류 0)
2. ✅ 잔존 검증 (언어 프로파일 기반 — 일본어/독일어/기타)
3. ✅ **페이지 정합성 검증** (1:1 매칭 — 글자수 비율 비교)
4. ✅ 대조 PDF 생성
5. ✅ translate-log.json 세션 기록
6. ✅ translated/index.md 이력 업데이트

### Step 5. 검증 실패 시 수정

파이프라인이 잔존 오류를 보고하면:
1. 에러 메시지에서 해당 페이지와 잔존 원문 확인
2. 해당 translation_draft MD 파일에서 해당 페이지만 수정
3. Step 4 다시 실행

---

## Phase 4: 저장 & 배포

### Step 6. Git 커밋 & 푸시

작업 완료 후 (또는 세션 종료 시):

```powershell
cd C:\Users\admin\Desktop\안티그래비티 개발\japanese translation\NAVI_Translate
git add -A
git commit -m "feat: {도서명} p{범위} 번역 완료"
git push origin main
```

**원격 레포지토리**: `https://github.com/NAVISCHOOL/translation.git`

---

## 부록

### A. 지원 언어 & 프로파일

| 코드 | 언어 | 프로파일 | 용어집 |
|:---:|------|---------|-------|
| `ja` | 🇯🇵 일본어 | `config/languages/ja.json` | `config/glossary.json` |
| `de` | 🇩🇪 독일어 | `config/languages/de.json` | `config/glossary_de.json` |

### B. 현재 번역 진행 상황

| 도서 | 소스 | 총 페이지 | 완료 | 경로 |
|------|:---:|:---:|:---:|------|
| 우주소원 서비스 (Bestellungen beim Universum) | 🇩🇪 | 160p | p1-150 | `translated/de-ko/우주소원/` |
| 후아후아 (ふわふわ) | 🇯🇵 | 63p | p1-42 | `translated/ja-ko/후아후아_v5/` |

### C. 핵심 소스 파일

| 파일 | 역할 |
|------|------|
| `src/translate_pipeline.py` | 메인 파이프라인 (MD→JSON→검증→대조PDF→로그) |
| `src/prepare_pages.py` | PDF → 페이지 이미지 + 텍스트 추출 |
| `src/language_profile.py` | 다국어 프로파일 로딩 & 프롬프트 생성 |
| `src/generate_comparison_pdf.py` | 원문/번역 대조 PDF 생성 |

### D. 자주 쓰는 명령어

```powershell
# 가상환경 활성화
.venv\Scripts\activate

# PDF 이미지 추출
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe src/prepare_pages.py -i "data/{PDF}" --pages {RANGE} --dpi 150 -o "tmp_pages"

# 파이프라인 빌드
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe src/translate_pipeline.py build --input {MD} --pdf "data/{PDF}" --pages {RANGE} --lang {LANG}

# 기존 JSON 검증만
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe src/translate_pipeline.py validate --json {JSON} --pages {RANGE}

# Git 커밋 & 푸시
git add -A; git commit -m "feat: {도서명} p{범위} 번역 완료"; git push origin main
```

### E. 작업 완료 알람

10초 이상 소요되는 작업 완료 시:
```powershell
[console]::beep(1000, 500); [console]::beep(1200, 500); [console]::beep(1500, 700)
```
