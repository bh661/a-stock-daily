#!/bin/bash
# A股每日选股网页版 —— 自动推送到 GitHub Pages
#
# 做三件事：
#   1. 把 Claude 每天更新的 artifact 页面复制进本仓库（artifact 路径固定，不随会话变）
#   2. 若本目录下有当日 xlsx，顺手打开页面上的「下载 xlsx」按钮
#   3. commit + push
#
# 由 launchd 在源文件变化时触发（见 com.astock.site-push.plist），也可以手动执行。
# 凭证完全依赖你本机的 git 配置（钥匙串 / SSH key），本脚本不保存也不读取任何密钥。

set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$HOME/Documents/Claude/Artifacts/a-stock-daily-screen-site/index.html"
LOG="$HOME/Library/Logs/astock-site-push.log"
LOCK="/tmp/astock-site-push.lock"

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') 触发 ==="

if ! mkdir "$LOCK" 2>/dev/null; then
  echo "已有任务在跑，跳过"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

sleep 45   # 防抖：等 Claude 那边写完

cd "$DIR" || { echo "进不去目录 $DIR"; exit 1; }
[ -d .git ] || { echo "还没 git init，先跑一次 setup.sh"; exit 1; }

# --- 1. 取最新页面 ---
if [ -f "$SRC" ]; then
  if [ ! -f index.html ] || ! cmp -s "$SRC" index.html; then
    cp "$SRC" index.html
    echo "已同步 artifact 页面"
  fi
else
  echo "警告：找不到 artifact 页面 $SRC （Claude 还没生成过？）"
fi

# --- 2. xlsx 下载按钮 ---
if [ -f latest.xlsx ]; then
  /usr/bin/sed -i '' 's/"xlsx": false/"xlsx": true/' index.html 2>/dev/null && echo "已开启 xlsx 下载按钮"
fi

# --- 3. 提交并推送 ---
if [ -z "$(git status --porcelain)" ]; then
  echo "没有变更，无需推送"; exit 0
fi

git add -A
MSG="自动更新 $(date '+%Y-%m-%d %H:%M')"
D=$(/usr/bin/python3 -c "
import re
try:
    s=open('index.html',encoding='utf-8').read(300000)
    m=re.search(r'\"date\": \"([0-9-]{8,10})\"',s)
    print(m.group(1) if m else '')
except Exception: print('')
" 2>/dev/null)
[ -n "$D" ] && MSG="更新至 $D 收盘快报"

git commit -q -m "$MSG" || { echo "commit 失败"; exit 1; }
echo "已提交：$MSG"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if git push origin "$BRANCH"; then
  echo "推送成功 -> origin/$BRANCH"
else
  echo "推送失败。常见原因：凭证过期（在终端手动跑一次 git push 重新登录）或网络不通。"
  exit 1
fi
