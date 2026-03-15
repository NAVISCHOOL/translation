# 📖 NAVI-Translate

**나비스쿨 × 사이토 히토리 서적 번역 파이프라인**

일본어 원서 PDF를 한국어로 번역하고, 대조 PDF까지 자동 출력하는 번역 시스템입니다.

---

## 💬 어떻게 쓰나요?

안티그래비티에게 **"번역해줘"** 라고 말하면 됩니다.

```
👤 사용자: 번역해줘

🤖 안티그래비티: 페이지 범위를 알려주세요! (예: 1-63 전체, 10 단일)

👤 사용자: 1-10페이지

🤖 안티그래비티: (p.1 이미지를 보고 번역 시작...)
```

안티그래비티가 PDF 페이지를 **이미지로 직접 보고** 번역합니다.
OCR 단계가 없어서 세로쓰기도 완벽하게 인식합니다.

---

## 📊 번역 방식

| 항목 | 설명 |
|------|------|
| **방식** | PDF → 이미지 → 안티그래비티가 직접 보고 번역 |
| **품질** | ★★★★★ |
| **비용** | ₩0 |
| **세로쓰기** | ✅ 완벽 |
| **자동화** | ✅ 페이지 순회 자동 번역 |

### 번역 규칙
- **100% 한국어만 출력** (일본어/중국어 절대 금지)
- **사이토 히토리 문체**: 따뜻하고 대화체, 해요체 혼용
- **번역투 제거**: '~의' 남용 금지, 자연스러운 한국어
- **극한의 단문**: 복문을 2~3개 짧은 단문으로 분리
- **용어집 자동 적용**: `config/glossary.json` (21항목)

---

## ⚙️ 처음 설정

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pymupdf requests fpdf2 python-dotenv
```

---

## 🏗️ 프로젝트 구조

```
NAVI-Translate/
├── src/
│   ├── prepare_pages.py             페이지 이미지 추출
│   ├── save_translation.py          번역 결과 저장
│   ├── generate_pdf.py              번역본 PDF
│   ├── generate_comparison_pdf.py   대조 PDF
│   ├── compare.py                   원문/번역 대조 (CLI)
│   ├── translate_gemini.py          Gemini Vision 자동 번역 (예정)
│   ├── translate_local_vision.py    로컬 Vision 오프라인 번역 (예정)
│   ├── translate.py                 PyMuPDF+Qwen 번역 (레거시)
│   └── extract_pdf.py               PDF 텍스트 추출 (레거시)
│
├── config/glossary.json           ← 용어집 (21항목)
├── .env                           ← API 키 (git 제외)
├── agents/workflows/translate.md  ← 번역 워크플로우
│
├── data/pdf/                      ← 원본 PDF
├── extracted/                     ← 추출 결과
└── translated/
    ├── llm/                         자동화 결과
    └── antigravity/                 안티그래비티 결과
```

---

## 📋 핵심 기능

| 기능 | 설명 |
|------|------|
| 안티그래비티 번역 | PDF를 직접 보고 자동/대화형 번역 |
| 용어집 자동 로딩 | `config/glossary.json` → 프롬프트 주입 |
| 일본어 잔류 방지 | 프롬프트 + 후처리 이중 안전장치 |
| 대조 PDF | 원본(왼) + 한국어(오) 나란히 배치 |

---

## 🧪 왜 OCR을 안 쓰나요?

기존 OCR 방식을 모두 테스트했지만, **안티그래비티가 직접 보는 게 가장 정확**했습니다.

### 실험 결과 요약

| 시도 | 방식 | 결과 |
|------|------|------|
| ① PyMuPDF OCR → Qwen | PDF 내장 텍스트 추출 → 로컬 LLM 번역 | ❌ 세로쓰기 OCR 깨짐. `景色`→`屎色` 등 오인식 다수. 60개+ 교정 테이블로도 한계 |
| ② Gemini Vision API | PDF 이미지 → Gemini가 직접 보고 번역 | ✅ 품질 최고 (4.4초/p). 하지만 안티그래비티와 본질적으로 동일 |
| ③ 로컬 Vision (Qwen2.5-VL 7B) | PDF 이미지 → 로컬 모델이 보고 번역 | ❌ 세로쓰기 인식률 낮음. 반복 출력 심각 (78초/p) |

> **결론**: OCR 단계를 없애고, AI가 이미지를 직접 보는 것이 정답.
> Gemini Vision도 좋지만 안티그래비티와 같은 방식이라 통합 → **안티그래비티 하나로 심플하게.**

---

## 🔮 예정 기능

| 기능 | 상태 | 비고 |
|------|:---:|------|
| Gemini Vision 자동 번역 | 🔧 구현 완료 | `translate_gemini.py` — API 키로 일괄 자동 번역. 63p/5분 |
| 로컬 Vision 오프라인 번역 | 🔧 실험적 | `translate_local_vision.py` — Qwen2.5-VL 7B. 더 큰 모델 출시 시 개선 예정 |
| PyMuPDF+Qwen 번역 | ⏸️ 레거시 | `translate.py` — OCR 오인식률 높아 비추천 |
