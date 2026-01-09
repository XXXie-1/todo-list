import os
import requests
import datetime
import re

# 接收 GitHub Secrets
GITHUB_REPO = os.getenv('GITHUB_REPOSITORY')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
APP_ID = os.getenv('WECHAT_APPID')
APP_SECRET = os.getenv('WECHAT_SECRET')
USER_ID = os.getenv('WECHAT_USER_ID')
TEMPLATE_ID = os.getenv('WECHAT_TEMPLATE_ID')

def get_access_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}"
    try:
        resp = requests.get(url).json()
        if 'access_token' in resp:
            return resp['access_token']
        print(f"获取 Token 失败: {resp}")
    except Exception as e:
        print(f"网络错误: {e}")
    return None

def send_template_msg(token, title, time_str, body, url):
    if not token: return
    push_url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}"
    data = {
        "touser": USER_ID,
        "template_id": TEMPLATE_ID,
        "url": url,
        "data": {
            "thing01": {"value": title[:20], "color": "#173177"}, # 限制长度防止报错
            "time01": {"value": time_str, "color": "#CC3300"},
            "thing02": {"value": body[:20] if body else "无备注", "color": "#666666"}
        }
    }
    requests.post(push_url, json=data)

def get_issues():
    if not GITHUB_TOKEN: return []
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues?state=open"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    return requests.get(url, headers=headers).json()

def check_reminders():
    wx_token = get_access_token()
    issues = get_issues()
    # 修正到北京时间 (UTC+8)
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    print(f"当前检测时间: {now}")

    pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})\]')

    for issue in issues:
        title = issue['title']
        match = pattern.search(title)
        if match:
            time_str = match.group(1)
            try:
                target_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                labels = [l['name'] for l in issue.get('labels', [])]
                
                # 定义提醒规则：正点、提前1天、提前1小时
                checks = [
                    (datetime.timedelta(minutes=0),  None,      "⏰ 到点啦"),
                    (datetime.timedelta(days=1),     "提前1天",  "🗓 明天提醒"),
                    (datetime.timedelta(hours=1),    "提前1小时", "⏳ 还有1小时"),
                ]

                for offset, required_label, prefix in checks:
                    if required_label is None or required_label in labels:
                        trigger_time = target_time - offset
                        diff = (now - trigger_time).total_seconds()
                        
                        # 20分钟的时间窗口
                        if 0 <= diff < 1200:
                            clean_title = title.replace(match.group(0), "").strip()
                            print(f"触发推送: {clean_title}")
                            send_template_msg(wx_token, f"{prefix}: {clean_title}", time_str, issue.get('body'), issue['html_url'])
            except ValueError:
                pass

if __name__ == "__main__":
    check_reminders()
