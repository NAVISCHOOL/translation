# 📖 NAVI-Translate

**나비스쿨 × 사이토 히토리 서적 번역 파이프라인**

일본어 원서 PDF를 다양한 엔진으로 번역하고, 대조 PDF까지 자동 출력하는 번역 시스템입니다.

## 🏗️ 프로젝트 구조

```
NAVI-Translate/
├── src/                         ← 핵심 스크립트
│   ├── extract_pdf.py              PDF → 일본어 텍스트 추출 (PyMuPDF)
│   ├── translate.py                Ollama + Qwen2.5-14B 로컬 번역
│   ├── translate_gemini.py         Gemini Vision API 번역 (OCR 불필요)
│   ├── prepare_pages.py            안티그래비티 모드 준비 (이미지/텍스트)
│   ├── save_translation.py         안티그래비티 번역 결과 저장
│   ├── compare.py                  원문/번역 대조 뷰어 (CLI)
│   ├── generate_pdf.py             번역본 → 한국어 PDF
│   └── generate_comparison_pdf.py  원본/번역 대조 PDF
│
├── config/glossary.json         ← 사이토 히토리 전용 용어집 (21항목)
├── .env                         ← Gemini API 키 (git 제외)
├── agents/workflows/translate.md← 번역 워크플로우
│
├── data/pdf/                    ← 원본 PDF
├── extracted/                   ← 추출 결과
└── translated/                  ← 번역 결과
    ├── llm/                        자동화 번역 (PyMuPDF/Gemini OCR)
    └── antigravity/                안티그래비티 직접 번역
```

## ⚡ 번역 모드

### 1. LLM 모드 — 자동 번역

#### 1a) PyMuPDF OCR → Qwen2.5-14B (완전 오프라인)
```bash
python src/extract_pdf.py -i data/pdf/후아후아.pdf -o ./extracted
python src/translate.py -i extracted/extracted_pages.json --pages 1-63 -o translated/llm/output.txt
```

#### 1b) Gemini Vision → 직접 번역 (고품질 OCR)
```bash
python src/translate_gemini.py -i data/pdf/후아후아.pdf --pages 1-63
```

### 2. 안티그래비티 모드 — 대화형 고품질 번역
```
"번역해줘" → 모드 선택 → 안티그래비티가 PDF 이미지를 직접 보고 번역
```

### 3. 대조 PDF 생성
```bash
python src/generate_comparison_pdf.py \
  --original data/pdf/후아후아.pdf \
  --translation translated/llm/output.json \
  --pages 1-63 -o translated/llm/대조본.pdf
```

## ⚙️ 환경 설정

```bash
# 1. Python 패키지
python3 -m venv .venv && source .venv/bin/activate
pip install pymupdf requests fpdf2 google-genai python-dotenv

# 2. Ollama + Qwen (LLM 모드 1a용)
brew install ollama && brew services start ollama && ollama pull qwen2.5:14b

# 3. Gemini API 키 (LLM 모드 1b용)
echo "GEMINI_API_KEY=YOUR_KEY" > .env
```

## 📋 핵심 기능

| 기능 | 설명 |
|------|------|
| OCR 전처리 v2.0 | 60개+ 한자 오인식 교정, 세로쓰기 복원, 노이즈 제거 |
| Gemini Vision | OCR 없이 이미지에서 직접 번역 (세로쓰기 완벽) |
| 용어집 자동 로딩 | `config/glossary.json` → 프롬프트에 자동 주입 |
| 일본어 잔류 방지 | 프롬프트 + 후처리 이중 안전장치 |
| 대조 PDF | 원본 이미지(왼) + 한국어(오) 나란히 배치 |

## 📊 성능 (M1 Max 32GB)

| 모드 | 63페이지 소요 시간 | 비용 |
|------|:-:|:-:|
| LLM (Qwen2.5-14B) | ~11분 | ₩0 |
| Gemini Vision | ~5분 | ₩0 (무료 API) |
| 안티그래비티 | 대화형 | ₩0 |
