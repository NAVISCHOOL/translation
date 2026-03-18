---
name: translate-chunk
description: "Translate a chunk of PDF pages using Antigravity mode automatically"
---

# 번역 청크 자동화 스킬 (Translate Chunk)

이 스킬은 사용자가 "X~Y페이지 번역해줘" 또는 "이어서 10페이지 번역해줘" 와 같이 번역 진행 의사를 밝혔을 때, 시스템이 개입 없이 번역 청크(예: 10페이지 분량) 하나를 완벽히 소화하도록(Agentic Loop) 돕는 가이드입니다.

## 🚀 발동 조건
- 사용자가 대화창에 "11~20페이지 번역할게", "다음 분량 이어서 해줘" 등 자연어로 특정 구간 번역을 요청했을 때 즉시 발동합니다.
- 만약 PDF 파일 이름이 대화내역 상에 명확하지 않은 경우, "어떤 PDF의 페이지를 번역할까요?" 라고 구체적으로 물어 확인합니다.

## 📋 프로세스 (Agentic Loop)

이 스킬이 발동되면 당신은 멈추지 않고 아래 과정을 순차적으로 자동 실행해야 합니다:

### 1단계: 텍스트 추출 (Execution)
```bash
python src/prepare_pages.py -i data/pdf/{PDF_FILE} --pages {START}-{END}
```
- `/tmp/antigravity_pages/` 에 결과가 잘 저장되었는지 확인합니다 (`page_texts.json`, 이미지 파일들).

### 2단계: 무결점 초안 작성 (Planning & Execution)
- 텍스트 파일과 해당 페이지의 이미지들을 `Read` 도구로 열어서 맥락(문맥, 배경, 요소)을 확인합니다.
- **Self-Correction**: 생각(thought) 과정에서 "나는 작은 푸터, 헤더, 로고에 들어가는 아주 작은 텍스트까지 놓치지 않고 100% 번역했는가?" 자문하고 검증합니다.
- **Zero Omission**: 한 글자도 빠짐없이 번역. 이미지에 보이는 텍스트만 기록 (페이지 경계 엄수).
- 작성한 초안을 `translated/antigravity/translation_draft_[pdf_name]_p[start]-[end].md` 파일로 저장합니다.
- **단, Markdown을 저장할 때 무단으로 OS임시폴더(`/tmp/`등)을 사용해선 절대 안 됩니다.**

초안 MD 포맷:
```
## page N
original: (일본어 원문)
translated: (한국어 번역)
```

### 3단계: 파이프라인 빌드 (Execution)
```bash
python src/translate_pipeline.py build \
  --input "translated/antigravity/translation_draft_{PDF명}_p{START}-{END}.md" \
  --pdf "data/pdf/{PDF_FILE}" \
  --pages {START}-{END} \
  --output "translated/antigravity/pages_{START}-{END}.json" \
  --text-meta /tmp/antigravity_pages/page_texts.json
```
- 빌드 결과에 일본어 잔존 오류(`japanese_remnants`)나 페이지 유실 오류가 있는지 확인합니다.
- 오류가 있다면 2단계로 돌아가 번역을 수정하고 다시 빌드합니다 (최대 3회 재시도).

### 4단계: 완료 보고 (Verification)
- 위 단계를 모두 마치면, "X~Y페이지 번역과 대조본 생성을 완료했습니다." 라고 사용자에게 직접 텍스트로 알립니다.
- **Relay 제안**: 반드시 "다음 청크(Y+1 ~ Y+10페이지) 분량을 번역할까요?" 라고 이어서 질문합니다.

## ⚠️ 강제 규칙 (Strict Constraints)
1. **모든 내부 분석(Thought), 대화, 마크다운 산출물 작성 시 반드시 100% 한국어만 사용해야 합니다.**
2. 이 워크플로우를 도는 중에 사용자에게 쓸데없는 중간 보고를 하지 마세요. 4단계(최종)에서만 리포팅합니다.
3. 번역 규칙 (`config/glossary.json` 참고, 번역투 지양, 극한의 단문, 그리고 **Zero Omission**)을 목숨처럼 지킵니다.
4. **10페이지 청크 단위**로 번역합니다. 50페이지 초과 시 대화 세션을 분할합니다.
5. **페이지 매핑 3규칙**: ① PDF 페이지 번호 사용, ② 이미지에 보이는 텍스트만 기록, ③ `page_texts.json` 참조하여 경계 확인
