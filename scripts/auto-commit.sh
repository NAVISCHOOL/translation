#!/bin/bash
#
# NAVI-Translate Auto Commit & Push Script
# (NAVI-Research에서 이식)
#
# 파일 변경 감지 시 자동으로 커밋하고 GitHub에 push합니다.
#
# 사용법:
#   ./scripts/auto-commit.sh          # 포그라운드 실행
#   ./scripts/auto-commit.sh start    # 백그라운드 실행
#   ./scripts/auto-commit.sh stop     # 백그라운드 중지
#   ./scripts/auto-commit.sh status   # 실행 상태 확인
#
# 설정:
INTERVAL=30          # 변경 감지 간격 (초)
COOLDOWN=60          # 변경 후 대기 시간 (초) — 이 시간 동안 추가 변경이 없으면 커밋
BRANCH="main"        # push할 브랜치
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_DIR/.git/auto-commit.pid"
LOG_FILE="$PROJECT_DIR/.git/auto-commit.log"

# 색상
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${CYAN}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

generate_commit_message() {
    local added=$(git -C "$PROJECT_DIR" diff --cached --name-only --diff-filter=A | wc -l | tr -d ' ')
    local modified=$(git -C "$PROJECT_DIR" diff --cached --name-only --diff-filter=M | wc -l | tr -d ' ')
    local deleted=$(git -C "$PROJECT_DIR" diff --cached --name-only --diff-filter=D | wc -l | tr -d ' ')
    local files=$(git -C "$PROJECT_DIR" diff --cached --name-only | head -3 | tr '\n' ', ' | sed 's/,$//')

    local parts=()
    [[ $added -gt 0 ]] && parts+=("${added} added")
    [[ $modified -gt 0 ]] && parts+=("${modified} modified")
    [[ $deleted -gt 0 ]] && parts+=("${deleted} deleted")

    local summary=$(IFS=', '; echo "${parts[*]}")
    echo "auto: ${summary} — ${files}"
}

has_changes() {
    cd "$PROJECT_DIR" || return 1
    ! (git diff --quiet && git diff --cached --quiet && [[ -z $(git ls-files --others --exclude-standard) ]])
}

do_auto_commit() {
    cd "$PROJECT_DIR" || exit 1

    if ! has_changes; then
        return 0
    fi

    log "⏳ Changes detected, waiting ${COOLDOWN}s for more changes..."
    local waited=0
    while [[ $waited -lt $COOLDOWN ]]; do
        sleep 10
        waited=$((waited + 10))
        if has_changes && [[ $(git diff --stat 2>/dev/null | wc -l) -gt 0 || $(git ls-files --others --exclude-standard | wc -l) -gt 0 ]]; then
            local new_count=$(git status --short | wc -l | tr -d ' ')
            log "   ...still changing (${new_count} files), resetting cooldown"
            waited=0
        fi
    done

    # 내부에 .git이 있는 서브디렉토리를 자동으로 .gitignore에 추가
    local gitignore="$PROJECT_DIR/.gitignore"
    for dir in $(find "$PROJECT_DIR" -mindepth 2 -name ".git" -type d 2>/dev/null); do
        local parent=$(dirname "$dir")
        local rel=$(python3 -c "import os; print(os.path.relpath('$parent', '$PROJECT_DIR'))")
        if ! grep -qx "${rel}/" "$gitignore" 2>/dev/null; then
            echo "${rel}/" >> "$gitignore"
            log "🚫 Auto-ignored embedded repo: ${rel}/"
        fi
    done

    git add -A

    if git diff --cached --quiet; then
        return 0
    fi

    local msg=$(generate_commit_message)
    git commit -m "$msg" > /dev/null 2>&1

    if [[ $? -eq 0 ]]; then
        log "✅ Committed: $msg"
        git push origin "$BRANCH" > /dev/null 2>&1
        if [[ $? -eq 0 ]]; then
            log "🚀 Pushed to origin/$BRANCH"
        else
            log "⚠️  Push failed (will retry next cycle)"
        fi
    fi
}

watch_loop() {
    log "🔄 Auto-commit started (interval: ${INTERVAL}s, branch: ${BRANCH})"
    log "📂 Watching: $PROJECT_DIR"
    log "🛑 Stop with: $0 stop"
    echo ""

    while true; do
        do_auto_commit
        sleep "$INTERVAL"
    done
}

case "${1:-}" in
    start)
        if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo -e "${YELLOW}⚠️  Already running (PID: $(cat "$PID_FILE"))${NC}"
            exit 1
        fi
        echo -e "${GREEN}🚀 Starting auto-commit in background...${NC}"
        nohup "$0" > /dev/null 2>&1 &
        echo $! > "$PID_FILE"
        echo -e "${GREEN}✅ Started (PID: $!)${NC}"
        echo -e "${CYAN}   Log: tail -f $LOG_FILE${NC}"
        echo -e "${CYAN}   Stop: $0 stop${NC}"
        ;;
    stop)
        if [[ -f "$PID_FILE" ]]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID"
                rm -f "$PID_FILE"
                echo -e "${GREEN}✅ Stopped auto-commit (PID: $PID)${NC}"
            else
                rm -f "$PID_FILE"
                echo -e "${YELLOW}⚠️  Process was not running. Cleaned up PID file.${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  No auto-commit process found.${NC}"
        fi
        ;;
    status)
        if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo -e "${GREEN}✅ Running (PID: $(cat "$PID_FILE"))${NC}"
            echo -e "${CYAN}   Log (last 5 lines):${NC}"
            tail -5 "$LOG_FILE" 2>/dev/null || echo "   (no log yet)"
        else
            echo -e "${YELLOW}⏹  Not running${NC}"
        fi
        ;;
    *)
        watch_loop
        ;;
esac
