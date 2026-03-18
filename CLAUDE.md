# CLAUDE.md — NAVI-Translate 프로젝트 규칙

## 프로젝트 개요
일본어 원서 PDF를 한국어로 번역하고 대조 PDF를 자동 생성하는 파이프라인.
PDF 페이지를 이미지로 추출 → AI가 직접 보고 번역 → 검증 → 대조 PDF 생성.

## 활성 코드 (수정 대상)
- `src/translate_pipeline.py` — 핵심 파이프라인 (MD→JSON→검증→대조PDF→로그)
- `src/prepare_pages.py` — PDF 페이지 이미지 추출
- `src/generate_comparison_pdf.py` — 원문/번역 대조 PDF 생성

## 레거시 코드 (참조만, 수정 금지)
- `src/_legacy/` — OCR 교정 테이블 등 참조 가치 있음. 삭제하지 말 것

## 번역 규칙 (엄수)
1. **100% 한국어만 출력** — 일본어/중국어 절대 금지
2. **사이토 히토리 문체** — 하십시오체 + 해요체 혼용, 따뜻한 대화체
3. **번역투 제거** — '~의' 남용 금지, 자연스러운 능동형
4. **극한의 단문** — 복문을 2~3개 짧은 단문으로 분리
5. **용어집 준수** — `config/glossary.json` 참조

## 번역 워크플로우
- 상세 절차: `agents/workflows/translate.md`
- 자동화 스킬: `.agent/skills/translate-chunk/SKILL.md`
- **10페이지 청크 단위**로 번역, 50페이지 초과 시 대화 분할

## 결과물 저장 경로
- Claude Code로 생성한 번역 결과물은 **`translated/antigravity/claude-code/`** 폴더에 저장
- 하위 폴더 구조: `claude-code/후아후아_v2/`, `claude-code/후아후아_v3/` 등 버전별 관리
- `translated/antigravity/후아후아_v1/`은 기존(레거시) 결과물 — 수정하지 말 것

## 파이프라인 사용법
```bash
# 올인원 빌드
python src/translate_pipeline.py build \
  --input translated/antigravity/translation_draft.md \
  --pdf data/pdf/원본.pdf \
  --pages 1-10

# 자동 git push 포함
python src/translate_pipeline.py build \
  --input ... --pdf ... --pages 1-10 --auto-push
```

## 커밋 규칙
- 자동 커밋/푸시는 `--auto-push` 플래그가 있을 때만 실행
- `.env` 파일은 절대 커밋하지 말 것
- `src/_legacy/extracted/`는 .gitignore에 포함 — 저작권 데이터

## 언어 규칙
- 사용자와의 대화: 한국어
- 코드, 커밋 메시지, 브랜치명: 영어
