"""
PUBGM 트래픽 영향 뉴스를 슬랙으로 발송하는 스크립트
매일 아침 9시 자동 발송용
"""
import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

NEWS_CSV = 'data/news.csv'

# 카테고리 그룹 정보
CATEGORY_INFO = {
    'outage_block': {'icon': '🔴', 'name': '장애/차단', 'color': '#ff4757'},
    'social_crisis': {'icon': '🟠', 'name': '사회 위기', 'color': '#ffa502'},
    'seasonal_calendar': {'icon': '🟢', 'name': '시즌/일정', 'color': '#2ed573'},
    'gaming_competitor': {'icon': '🔵', 'name': '게임/경쟁', 'color': '#5352ed'},
    'other': {'icon': '⚪', 'name': '기타', 'color': '#95a5a6'}
}


def get_recent_news(hours=24):
    """최근 N시간 내 뉴스 가져오기"""
    if not os.path.exists(NEWS_CSV):
        return [], []
    
    df = pd.read_csv(NEWS_CSV, encoding='utf-8-sig')
    
    # 날짜 필터링
    cutoff_date = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d')
    df = df[df['date'] >= cutoff_date]
    
    # 타입별 분리
    traffic_news = df[df['news_type'] == 'traffic_impact'].to_dict('records')
    gaming_news = df[df['news_type'] == 'gaming'].to_dict('records')
    
    return traffic_news, gaming_news


def create_slack_message(traffic_news, gaming_news):
    """슬랙 메시지 포맷 생성"""
    
    today = datetime.now().strftime('%Y년 %m월 %d일')
    
    # 카테고리별 집계
    category_counts = {}
    for news in traffic_news:
        cat = news.get('category_group', 'other')
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # 메시지 헤더
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📊 PUBGM 트래픽 리포트 - {today}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*지난 24시간 뉴스 현황*\n⚡ 트래픽 영향: *{len(traffic_news)}건* | 🎮 게임 뉴스: *{len(gaming_news)}건*"
            }
        },
        {"type": "divider"}
    ]
    
    # 트래픽 영향 뉴스가 있을 때
    if traffic_news:
        # 카테고리별 현황
        cat_text = ""
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            info = CATEGORY_INFO.get(cat, CATEGORY_INFO['other'])
            cat_text += f"{info['icon']} {info['name']}: *{count}건*\n"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🚨 트래픽 영향 이슈*\n{cat_text}"
            }
        })
        
        # 위기/장애 체크
        crisis_count = category_counts.get('outage_block', 0) + category_counts.get('social_crisis', 0)
        if crisis_count > 0:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *주의:* {crisis_count}건의 위기/장애 관련 뉴스가 감지되었습니다."
                }
            })
        
        # 주요 뉴스 3개
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*📌 주요 뉴스*"
            }
        })
        
        for news in traffic_news[:3]:
            cat = news.get('category_group', 'other')
            info = CATEGORY_INFO.get(cat, CATEGORY_INFO['other'])
            title = news.get('title', '')[:60]
            country = news.get('country', '')
            
            news_text = f"{info['icon']} {title}"
            if country and country != 'Unknown':
                news_text += f" ({country})"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": news_text
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "보기",
                        "emoji": True
                    },
                    "url": news.get('url', '#'),
                    "action_id": f"view_news_{traffic_news.index(news)}"
                }
            })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "✅ 지난 24시간 동안 특이한 트래픽 영향 이슈가 없습니다."
            }
        })
    
    # 대시보드 링크
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "📊 대시보드 바로가기",
                    "emoji": True
                },
                "url": "https://sangwonji.github.io/TEST3/",
                "style": "primary"
            }
        ]
    })
    
    return {"blocks": blocks}


def send_to_slack(message):
    """슬랙으로 메시지 발송"""
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    
    if not webhook_url:
        print("Error: SLACK_WEBHOOK_URL not set in .env")
        print("\n[Preview] Message saved to slack_preview.json")
        # 파일로 저장 (인코딩 문제 방지)
        with open('slack_preview.json', 'w', encoding='utf-8') as f:
            json.dump(message, f, ensure_ascii=False, indent=2)
        return False
    
    try:
        response = requests.post(
            webhook_url,
            json=message,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print("Slack message sent successfully!")
            return True
        else:
            print(f"Slack API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error sending to Slack: {e}")
        return False


def main():
    print("="*50)
    print("PUBGM Traffic Report - Slack Sender")
    print("="*50)
    
    # 최근 24시간 뉴스 가져오기
    traffic_news, gaming_news = get_recent_news(hours=24)
    
    print(f"\nTraffic Impact News: {len(traffic_news)}")
    print(f"Gaming News: {len(gaming_news)}")
    
    # 슬랙 메시지 생성
    message = create_slack_message(traffic_news, gaming_news)
    
    # 발송
    send_to_slack(message)


if __name__ == "__main__":
    main()

