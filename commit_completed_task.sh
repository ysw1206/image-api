#!/bin/bash
# commit_completed_task.sh

TASK_ID="ea332f46-856d-48ec-81be-bb82d0d759d7"
PROJECT_ROOT=${1:-$(pwd)}

# Task 정보 추출
TASK_INFO=$(cat .shrimp/image-api/tasks.json | jq -r ".tasks[] | select(.id == \"$TASK_ID\")")

if [ "$TASK_INFO" = "" ]; then
    echo "Task ID $TASK_ID not found"
    exit 1
fi

TASK_NAME=$(echo $TASK_INFO | jq -r '.name')
TASK_SUMMARY=$(echo $TASK_INFO | jq -r '.summary // "No summary"')
TASK_STATUS=$(echo $TASK_INFO | jq -r '.status')
TASK_COMPLETED_AT=$(echo $TASK_INFO | jq -r '.completedAt // "Unknown"')

# 커밋 메시지 생성
COMMIT_MSG="✅ Complete task: $TASK_NAME

📋 Summary: $TASK_SUMMARY
🆔 Task ID: $TASK_ID
📅 Completed: $TASK_COMPLETED_AT
📊 Status: $TASK_STATUS"

# data/ 디렉토리에 커밋
cd data
git add tasks.json
git commit -m "$COMMIT_MSG"

# 프로젝트 루트에도 커밋 (선택사항)
cd "$PROJECT_ROOT"
echo "$PROJECT_ROOT"

git add .
git commit -m "$COMMIT_MSG"

echo "Task '$TASK_NAME' committed successfully"