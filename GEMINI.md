@./skills/using-superpowers/SKILL.md
@./skills/using-superpowers/references/gemini-tools.md

# 🔴 슈퍼파워즈 자동 발동 규칙 (MANDATORY)

**개발 작업(코드 수정, 기능 추가, 버그 수정, 파이프라인 개선 등)을 시작할 때:**
1. 반드시 `skills/` 폴더의 관련 스킬을 먼저 읽을 것
2. `writing-plans` → `executing-plans` → `verification-before-completion` 순서를 따를 것
3. 사용자가 "슈퍼파워즈"를 언급하지 않아도 자동 발동할 것

**행동 및 출력 규칙 (Strict Compliance):**
1. **100% 한국어화**: 모든 내부 분석(Thought), 대화, 마크다운 산출물(task, walkthrough, log 등) 작성 시 반드시 한국어만 사용.
2. **경로 이탈 금지(No /tmp)**: 프로젝트 공식 결과물(초안, JSON, PDF 등)을 절대 OS 임시 폴더(`/tmp/`, `~/Desktop` 등)에 무단으로 저장하지 않고 반드시 워크플로우에 명시된 공식 경로만 사용.

**이 규칙은 대화가 길어져 truncation되어도 반드시 지켜야 합니다.**
