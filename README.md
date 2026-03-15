# 📖 NAVI-Translate

**나비스쿨 × 사이토 히토리 서적 번역 파이프라인**

일본어 원서 PDF를 로컬 LLM(Qwen2.5-14B)으로 번역하고, 대조 PDF까지 자동 출력하는 완전 무료 번역 시스템입니다.

## 🏗️ 프로젝트 구조

```
NAVI-Translate/
├── README.md                  ← 이 파일
├── .gitignore
├── GEMINI.md                  ← 안티그래비티 설정
│
├── src/                       ← 핵심 스크립트
│   ├── extract_pdf.py            PDF → 일본어 텍스트 추출
│   ├── translate.py              Ollama + Qwen2.5-14B 번역 엔진
│   ├── compare.py                원문/번역 대조 뷰어 (CLI)
│   ├── generate_pdf.py           번역본 → 한국어 PDF
│   └── generate_comparison_pdf.py 원본/번역 대조 PDF
│
├── config/                    ← 설정 파일
│   └── glossary.json             사이토 히토리 전용 용어집
│
├── data/pdf/                  ← 원본 PDF (OCR 처리 완료)
│   └── 후아후아_20251210-part-1-ocr.pdf
│
├── extracted/                 ← 추출 결과 (자동 생성)
│   ├── extracted_pages.json      페이지별 텍스트
│   └── full_text_jp.txt          전체 원문 텍스트
│
└── translated/                ← 번역 결과 (자동 생성)
    ├── full_output.txt           한국어 번역 텍스트
    ├── full_output.json          원문/번역 대조 JSON
    └── 후아후아_대조본_전체.pdf    원본/번역 대조 PDF (63p)
```

## ⚙️ 환경 설정

```bash
# 1. 가상환경 + 패키지
python3 -m venv .venv
source .venv/bin/activate
pip install pymupdf requests fpdf2

# 2. Ollama + Qwen2.5-14B (~9GB)
brew install ollama
brew services start ollama
ollama pull qwen2.5:14b
```

## 🚀 워크플로우 (4단계)

### Step 1. PDF 텍스트 추출
```bash
python src/extract_pdf.py -i data/pdf/후아후아_20251210-part-1-ocr.pdf -o ./extracted
```

### Step 2. 번역 (로컬 LLM)
```bash
# 전체 번역 (~11분)
python src/translate.py -i extracted/extracted_pages.json -o ./translated/full_output.txt

# 특정 페이지만
python src/translate.py -i extracted/extracted_pages.json --pages 10-20
```

### Step 3. 대조 확인
```bash
# CLI 대조 뷰어
python src/compare.py -i translated/full_output.json

# 마크다운 내보내기
python src/compare.py -i translated/full_output.json --export translated/comparison.md
```

### Step 4. PDF 생성
```bash
# 원본/번역 대조 PDF (가로 A4, 나란히)
python src/generate_comparison_pdf.py \
  --original data/pdf/후아후아_20251210-part-1-ocr.pdf \
  --translation translated/full_output.json \
  --pages 1-63 \
  -o translated/후아후아_대조본_전체.pdf

# 번역본 단독 PDF
python src/generate_pdf.py -i translated/full_output.json -o translated/후아후아_번역.pdf
```

## 📋 핵심 기능

| 기능 | 설명 |
|------|------|
| OCR 전처리 v2.0 | 60개+ 한자 오인식 교정, 세로쓰기 복원, 노이즈 제거 |
| 용어집 자동 로딩 | `config/glossary.json` → 시스템 프롬프트에 자동 주입 |
| 일본어 잔류 방지 | 프롬프트 + 후처리 이중 안전장치 |
| 대조 PDF 생성 | 원본 이미지(왼) + 한국어(오) 나란히 배치 |

## 📊 성능 (M1 Max 32GB)

| 항목 | 수치 |
|------|------|
| 전체 63페이지 | **11.1분** |
| 번역 속도 | 20.1 tok/s |
| 비용 | **₩0** (완전 로컬) |
| 엔진 | Qwen2.5-14B (Ollama, Apache 2.0) |
