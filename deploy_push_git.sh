#!/bin/bash
# 自动推送 MkDocs 静态站点到远程 Git 仓库
set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# 1. 构建 MkDocs 静态站点
mkdocs build -f mkdocs.yml

# 2. 检查远程仓库地址
GIT_REMOTE_URL="git@github.com:roboticsystem/robotic_system_static.git"

if ! git remote | grep origin >/dev/null; then
  git remote add origin "$GIT_REMOTE_URL"
fi

git add .
git commit -m "auto: update static site $(date +'%F %T')" || true
git push origin master
