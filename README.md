# 📖 NAVI-Translate

**나비스쿨 × 사이토 히토리 서적 번역 파이프라인**

일본어 원서 PDF를 한국어로 번역하고, 대조 PDF까지 자동 출력하는 번역 시스템입니다.

---

## 💬 어떻게 쓰나요?

안티그래비티에게 **"번역해줘"** 라고 말하면 됩니다.

```
👤 사용자: 번역해줘

🤖 안티그래비티: 어떤 모드로 번역할까요?

    1. Gemini Vision — 자동 번역 (무료 API, 최고 품질)
    2. 안티그래비티 모드 — PDF 이미지를 직접 보고 번역 (최고 품질, 대화형)

    페이지 범위도 알려주세요! (예: 1-63 전체, 10 단일)

👤 사용자: 1번으로 1-10페이지

🤖 안티그래비티: (Gemini Vision으로 p.1~10 자동 번역 시작...)
```

---

## ❓ 모드가 뭐가 다른 건가요?

### Q. "Gemini Vision" 이 뭐예요?
> PDF 페이지를 **이미지로** Gemini API에 보냅니다. OCR 단계가 아예 없어서 **세로쓰기도 완벽**!
> Gemini가 이미지를 보고 읽기와 번역을 한번에 처리합니다.

```bash
# 예시: p.1~10 Gemini 번역 (~1분)
python src/translate_gemini.py -i data/pdf/후아후아.pdf --pages 1-10
```

#### 💰 Gemini API 무료 한도 (2.0 Flash 기준)
| 한도 | 수치 | 번역 가능량 |
|------|:---:|------|
| 분당 | 15요청 | 15페이지/분 |
| **일일** | **1,500요청** | **하루 23권** (63p 기준) |

> 63페이지 책 한 권 = 63요청 → 일일 한도의 **4.2%만** 사용. 전혀 부족하지 않아요!

### Q. "안티그래비티 모드" 는요?
> 안티그래비티가 PDF 이미지를 **직접 눈으로 보고** 번역합니다. 대화하면서 진행돼요.
> 가장 품질이 높지만, 자동화는 아니에요. 표지나 특수 페이지에 적합합니다.

```
👤 사용자: 안티그래비티 모드로 p.8 번역해줘
🤖 안티그래비티: (p.8 이미지를 보고...)

    머리말

    지금 마음이 무겁습니까?
    지금 자신이나 주변에 불만이 있습니까?
    ...
```

---

## 📊 모드 비교

| | 1) Gemini Vision | 2) 안티그래비티 |
|---|:---:|:---:|
| **속도** | 63p / ~5분 | 대화형 |
| **품질** | ★★★★★ | ★★★★★ |
| **비용** | ₩0 (무료 API) | ₩0 |
| **인터넷** | ✅ 필요 | ✅ 필요 |
| **자동화** | ✅ 완전 자동 | ❌ 수동 |
| **세로쓰기** | ✅ 완벽 | ✅ 완벽 |
| 일일 한도 | ~23권/일 | 무제한 |

### Q. 어떤 걸 써야 하나요?

> **대량 자동 번역** → 1) Gemini Vision (추천!)
> **표지·특수 페이지·문맥 조정** → 2) 안티그래비티 모드

---

## ⚙️ 처음 설정은 어떻게 하나요?

### Q. 기본 패키지 설치
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pymupdf requests fpdf2 google-genai python-dotenv
```

### Q. Gemini API 키 설정
1. [Google AI Studio](https://aistudio.google.com/apikey)에서 무료 API 키 발급
2. `.env` 파일에 입력:
```
GEMINI_API_KEY=여기에_키_입력
```

---

## 🏗️ 프로젝트 구조

```
NAVI-Translate/
├── src/                          ← 핵심 스크립트
│   ├── translate_gemini.py          Gemini Vision 번역 (추천)
│   ├── translate_local_vision.py    로컬 Vision 번역 (예정)
│   ├── translate.py                 PyMuPDF+Qwen 로컬 번역 (레거시)
│   ├── extract_pdf.py               PDF → 텍스트 추출
│   ├── prepare_pages.py             안티그래비티 이미지 준비
│   ├── save_translation.py          번역 결과 저장
│   ├── compare.py                   원문/번역 대조 (CLI)
│   ├── generate_pdf.py              번역본 PDF
│   └── generate_comparison_pdf.py   대조 PDF
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
| Gemini Vision | OCR 없이 이미지에서 직접 번역 (추천) |
| 안티그래비티 모드 | PDF를 직접 보고 대화형 번역 |
| 용어집 자동 로딩 | `config/glossary.json` → 프롬프트 주입 |
| 일본어 잔류 방지 | 프롬프트 + 후처리 이중 안전장치 |
| 대조 PDF | 원본(왼) + 한국어(오) 나란히 배치 |

---

## 🔮 예정 기능

| 기능 | 상태 | 비고 |
|------|:---:|------|
| 로컬 Vision 번역 (오프라인) | 🔧 실험적 | `translate_local_vision.py` 구현 완료, Qwen2.5-VL 7B 기반. 현재 세로쓰기 인식률 낮음 → 더 큰 모델(32B+) 또는 일본어 특화 모델 출시 시 개선 예정 |
| PyMuPDF+Qwen 모드 | ⏸️ 레거시 | OCR 오인식률 높아 사용 비추천. 코드는 유지 |
