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

# --- 1. 找最新的页面来源，三级兜底 ---
#
#   主路径：Claude 的定时任务直接把 index.html 写进本目录（需要它连接过本文件夹）
#   兜底A ：Claude 会话的 outputs 目录里的 site.html —— 任务每天必然会生成它，
#           且 ~/Library 不受 TCC 保护，launchd 读得到，**不需要任何授权**
#   兜底B ：artifact 落盘文件（在 ~/Documents 下，launchd 通常读不到，仅手动运行时有效）
#
#   三者都只在「比当前 index.html 新」时才覆盖，避免旧文件把新页面顶回去。

take () {  # $1 = 候选文件
  [ -r "$1" ] || return 1
  [ -s "$1" ] || return 1
  grep -q 'A股每日条件选股' "$1" 2>/dev/null || return 1     # 必须是我们的页面
  if [ ! -f index.html ] || [ "$1" -nt index.html ]; then
    cp "$1" index.html && echo "已同步页面来源: $1" && return 0
  fi
  return 1
}

SESSIONS="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"
NEWEST=$(find "$SESSIONS" -name 'site.html' -type f -mmin -720 2>/dev/null \
         | xargs -I{} stat -f '%m %N' {} 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)

[ -n "$NEWEST" ] && take "$NEWEST"
take "$ARTIFACT"

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
