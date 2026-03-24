# 다국어 번역 지원 구현 계획

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NAVI-Translate 파이프라인에 독일어→한국어 번역 지원을 추가하고, 향후 다른 언어도 쉽게 추가할 수 있는 설정 기반 구조로 리팩토링한다.

**Architecture:** `config/languages.json`에 언어별 검증 패턴·글로서리·비율 기준을 정의하고, 파이프라인 코드에서 `--lang` 파라미터로 해당 설정을 로드하여 범용 검증을 수행한다.

**Tech Stack:** Python 3, PyMuPDF, fpdf2, JSON

---

## Task 1: 언어 설정 파일 생성

**Files:**
- Create: `config/languages.json`
- Create: `config/glossary_de.json`

- [ ] **Step 1: `config/languages.json` 생성**

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

- [ ] **Step 2: `config/glossary_de.json` 빈 용어집 생성**

```json
{}
```

---

## Task 2: `translate_pipeline.py` 리팩토링

**Files:**
- Modify: `src/translate_pipeline.py`

- [ ] **Step 1: `load_lang_config()` 함수 추가 (L28 부근)**

```python
def load_lang_config(lang: str = "ja") -> dict:
    """languages.json에서 언어 설정을 로드합니다. 하위호환: 파일 없으면 ja 기본값."""
    config_path = PROJECT_ROOT / "config" / "languages.json"
    if not config_path.exists():
        # 하위호환: languages.json 없으면 기존 일본어 기본값
        return {
            "name": "일본어",
            "detection_pattern": r"[\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\uFF66-\uFF9F]+",
            "detection_severity": "error",
            "glossary_file": "glossary.json",
            "sentence_endings": ["。", "！", "？", ")", "）", "」", "』", "…"],
            "len_ratio": {"warn": 1.5, "error": 2.0, "missing": 0.3},
        }
    with open(config_path, "r", encoding="utf-8") as f:
        langs = json.load(f)
    if lang not in langs:
        available = ", ".join(langs.keys())
        raise ValueError(f"지원하지 않는 언어: {lang}. 지원 언어: {available}")
    return langs[lang]
```

- [ ] **Step 2: `JAPANESE_PATTERN` 하드코딩 제거, `load_glossary_exceptions()` 수정**

기존:
```python
JAPANESE_PATTERN = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\uFF66-\uFF9F]+')

def load_glossary_exceptions() -> set[str]:
    glossary_path = PROJECT_ROOT / "config" / "glossary.json"
```

변경:
```python
# JAPANESE_PATTERN 삭제 (언어 설정에서 동적 로드)

def load_glossary_exceptions(lang_config: dict = None) -> set[str]:
    """글로서리에 등록된 번역어를 예외 목록으로 로드합니다."""
    glossary_file = (lang_config or {}).get("glossary_file", "glossary.json")
    glossary_path = PROJECT_ROOT / "config" / glossary_file
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)
        return set(glossary.values())
    return set()
```

- [ ] **Step 3: `validate_translations()` 함수에 `lang` 파라미터 추가**

시그니처 변경:
```python
def validate_translations(pages, expected_range=None, pdf_path=None, lang="ja"):
```

검증 섹션 1 (일본어 잔존) → 범용 소스 언어 잔존 감지:
```python
    lang_config = load_lang_config(lang)
    source_pattern = re.compile(lang_config["detection_pattern"])
    severity = lang_config.get("detection_severity", "error")
    lang_name = lang_config["name"]

    # ── 1. 소스 언어 잔존 감지 ──
    source_remnant_count = 0
    empty_count = 0
    for entry in pages:
        pn = entry["page"]
        text = entry.get("translated", "")

        if not text.strip():
            errors.append(f"p.{pn}: 번역 텍스트가 비어 있습니다")
            empty_count += 1
            continue

        matches = source_pattern.findall(text)
        if matches:
            for m in matches:
                msg = f"p.{pn}: {lang_name} 잔존 감지: '{m}' → 한국어로 교체 필요"
                if severity == "error":
                    errors.append(msg)
                else:
                    warnings.append(msg)
            source_remnant_count += len(matches)

    qa_scores[f"{lang_name}_잔존"] = 0 if source_remnant_count == 0 else source_remnant_count
```

검증 섹션 3 (문장 끊김) — 문장 끝 판정 문자를 설정에서 로드:
```python
    endings = tuple(lang_config.get("sentence_endings", ["。", ".", "!", "?"]))
    # ...
    if curr_orig and not curr_orig.rstrip().endswith(endings):
```

검증 섹션 4 (용어집) — 언어별 글로서리 파일 사용:
```python
    glossary_file = lang_config.get("glossary_file", "glossary.json")
    glossary_path = PROJECT_ROOT / "config" / glossary_file
```

