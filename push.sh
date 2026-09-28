#!/bin/bash
# A股每日选股网页版 —— 自动推送到 GitHub Pages
#
# 触发：launchd 监视本目录（见 com.astock.site-push.plist），index.html 一变就跑；
#       另有工作日 05:40 / 06:40 兜底。也可以手动执行。
#
# 页面来源：Claude 的定时任务每天直接把 index.html 写进本目录。
#   （本目录刻意放在家目录根部而不是「文稿」下——「文稿」受 macOS TCC 保护，
#     launchd 拉起的 /bin/bash 读不到，会以退出码 126 静默失败。）
#
# 凭证完全依赖你本机的 git 配置（钥匙串），本脚本不保存也不读取任何密钥。

set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ARTIFACT="$HOME/Documents/Claude/Artifacts/a-stock-daily-screen-site/index.html"
LOG="$HOME/Library/Logs/astock-site-push.log"
LOCK="/tmp/astock-site-push.lock"

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') 触发 ==="

if ! mkdir "$LOCK" 2>/dev/null; then
  echo "已有任务在跑，跳过"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

sleep 45   # 防抖：等写入方落盘完毕

cd "$DIR" || { echo "进不去目录 $DIR"; exit 1; }
[ -d .git ] || { echo "还没 git init，先跑一次 setup.sh"; exit 1; }

# --- 1. 可选：若能读到 artifact 且比本地新，就同步过来 ---
#     手动运行时（终端有完全磁盘访问）通常可读；launchd 触发时大概率读不到，
#     属于正常情况，不当错误处理。
if [ -r "$ARTIFACT" ] && [ "$ARTIFACT" -nt index.html ] 2>/dev/null; then
  if cp "$ARTIFACT" index.html 2>/dev/null; then
    echo "已从 artifact 同步页面"
  fi
fi

if [ ! -f index.html ]; then
  echo "目录里没有 index.html，无可推送"; exit 1
fi

# --- 2. 有 xlsx 就打开页面上的下载按钮 ---
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
    m=re.search(r'\"date\": \"([0-9]{4}-[0-9]{2}-[0-9]{2})\"',s)
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
  echo "推送失败。常见原因：令牌过期或缺 workflow 权限（终端里手动跑一次 git push 看详情），或网络不通。"
  exit 1
fi
