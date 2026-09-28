#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日收盘快报邮件发送器。

**这个脚本由你的自动化（GitHub Actions / VPS / 本机 launchd）执行，发件人是你自己的邮箱。
Claude 不接触、不保存、也不读取你的邮箱密码——密码只存在你自己设的 Secret 里。**

需要的环境变量
--------------
  MAIL_USER          发件邮箱，如 tonyhu0601@gmail.com
  MAIL_APP_PASSWORD  Gmail「应用专用密码」（16位，不是你的登录密码）
  MAIL_TO            收件人，多个用英文逗号分隔
  MAIL_CC            抄送（可选）
  PAGES_URL          网页版地址（可选），如 https://用户名.github.io/仓库名/
  REPORT_DATE        基准交易日 YYYY-MM-DD（可选，默认从 index.html 里读）

用法
----
  python3 send_report_mail.py                 # 发送，附件取同目录 latest.xlsx
  python3 send_report_mail.py --dry-run       # 只打印，不发送（先这样测一遍）
  python3 send_report_mail.py --xlsx 路径     # 指定附件

怎么拿 Gmail 应用专用密码
------------------------
  1. 账号必须已开启两步验证：myaccount.google.com → 安全性 → 两步验证
  2. myaccount.google.com/apppasswords → 生成 → 复制那 16 位字符串
  3. 粘贴到 GitHub 仓库 Settings → Secrets and variables → Actions → New repository secret
     名字填 MAIL_APP_PASSWORD。**不要贴到聊天里，也不要写进任何代码文件。**

GitHub Actions 里的对应步骤
--------------------------
    - name: 发送快报邮件
      if: success()
      env:
        MAIL_USER: ${{ secrets.MAIL_USER }}
        MAIL_APP_PASSWORD: ${{ secrets.MAIL_APP_PASSWORD }}
        MAIL_TO: ${{ secrets.MAIL_TO }}
        PAGES_URL: https://你的用户名.github.io/仓库名/
      run: python3 send_report_mail.py
"""
import os
import re
import sys
import smtplib
import mimetypes
from email.message import EmailMessage
from email.utils import formataddr, formatdate

HERE = os.path.dirname(os.path.abspath(__file__))


def read_date(default=''):
    if os.environ.get('REPORT_DATE'):
        return os.environ['REPORT_DATE']
    p = os.path.join(HERE, 'index.html')
    try:
        s = open(p, encoding='utf-8').read(300000)
        m = re.search(r'"date":\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})"', s)
        if m:
            return m.group(1)
    except Exception:
        pass
    return default


def build(date, pages_url, xlsx, to_list, cc_list, sender):
    msg = EmailMessage()
    msg['Subject'] = f'A股收盘快报 {date}' if date else 'A股收盘快报'
    msg['From'] = formataddr(('A股每日选股', sender))
    msg['To'] = ', '.join(to_list)
    if cc_list:
        msg['Cc'] = ', '.join(cc_list)
    msg['Date'] = formatdate(localtime=True)

    link_txt = f'\n网页版（可排序、可搜索）：{pages_url}\n' if pages_url else ''
    body = f"""{date} A股收盘快报已生成。

包含四张表：筛选结果、被10亿门槛剔除、全市场涨停股、筛选说明。
均线三条件（收盘价同时高于 MA5 / MA10 / 5周线）、新高与换手标注、
开盘0930主买主卖、主力资金流向、前十大流通股东（外资/社保/国资）标注。
{link_txt}
本邮件由自动化流程在收盘后生成发送。
本表仅为按既定规则对公开行情数据的筛选结果，不构成投资建议。
"""
    msg.set_content(body)

    link_html = (f'<p><a href="{pages_url}" style="color:#1F3864">'
                 f'打开网页版（可排序、可搜索）</a></p>') if pages_url else ''
    msg.add_alternative(f"""<html><body style="font:14px/1.6 -apple-system,'PingFang SC',Arial,sans-serif;color:#15181d">
<h2 style="color:#1F3864;font-size:18px;margin:0 0 10px">A股收盘快报 · {date}</h2>
{link_html}
<p>包含四张表：<b>筛选结果</b>、被10亿门槛剔除、<b>全市场涨停股</b>、筛选说明。</p>
<ul style="padding-left:20px;color:#3c4653">
  <li>均线三条件：收盘价同时高于 MA5 / MA10 / 5周线</li>
  <li>历史 / 年内 / 60日新高，5周内单日换手&gt;30%，分时单分钟成交额&gt;1亿</li>
  <li>开盘 0930 分钟主买 / 主卖及盘中反向超越</li>
  <li>主力资金当日 / 5日 / 10日净额</li>
  <li>前十大流通股东中的外资、社保养老金、国家产业基金标注</li>
</ul>
<p style="color:#6b7482;font-size:12px;border-top:1px solid #e3e6ea;padding-top:10px">
本邮件由自动化流程在收盘后生成发送。数据来源：东方财富 / 同花顺 / 腾讯财经。<br>
本表仅为按既定规则对公开行情数据的筛选结果，<b>不构成投资建议</b>。</p>
</body></html>""", subtype='html')

    if xlsx and os.path.exists(xlsx):
        ctype, _ = mimetypes.guess_type(xlsx)
        maintype, _, subtype = (ctype or 'application/octet-stream').partition('/')
        name = f'A股选股_{date.replace("-", "")}_收盘快报.xlsx' if date else os.path.basename(xlsx)
        with open(xlsx, 'rb') as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=name)
        print(f'附件: {name} ({os.path.getsize(xlsx)} bytes)')
    else:
        print('（无 xlsx 附件，只发正文和链接）')

    return msg


def main():
    args = sys.argv[1:]
    dry = '--dry-run' in args
    xlsx = os.path.join(HERE, 'latest.xlsx')
    if '--xlsx' in args:
        xlsx = args[args.index('--xlsx') + 1]

    sender = os.environ.get('MAIL_USER', '').strip()
    pw = os.environ.get('MAIL_APP_PASSWORD', '')
    to_list = [x.strip() for x in os.environ.get('MAIL_TO', '').split(',') if x.strip()]
    cc_list = [x.strip() for x in os.environ.get('MAIL_CC', '').split(',') if x.strip()]
    pages_url = os.environ.get('PAGES_URL', '').strip()
    date = read_date()

    missing = [k for k, v in (('MAIL_USER', sender), ('MAIL_TO', to_list)) if not v]
    if not dry and not pw:
        missing.append('MAIL_APP_PASSWORD')
    if missing:
        print('缺少环境变量: ' + ', '.join(missing), file=sys.stderr)
        sys.exit(1)

    msg = build(date, pages_url, xlsx, to_list, cc_list, sender or 'me@example.com')

    if dry:
        print('--- DRY RUN，未发送 ---')
        print(f'Subject: {msg["Subject"]}')
        print(f'From:    {msg["From"]}')
        print(f'To:      {msg["To"]}')
        print(f'Cc:      {msg["Cc"] or "-"}')
        print('--- 正文 ---')
        print(msg.get_body(preferencelist=('plain',)).get_content())
        return

    host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.environ.get('SMTP_PORT', '465'))
    try:
        with smtplib.SMTP_SSL(host, port, timeout=45) as s:
            s.login(sender, pw)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        print('SMTP 认证失败。Gmail 必须用「应用专用密码」而不是登录密码，'
              '且账号需已开启两步验证。', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'发送失败: {type(e).__name__}: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'已发送 -> {", ".join(to_list)}' + (f' (cc {", ".join(cc_list)})' if cc_list else ''))


if __name__ == '__main__':
    main()
