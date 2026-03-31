# 📖 NAVI-Translate — 안티그래비티 번역 파이프라인

## 프로젝트 개요
일본어/독일어 원서 PDF를 한국어로 번역하고, 대조 PDF까지 자동 출력하는 번역 시스템입니다.
PDF 페이지를 **이미지로 직접 보고** 번역합니다 (OCR 없음).

## 기술 스택
- **Python 3.12+**, 가상환경: `.venv/`
- **핵심 라이브러리**: pymupdf(fitz), fpdf2, pillow
- **가상환경 활성화**: `.venv/Scripts/activate` (Windows)
- **Git 원격**: `https://github.com/NAVISCHOOL/translation.git`

## 프로젝트 구조
```
NAVI_Translate/
├── src/
│   ├── translate_pipeline.py        번역 파이프라인 (MD→JSON→검증→PDF)
│   ├── prepare_pages.py             페이지 이미지 추출
│   ├── language_profile.py          다국어 프로파일 관리
│   └── generate_comparison_pdf.py   대조 PDF 생성
├── config/
│   ├── glossary.json                일본어 용어집
│   ├── glossary_de.json             독일어 용어집
│   └── languages/                   언어별 프로파일 (ja.json, de.json)
├── data/                            원본 PDF 파일
├── translated/                      번역 결과물
│   ├── de-ko/우주소원/              독일어→한국어 번역
│   ├── ja-ko/후아후아_v5/           일본어→한국어 번역
│   ├── index.md                     번역 이력 테이블
│   └── translate-log.json           세션 로그
├── agents/workflows/                워크플로우 정의
│   └── translate.md                 ⭐ 전체 번역 프로세스 워크플로우
└── tmp_pages/                       임시 이미지 (Git 제외)
```

## 🔴 핵심 규칙

### 번역 워크플로우
사용자가 "번역해줘" 등 번역 요청 시 `agents/workflows/translate.md` 워크플로우를 따릅니다.

**전체 흐름**: PDF → 이미지 추출 → 이미지 보고 번역 → MD 저장 → 파이프라인 빌드 → Git 커밋

### 번역 규칙
- **100% 한국어만 출력** (원문 절대 금지)
- **문체**: 따뜻하고 대화체, 해요체 혼용
- **번역투 제거**: '~의' 남용 금지, 자연스러운 한국어
- **극한의 단문**: 복문을 2~3개 짧은 단문으로 분리
- **용어집 자동 적용**: `config/glossary.json` 또는 언어별 용어집

### 페이지 매핑 필수 규칙 (1:1 정합성)
1. **PDF 페이지 번호를 사용** — 책 내부 번호가 아닌 이미지 파일명 번호 기준
2. **이미지에 보이는 텍스트만 기록** — 다음 페이지로 이어져도 현재 이미지까지만
3. **`page_texts.json` 참조** — 페이지 경계 확인용

### 저장 경로 규칙
결과물은 `translated/{소스언어}-ko/{도서명}/` 아래에 저장:
- 독일어: `translated/de-ko/우주소원/translation_draft_우주소원_p{범위}.md`
- 일본어: `translated/ja-ko/후아후아_v5/translation_draft_후아후아_p{범위}.md`

### 마크다운 번역 형식
```markdown
## page 1
original: (원문)
translated: (한국어 번역)

## page 2
original: (원문)
translated: (한국어 번역)
```

## 지원 언어
- `ja` — 일본어 (프로파일: `config/languages/ja.json`)
- `de` — 독일어 (프로파일: `config/languages/de.json`)

## 현재 번역 진행 상황
| 도서 | 소스 | 총 페이지 | 완료 | 경로 |
|------|:---:|:---:|:---:|------|
| 우주소원 서비스 | 🇩🇪 | 160p | p1-150 | `translated/de-ko/우주소원/` |
| 후아후아 | 🇯🇵 | 63p | p1-42 | `translated/ja-ko/후아후아_v5/` |

## 자주 쓰는 명령어

```powershell
# 가상환경 활성화
.venv\Scripts\activate

# PDF 이미지 추출
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe src/prepare_pages.py -i "data/{PDF}" --pages {RANGE} --dpi 150 -o "tmp_pages"

# 파이프라인 빌드 (MD→JSON→검증→대조PDF→로그)
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe src/translate_pipeline.py build --input {MD} --pdf "data/{PDF}" --pages {RANGE} --lang {LANG}

# 기존 JSON 검증만
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe src/translate_pipeline.py validate --json {JSON} --pages {RANGE}

# Git 커밋 & 푸시
git add -A; git commit -m "feat: {도서명} p{범위} 번역 완료"; git push origin main
```

## 작업 완료 알람
10초 이상 소요되는 작업 완료 시:
```powershell
[console]::beep(1000, 500); [console]::beep(1200, 500); [console]::beep(1500, 700)
```
