#!/bin/bash
# 一次性安装脚本：把本目录变成一个推向 GitHub Pages 的 git 仓库，并装上自动推送的定时任务。
#
# 用法（在「终端」里执行）：
#   bash ~/Documents/astock-site/setup.sh https://github.com/你的用户名/仓库名.git
#
# 执行前请先在 github.com 上建好一个**空的公开仓库**（不要勾 README / .gitignore / license）。

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE="${1:-}"

if [ -z "$REMOTE" ]; then
  echo "用法: bash $DIR/setup.sh <仓库地址>"
  echo "例:   bash $DIR/setup.sh https://github.com/yourname/astock-site.git"
  exit 1
fi

cd "$DIR"

echo "==> 1/5 初始化 git 仓库"
SRC="$HOME/Documents/Claude/Artifacts/a-stock-daily-screen-site/index.html"
if [ -f "$SRC" ]; then
  cp "$SRC" index.html
  echo "    已同步当前 artifact 页面"
fi
if [ ! -d .git ]; then
  git init -q
fi
git symbolic-ref HEAD refs/heads/main 2>/dev/null || true
git add -A
git -c user.useConfigOnly=false commit -q -m "初始化：A股每日选股网页版" || echo "    （没有新变更，跳过提交）"

echo "==> 2/5 绑定远端"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE"
else
  git remote add origin "$REMOTE"
fi
echo "    origin = $(git remote get-url origin)"

echo "==> 3/5 推送到 GitHub（这一步会让你登录 / 授权，凭证存进你的钥匙串，我看不到）"
git push -u origin main

echo "==> 4/5 安装自动推送的定时任务（launchd）"
PLIST_SRC="$DIR/com.astock.site-push.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.astock.site-push.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
sed -e "s|__DIR__|$DIR|g" -e "s|__HOME__|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"
chmod +x "$DIR/push.sh"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "    已加载 com.astock.site-push（目录一有变化就推送，另有工作日 05:40 / 06:40 兜底）"

echo "==> 5/5 最后一步要你手动点两下（GitHub 没开放这个的免登录接口）"
USER_REPO=$(echo "$REMOTE" | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')
GH_USER=$(echo "$USER_REPO" | cut -d/ -f1)
GH_REPO=$(echo "$USER_REPO" | cut -d/ -f2)
cat <<EOF

  打开  https://github.com/$USER_REPO/settings/pages
  Source 选  "Deploy from a branch"
  Branch 选  main  +  / (root)   → Save

  等 1-2 分钟后，你的网址就是：

      https://$GH_USER.github.io/$GH_REPO/

  （公开仓库，任何人拿到链接都能访问，不需要 GitHub 账号。）

安装完成。之后每个交易日收盘后 Claude 写入 index.html，定时任务会自动推送上去。
查看推送日志： tail -f ~/Library/Logs/astock-site-push.log
EOF