검증 섹션 6 (정합성) — 언어별 비율 기준:
```python
    ratio_config = lang_config.get("len_ratio", {"warn": 1.5, "error": 2.0, "missing": 0.3})
    # ...
    if len_ratio > ratio_config["error"]:
        # ❌ 에러
    elif len_ratio > ratio_config["warn"]:
        # ⚠️ 경고
    elif len_ratio < ratio_config["missing"] and pdf_len > 30:
        # ⚠️ 누락 의심
```

- [ ] **Step 4: `cmd_build()`에 `--lang` 전달**

```python
result = validate_translations(pages, page_range, pdf_path=args.pdf, lang=args.lang)
```

로그에 언어 정보 추가:
```python
session = {
    ...
    "lang": args.lang,
    ...
}
```

- [ ] **Step 5: CLI에 `--lang` 옵션 추가**

`p_build`에:
```python
p_build.add_argument("--lang", "-l", default="ja", help="소스 언어 코드 (기본: ja, 지원: ja/de)")
```

`p_val`에:
```python
p_val.add_argument("--lang", "-l", default="ja", help="소스 언어 코드 (기본: ja)")
```

`cmd_validate()`에:
```python
result = validate_translations(pages, page_range, pdf_path=getattr(args, 'pdf', None), lang=args.lang)
```

- [ ] **Step 6: 콘솔 메시지 동적화**

`ANTI-JAPANESE` 문구를 범용으로 변경:
```python
lang_config = load_lang_config(args.lang)
print(f"\n🔍 ANTI-{lang_config['name'].upper()} 검증 중...")
# ...
print(f"   ✅ 검증 통과 ({result['page_count']}페이지, {lang_config['name']} 잔존 0)")
```

---

## Task 3: `generate_comparison_pdf.py` 수정

**Files:**
- Modify: `src/generate_comparison_pdf.py`

- [ ] **Step 1: Windows 폰트 경로 추가**

```python
FONT_SEARCH_PATHS = [
    # macOS
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    # Windows
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
    # Linux
    "/usr/share/fonts/truetype",
    os.path.expanduser("~/.fonts"),
]

FONT_CANDIDATES = {
    "regular": ["NanumSquare_acR.ttf", "NanumSquareR.ttf", "NanumGothic.ttf", "malgun.ttf", "gulim.ttc"],
    "bold": ["NanumSquareEB.ttf", "NanumSquare_acB.ttf", "NanumGothicBold.ttf", "malgunbd.ttf"],
}
```

- [ ] **Step 2: 대조 PDF 라벨에 언어명 추가**

`generate_comparison_pdf()` 시그니처에 `lang` 파라미터 추가:
```python
def generate_comparison_pdf(original_pdf, translations, output_path, page_range=None, lang="ja"):
```

`ComparisonPDF`에 언어명 전달:
```python
pdf = ComparisonPDF(lang_name=lang_name)
```

라벨 변경:
```python
self.cell(half_width, 6, f"[원문 - {self.lang_name}] p.{page_num}", align="C")
```

- [ ] **Step 3: `build_comparison_pdf()` 호출부 수정 (translate_pipeline.py)**

```python
def build_comparison_pdf(json_path, pdf_path, page_range, lang="ja"):
    # ...
    generate_comparison_pdf(pdf_path, translations, output_path, page_range, lang=lang)
```

---

## Task 4: 워크플로우 업데이트

**Files:**
- Modify: `agents/workflows/translate.md`

- [ ] **Step 1: 번역 시작 프롬프트에 언어 선택 추가**

기존 프롬프트 뒤에 언어 선택 테이블 추가:
```markdown
> 📚 소스 언어:
> | 코드 | 언어 |
> |:---:|------|
> | ja | 일본어 (기본) |
> | de | 독일어 |
```

- [ ] **Step 2: Step 4 파이프라인 명령에 `--lang` 추가**

```bash
source .venv/bin/activate && python src/translate_pipeline.py build \
  --input translated/antigravity/translation_draft_{PDF명}_{RANGE}.md \
  --pdf data/pdf/{PDF_FILE} \
  --pages {PAGE_RANGE} \
  --lang {LANG_CODE} \
  --output translated/antigravity/pages_{RANGE}.json
```

---

## Task 5: README.md 업데이트

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 다국어 지원 섹션 추가**

번역 방식 테이블 아래에:
```markdown
### 지원 언어

| 소스 언어 | 타겟 언어 | 검증 | 상태 |
|----------|----------|------|------|
| 🇯🇵 일본어 | 🇰🇷 한국어 | ANTI-JAPANESE (error) | ✅ 안정 |
| 🇩🇪 독일어 | 🇰🇷 한국어 | ANTI-GERMAN (warning) | 🔧 신규 |
```
