#!/usr/bin/env bash
# ----------------------------------------------------------------------
# init_github.sh
#
# 一键初始化本地 git 仓库、创建首个 commit、新建 GitHub 远端仓库并 push。
#
# 使用前提：
#   1. 已安装并登录 GitHub CLI:  brew install gh && gh auth login
#   2. 在项目根目录执行: bash init_github.sh
#
# 可通过环境变量自定义：
#   REPO_NAME       默认: 当前目录名
#   REPO_VISIBILITY 默认: private  (public | private | internal)
#   REPO_DESC       默认: 自动生成的项目描述
#   REPO_OWNER      默认: 当前 gh 登录的用户名 / 组织
# ----------------------------------------------------------------------
set -euo pipefail

REPO_NAME="${REPO_NAME:-$(basename "$(pwd)")}"
REPO_VISIBILITY="${REPO_VISIBILITY:-private}"
REPO_DESC="${REPO_DESC:-多 Agent 客服自动化系统：AutoGen + LangGraph + LangChain + FastAPI}"
REPO_OWNER="${REPO_OWNER:-}"

echo "==> 仓库名:       $REPO_NAME"
echo "==> 可见性:       $REPO_VISIBILITY"
echo "==> 描述:         $REPO_DESC"

if ! command -v git >/dev/null 2>&1; then
  echo "❌ 未找到 git，请先安装 git。" >&2
  exit 1
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "❌ 未找到 GitHub CLI (gh)，请先安装：https://cli.github.com" >&2
  exit 1
fi

# 1) 初始化本地仓库
if [ ! -d ".git" ]; then
  echo "==> git init"
  git init -b main
fi

# 2) 创建 .gitkeep
mkdir -p data logs
touch data/.gitkeep logs/.gitkeep

# 3) 第一次提交
git add .
if git diff --cached --quiet; then
  echo "==> 没有变更需要提交"
else
  echo "==> git commit"
  git commit -m "feat: initial production-grade multi-agent customer service automation"
fi

# 4) 创建 GitHub 远端仓库（若未存在）
TARGET_FULL_NAME="${REPO_OWNER:+$REPO_OWNER/}$REPO_NAME"
TARGET_FULL_NAME="${TARGET_FULL_NAME%/}"
if [ -z "${REPO_OWNER}" ]; then
  TARGET_FULL_NAME="$REPO_NAME"
fi

if gh repo view "$TARGET_FULL_NAME" >/dev/null 2>&1; then
  echo "==> 远端仓库已存在: $TARGET_FULL_NAME"
else
  echo "==> 创建远端仓库: $TARGET_FULL_NAME ($REPO_VISIBILITY)"
  gh repo create "$TARGET_FULL_NAME" \
    --"$REPO_VISIBILITY" \
    --description "$REPO_DESC" \
    --source=. \
    --remote=origin \
    --push
  echo "==> ✅ 完成"
  exit 0
fi

# 5) 添加 origin 并推送
if ! git remote get-url origin >/dev/null 2>&1; then
  REMOTE_URL=$(gh repo view "$TARGET_FULL_NAME" --json sshUrl -q .sshUrl)
  echo "==> 添加 origin = $REMOTE_URL"
  git remote add origin "$REMOTE_URL"
fi

echo "==> git push"
git push -u origin main

echo "==> ✅ 完成: $TARGET_FULL_NAME"
