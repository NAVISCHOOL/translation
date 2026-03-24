---
description: 모든 bash/터미널 명령어를 사용자 승인 없이 자동 실행하는 설정
---

# 자동 승인 모드

// turbo-all

이 워크플로우가 활성화되면 **모든 `run_command` 호출에 `SafeToAutoRun: true`를 설정**하여 사용자 승인 없이 즉시 실행합니다.

## 적용 범위

아래 명령어들을 자동 승인합니다:

1. **파일 탐색**: `ls`, `dir`, `cat`, `type`, `find`, `fd`, `tree` 등
2. **빌드/실행**: `python`, `node`, `npm`, `pip`, `cargo` 등
3. **Git 명령어**: `git status`, `git log`, `git diff`, `git add`, `git commit`, `git push` 등
4. **패키지 설치**: `pip install`, `npm install` 등
5. **서버 실행**: `npm run dev`, `python -m http.server` 등
6. **파일 생성/수정**: `mkdir`, `cp`, `mv`, `touch` 등
7. **기타 모든 터미널 명령어**

## 사용법

사용자가 아래와 같이 요청하면 이 워크플로우를 활성화합니다:
- "자동 승인 켜줘"
- "터보 모드"
- "명령어 자동 실행"
- "/auto-approve"

활성화되면 대화 전체에서 모든 명령어가 자동 실행됩니다.

## 주의사항

⚠️ 시스템 수준의 위험한 명령어(예: `rm -rf /`, `format`, 레지스트리 수정 등)는 여전히 주의가 필요합니다.
