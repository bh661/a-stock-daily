# A股每日条件选股 · 网页版

每个交易日北京时间 16:00 收盘后，由 Claude 的定时任务自动生成并推送。

- **网页**：https://bh661.github.io/a-stock-daily/
- **内容**：筛选结果 / 被10亿门槛剔除 / 全市场涨停股 / 筛选说明，共四张表
- **数据来源**：东方财富、同花顺、腾讯财经的公开行情接口

## 目录里有什么

| 文件 | 作用 |
|---|---|
| `index.html` | 网页本体，单文件自包含（数据、样式、脚本全内嵌），断网也能看 |
| `latest.xlsx` | 最新一个交易日的 xlsx 报表（只保留最新一份，每天覆盖） |
| `build_site.py` | 把 xlsx 转成 `index.html` 的生成器，Claude 每天调用它 |
| `push.sh` | 同步 + 提交 + 推送脚本，由 launchd 自动触发 |
| `setup.sh` | 一次性安装脚本 |
| `com.astock.site-push.plist` | launchd 定时任务模板 |

## 自动化链路

```
Claude 定时任务（每个交易日 16:00 北京时间）
   └─ 取数 → 生成 xlsx → build_site.py 转成 html
        └─ 更新 Claude artifact（路径固定：~/Documents/Claude/Artifacts/a-stock-daily-screen-site/）
             └─ launchd 监测到该文件变化
                  └─ push.sh 复制进本仓库 → commit → push
                       └─ GitHub Pages 自动重新发布（1-2 分钟）
```

休市日或数据源不可用时，Claude 不会更新页面，仓库也就没有新提交，页面停留在上一个交易日。

## 一次性安装

1. 在 GitHub 上建一个**空的公开仓库**（不要勾 README / .gitignore / license）
2. 终端里执行：`bash ~/Documents/astock-site/setup.sh https://github.com/你的用户名/仓库名.git`
3. 按脚本最后的提示，去仓库 Settings → Pages 把 Source 设为 `Deploy from a branch` → `main` / `(root)`

推送日志：`tail -f ~/Library/Logs/astock-site-push.log`

停用自动推送：`launchctl unload ~/Library/LaunchAgents/com.astock.site-push.plist`

---

本页与本仓库内容仅为按既定规则的公开行情数据筛选结果，**不构成投资建议**。
