# 📖 NAVI-Translate — 안티그래비티 번역 파이프라인

## 프로젝트 개요
일본어/독일어 원서 PDF를 한국어로 번역하고, 대조 PDF까지 자동 출력하는 번역 시스템입니다.
PDF 페이지를 **이미지로 직접 보고** 번역합니다 (OCR 없음).

## 기술 스택
- **Python 3.12+**, 가상환경: `.venv/`
- **핵심 라이브러리**: pymupdf(fitz), fpdf2, pillow
- **가상환경 활성화**: `.venv/Scripts/activate` (Windows)

## 프로젝트 구조
```
NAVI_Translate/
├── src/
│   ├── translate_pipeline.py        번역 파이프라인 (MD→JSON→검증→PDF)
│   ├── prepare_pages.py             페이지 이미지 추출
│   ├── language_profile.py          다국어 프로파일 관리
│   └── generate_comparison_pdf.py   대조 PDF 생성
├── config/
│   ├── glossary.json                일본어 용어집 (21항목)
│   ├── glossary_de.json             독일어 용어집
│   ├── languages.json               언어 설정
│   └── languages/                   언어별 프로파일 (ja.json, de.json 등)
├── data/pdf/                        원본 PDF 파일
├── translated/                      번역 결과물
│   ├── ja/antigravity/              일본어 번역 결과
│   └── de/antigravity/              독일어 번역 결과
└── agents/workflows/                워크플로우 정의
```

## 🔴 핵심 규칙

### 번역 워크플로우
사용자가 "번역해줘" 등 번역 요청 시 `agents/workflows/translate.md` 워크플로우를 따릅니다:

1. **PDF와 페이지 범위를 물어봅니다** — `data/pdf/` 폴더의 PDF 목록을 보여주고 선택하게 합니다
2. **PDF → 이미지 추출**: `python src/prepare_pages.py -i data/pdf/{PDF} --pages {RANGE} --dpi 150`
3. **이미지 직접 보고 번역**: 10페이지 청크 단위, `config/glossary.json` 용어집 적용
4. **마크다운으로 저장**: `translated/{lang}/antigravity/` 아래에 저장 (/tmp/ 사용 금지)
5. **파이프라인 빌드**: `python src/translate_pipeline.py build --input {MD} --pdf {PDF} --pages {RANGE} --lang {LANG}`

### 번역 규칙
- **100% 한국어만 출력** (일본어/중국어/독일어 절대 금지)
- **사이토 히토리 문체**: 따뜻하고 대화체, 해요체 혼용
- **번역투 제거**: '~의' 남용 금지, 자연스러운 한국어
- **극한의 단문**: 복문을 2~3개 짧은 단문으로 분리
- **용어집 자동 적용**: `config/glossary.json`

### 페이지 매핑 필수 규칙 (1:1 정합성)
1. **PDF 페이지 번호를 사용** — 책 내부 번호가 아닌 이미지 파일명 번호 기준
2. **이미지에 보이는 텍스트만 기록** — 다음 페이지로 이어져도 현재 이미지까지만
3. **`page_texts.json` 참조** — 페이지 경계 확인용

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
- `ja` — 일본어 (기본)
- `de` — 독일어

언어 프로파일: `config/languages/` 폴더

## 자주 쓰는 명령어

```bash
# 가상환경 활성화 (Windows)
.venv\Scripts\activate

# PDF 이미지 추출
python src/prepare_pages.py -i data/pdf/{PDF} --pages {RANGE} --dpi 150

# 파이프라인 빌드 (MD→JSON→검증→대조PDF→로그)
python src/translate_pipeline.py build --input {MD} --pdf data/pdf/{PDF} --pages {RANGE} --lang {LANG}

# 기존 JSON 검증만
python src/translate_pipeline.py validate --json {JSON} --pages {RANGE}

# 언어 프로파일 확인
python src/language_profile.py {LANG_CODE}
```

## 작업 완료 알람
10초 이상 소요되는 작업 완료 시 비프음을 울립니다:
```powershell
[console]::beep(1000, 500); [console]::beep(1200, 500); [console]::beep(1500, 700)
```
