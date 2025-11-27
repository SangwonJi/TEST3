#!/usr/bin/env python3
"""
뉴스 수집 스크립트
Google News RSS를 사용하여 PUBG Mobile 관련 뉴스를 수집하고 CSV로 저장합니다.
"""

import os
import sys
import json
import csv
import feedparser
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import time
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
SCRIPTS_DIR = PROJECT_ROOT / 'scripts'
KEYWORDS_FILE = SCRIPTS_DIR / 'keywords.json'
NEWS_CSV = DATA_DIR / 'news.csv'

# 환경 변수 로드 (로컬 개발 환경)
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
    logger.info("로컬 환경: .env 파일에서 환경 변수 로드")
except ImportError:
    logger.info("GitHub Actions 환경: os.getenv 사용")


def load_keywords() -> Dict:
    """키워드 설정 파일 로드"""
    try:
        with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"키워드 파일을 찾을 수 없습니다: {KEYWORDS_FILE}")
        return {
            "base_keywords": ["PUBG Mobile"],
            "country_keywords": {},
            "categories": ["gaming"]
        }
    except json.JSONDecodeError:
        logger.error("키워드 파일 JSON 파싱 오류")
        return {"base_keywords": ["PUBG Mobile"], "country_keywords": {}, "categories": ["gaming"]}


def get_continent(country: str) -> str:
    """국가명으로 대륙 반환"""
    continent_map = {
        'USA': 'NORTH AMERICA', 'Canada': 'NORTH AMERICA', 'Mexico': 'NORTH AMERICA',
        'Brazil': 'SOUTH AMERICA', 'Argentina': 'SOUTH AMERICA',
        'Germany': 'EUROPE', 'UK': 'EUROPE', 'France': 'EUROPE', 'Italy': 'EUROPE', 'Spain': 'EUROPE',
        'China': 'ASIA', 'India': 'ASIA', 'Japan': 'ASIA', 'Korea': 'ASIA', 'South Korea': 'ASIA',
        'South Africa': 'AFRICA', 'Egypt': 'AFRICA', 'Nigeria': 'AFRICA',
        'Australia': 'OCEANIA', 'New Zealand': 'OCEANIA',
        'Russia': 'RUSSIA & CIS'
    }
    return continent_map.get(country, 'OTHER')


def fetch_news_from_openai(keyword: str, countries: List[Dict] = None) -> List[Dict]:
    """
    OpenAI API를 사용하여 뉴스 검색 및 분석
    
    Args:
        keyword: 검색 키워드
        countries: 관련 국가 리스트 (선택사항)
    
    Returns:
        뉴스 리스트
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY가 설정되지 않았습니다.")
        return []
    
    try:
        import requests
        
        # 국가 정보 포함
        country_context = ""
        if countries:
            country_names = [c.get('country', '') for c in countries if c.get('country')]
            if country_names:
                country_context = f" 특히 {', '.join(country_names[:5])} 국가와 관련된"
        
        prompt = f"""다음 키워드와 관련된 최신 뉴스를 검색하고 분석해주세요: {keyword}{country_context}

다음 JSON 형식으로 응답해주세요 (최대 10개):
[
  {{
    "title": "뉴스 제목",
    "summary": "요약 (2-3문장)",
    "url": "뉴스 링크 (가능한 경우)",
    "source": "출처",
    "date": "YYYY-MM-DD 형식",
    "country": "관련 국가 (없으면 null)",
    "reason": "트래픽 변화와의 연관성 분석"
  }}
]

최근 7일 이내의 뉴스만 포함하고, PUBG Mobile이나 모바일 게임과 관련된 뉴스만 알려주세요."""

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",  # 또는 "gpt-4", "gpt-3.5-turbo"
                "messages": [
                    {"role": "system", "content": "You are a news analyst. Return only valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"OpenAI API 오류: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        
        # JSON 추출
        import re
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            news_data = json.loads(json_match.group())
            
            # 형식 변환
            news_list = []
            for item in news_data:
                news_list.append({
                    'date': item.get('date', datetime.now().strftime('%Y-%m-%d')),
                    'country': item.get('country'),
                    'continent': get_continent(item.get('country', '')) if item.get('country') else None,
                    'title': item.get('title', ''),
                    'summary': item.get('summary', '')[:500],
                    'url': item.get('url', '#'),
                    'source': item.get('source', 'OpenAI'),
                    'category': 'gaming'
                })
            
            logger.info(f"OpenAI API로 '{keyword}'에서 {len(news_list)}개 뉴스 수집 완료")
            return news_list
        else:
            logger.warning("OpenAI 응답에서 JSON을 찾을 수 없습니다.")
            return []
            
    except Exception as e:
        logger.error(f"OpenAI API 호출 실패: {e}")
        return []


def fetch_news_from_claude(keyword: str, countries: List[Dict] = None) -> List[Dict]:
    """
    Claude API를 사용하여 뉴스 검색 및 분석
    
    Args:
        keyword: 검색 키워드
        countries: 관련 국가 리스트 (선택사항)
    
    Returns:
        뉴스 리스트
    """
    # CLAUDE_API_KEY 또는 ANTHROPIC_API_KEY 지원 (둘 다 동일)
    api_key = os.getenv('CLAUDE_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning("CLAUDE_API_KEY 또는 ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return []
    
    try:
        import requests
        
        # 국가 정보 포함
        country_context = ""
        if countries:
            country_names = [c.get('country', '') for c in countries if c.get('country')]
            if country_names:
                country_context = f" 특히 {', '.join(country_names[:5])} 국가와 관련된"
        
        prompt = f"""다음 키워드와 관련된 최신 뉴스를 검색하고 분석해주세요: {keyword}{country_context}

다음 JSON 형식으로 응답해주세요 (최대 10개):
[
  {{
    "title": "뉴스 제목",
    "summary": "요약 (2-3문장)",
    "url": "뉴스 링크 (가능한 경우)",
    "source": "출처",
    "date": "YYYY-MM-DD 형식",
    "country": "관련 국가 (없으면 null)",
    "reason": "트래픽 변화와의 연관성 분석"
  }}
]

최근 7일 이내의 뉴스만 포함하고, PUBG Mobile이나 모바일 게임과 관련된 뉴스만 알려주세요."""

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": "claude-3-5-sonnet-20241022",  # 또는 "claude-3-opus-20240229"
                "max_tokens": 2000,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Claude API 오류: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        content = data['content'][0]['text']
        
        # JSON 추출
        import re
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            news_data = json.loads(json_match.group())
            
            # 형식 변환
            news_list = []
            for item in news_data:
                news_list.append({
                    'date': item.get('date', datetime.now().strftime('%Y-%m-%d')),
                    'country': item.get('country'),
                    'continent': get_continent(item.get('country', '')) if item.get('country') else None,
                    'title': item.get('title', ''),
                    'summary': item.get('summary', '')[:500],
                    'url': item.get('url', '#'),
                    'source': item.get('source', 'Claude'),
                    'category': 'gaming'
                })
            
            logger.info(f"Claude API로 '{keyword}'에서 {len(news_list)}개 뉴스 수집 완료")
            return news_list
        else:
            logger.warning("Claude 응답에서 JSON을 찾을 수 없습니다.")
            return []
            
    except Exception as e:
        logger.error(f"Claude API 호출 실패: {e}")
        return []


def fetch_news_from_api(keyword: str, api_type: str = 'rss', countries: List[Dict] = None) -> List[Dict]:
    """
    API를 사용하여 뉴스 가져오기 (확장 가능)
    
    Args:
        keyword: 검색 키워드
        api_type: API 타입 ('rss', 'openai', 'claude', 'gemini' 등)
        countries: 관련 국가 리스트 (선택사항)
    
    Returns:
        뉴스 리스트
    """
    # RSS는 기본으로 사용
    if api_type == 'rss':
        return fetch_news_from_rss(keyword)
    
    # OpenAI API 사용
    elif api_type == 'openai':
        news = fetch_news_from_openai(keyword, countries)
        if news:
            return news
        else:
            logger.info("OpenAI API 실패, RSS로 폴백")
            return fetch_news_from_rss(keyword)
    
    # Claude API 사용
    elif api_type == 'claude':
        news = fetch_news_from_claude(keyword, countries)
        if news:
            return news
        else:
            logger.info("Claude API 실패, RSS로 폴백")
            return fetch_news_from_rss(keyword)
    
    # Gemini API 사용 (API 키 필요)
    elif api_type == 'gemini':
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY가 설정되지 않았습니다. RSS를 사용합니다.")
            return fetch_news_from_rss(keyword)
        
        try:
            # Gemini API 호출 로직 (추후 구현)
            logger.info(f"Gemini API 사용 (키워드: {keyword})")
            return []  # TODO: Gemini API 구현
        except Exception as e:
            logger.error(f"Gemini API 호출 실패: {e}")
            return fetch_news_from_rss(keyword)  # 폴백
    
    else:
        logger.warning(f"알 수 없는 API 타입: {api_type}. RSS를 사용합니다.")
        return fetch_news_from_rss(keyword)


def fetch_news_from_rss(keyword: str, max_retries: int = 3) -> List[Dict]:
    """
    Google News RSS에서 뉴스 가져오기
    
    Args:
        keyword: 검색 키워드
        max_retries: 최대 재시도 횟수
    
    Returns:
        뉴스 리스트
    """
    news_list = []
    # URL 인코딩으로 특수문자 처리
    import urllib.parse
    encoded_keyword = urllib.parse.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    for attempt in range(max_retries):
        try:
            # 로그에는 키워드만 표시 (URL 전체는 표시하지 않음)
            logger.info(f"RSS 피드 가져오기 시도 {attempt + 1}/{max_retries}: 키워드='{keyword}'")
            feed = feedparser.parse(rss_url)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS 파싱 경고: {feed.bozo_exception}")
            
            for entry in feed.entries[:10]:  # 최대 10개
                # 날짜 파싱
                try:
                    pub_date = datetime(*entry.published_parsed[:6])
                except (AttributeError, TypeError):
                    pub_date = datetime.now()
                
                # 오늘부터 7일 이내 뉴스만
                if pub_date < datetime.now() - timedelta(days=7):
                    continue
                
                news_item = {
                    'date': pub_date.strftime('%Y-%m-%d'),
                    'country': None,  # 키워드에서 추출
                    'continent': None,
                    'title': entry.get('title', '').strip(),
                    'summary': entry.get('summary', '').strip()[:500],  # 최대 500자
                    'url': entry.get('link', ''),
                    'source': entry.get('source', {}).get('title', 'Google News'),
                    'category': 'gaming'
                }
                
                # 국가명 추출 (키워드에서)
                for country in load_keywords().get('country_keywords', {}).keys():
                    if country.lower() in keyword.lower():
                        news_item['country'] = country
                        news_item['continent'] = get_continent(country)
                        break
                
                news_list.append(news_item)
            
            logger.info(f"'{keyword}'에서 {len(news_list)}개 뉴스 수집 완료")
            break  # 성공하면 중단
            
        except Exception as e:
            logger.error(f"RSS 가져오기 실패 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)  # 5초 대기 후 재시도
            else:
                logger.error(f"'{keyword}' 키워드로 뉴스 수집 실패")
    
    return news_list


def refine_news_with_ai(news_item: Dict, api_type: str = 'openai') -> Optional[Dict]:
    """
    RSS로 수집한 뉴스를 AI로 정제 (카테고리 분류, 트래픽 영향 분석)
    
    Args:
        news_item: RSS로 수집한 뉴스 아이템
        api_type: 사용할 API ('openai' 또는 'claude')
    
    Returns:
        정제된 뉴스 딕셔너리 또는 None (관련 없음)
    """
    api_key = None
    api_url = None
    headers = {}
    payload = {}
    
    if api_type == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return news_item  # API 키 없으면 원본 반환
        
        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""다음 뉴스를 분석하여 모바일 게임 트래픽에 영향을 줄 수 있는지 판단해주세요:

제목: {news_item.get('title', '')}
내용: {news_item.get('summary', '')}
URL: {news_item.get('url', '')}

다음 JSON 형식으로 응답해주세요:
{{
  "relevant": true 또는 false (모바일 게임 트래픽에 영향을 줄 수 있으면 true),
  "category": "gaming, holiday, school_calendar, war_conflict, natural_disaster, internet_shutdown, power_outage, curfew, economic, other 중 하나",
  "country": "관련 국가명 (없으면 null)",
  "traffic_impact": "트래픽에 미치는 영향 설명 (간단히)",
  "summary_kr": "한국어로 2-3줄 요약"
}}

카테고리 설명:
- gaming: 게임 관련 뉴스
- holiday: 공휴일, 명절, 축제
- school_calendar: 방학, 시험기간 등 학사일정
- war_conflict: 전쟁, 분쟁, 군사 작전
- terrorism_explosion: 테러, 폭발, 폭탄 공격
- protest_strike: 시위, 파업, 폭동
- natural_disaster: 지진, 홍수, 태풍, 산불 등 천재지변
- internet_shutdown: 인터넷 차단, 통신 장애
- power_outage: 정전, 전력 공급 중단
- curfew: 통금, 봉쇄, 비상사태
- economic: 경제 위기, 인플레이션, 통화 평가절하
- tech_outage: 소셜미디어/앱스토어/클라우드 장애
- cyber_attack: 사이버 공격, DDoS, 해킹
- censorship: 검열, 앱/게임 금지
- sports_event: 월드컵, 올림픽 등 스포츠 이벤트
- election: 선거, 투표, 정치 이벤트
- pandemic: 팬데믹, 전염병, 격리
- infrastructure_damage: 인프라 손상, 교량/건물 붕괴
- competitor_game: 경쟁 게임 출시/업데이트
- social_trend: 바이럴 트렌드, 인플루언서, e스포츠 토너먼트
- major_event: 주요 문화 행사, 게임 컨벤션
- other: 기타

관련이 없으면 relevant: false로 설정하세요."""

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a news analyst. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
    
    elif api_type == 'claude':
        api_key = os.getenv('CLAUDE_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return news_item  # API 키 없으면 원본 반환
        
        api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        prompt = f"""다음 뉴스를 분석하여 모바일 게임 트래픽에 영향을 줄 수 있는지 판단해주세요:

제목: {news_item.get('title', '')}
내용: {news_item.get('summary', '')}
URL: {news_item.get('url', '')}

다음 JSON 형식으로 응답해주세요:
{{
  "relevant": true 또는 false (모바일 게임 트래픽에 영향을 줄 수 있으면 true),
  "category": "gaming, holiday, school_calendar, war_conflict, natural_disaster, internet_shutdown, power_outage, curfew, economic, other 중 하나",
  "country": "관련 국가명 (없으면 null)",
  "traffic_impact": "트래픽에 미치는 영향 설명 (간단히)",
  "summary_kr": "한국어로 2-3줄 요약"
}}

카테고리 설명:
- gaming: 게임 관련 뉴스
- holiday: 공휴일, 명절, 축제
- school_calendar: 방학, 시험기간 등 학사일정
- war_conflict: 전쟁, 분쟁, 군사 작전
- terrorism_explosion: 테러, 폭발, 폭탄 공격
- protest_strike: 시위, 파업, 폭동
- natural_disaster: 지진, 홍수, 태풍, 산불 등 천재지변
- internet_shutdown: 인터넷 차단, 통신 장애
- power_outage: 정전, 전력 공급 중단
- curfew: 통금, 봉쇄, 비상사태
- economic: 경제 위기, 인플레이션, 통화 평가절하
- tech_outage: 소셜미디어/앱스토어/클라우드 장애
- cyber_attack: 사이버 공격, DDoS, 해킹
- censorship: 검열, 앱/게임 금지
- sports_event: 월드컵, 올림픽 등 스포츠 이벤트
- election: 선거, 투표, 정치 이벤트
- pandemic: 팬데믹, 전염병, 격리
- infrastructure_damage: 인프라 손상, 교량/건물 붕괴
- competitor_game: 경쟁 게임 출시/업데이트
- social_trend: 바이럴 트렌드, 인플루언서, e스포츠 토너먼트
- major_event: 주요 문화 행사, 게임 컨벤션
- other: 기타

관련이 없으면 relevant: false로 설정하세요."""

        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 500,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
    
    else:
        return news_item  # 알 수 없는 API 타입이면 원본 반환
    
    try:
        import requests
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.warning(f"AI API 오류: {response.status_code}, 원본 뉴스 사용")
            return news_item
        
        data = response.json()
        
        # 응답에서 텍스트 추출
        if api_type == 'openai':
            content = data['choices'][0]['message']['content']
        else:  # claude
            content = data['content'][0]['text']
        
        # JSON 추출
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            ai_result = json.loads(json_match.group())
            
            # 관련 없으면 None 반환
            if not ai_result.get('relevant', False):
                return None
            
            # 정제된 정보 병합
            refined_item = {
                **news_item,
                'category': ai_result.get('category', 'other'),
                'summary': ai_result.get('summary_kr', news_item.get('summary', '')),
                'traffic_impact': ai_result.get('traffic_impact', '')
            }
            
            # 국가 정보 업데이트
            if ai_result.get('country'):
                refined_item['country'] = ai_result.get('country')
                refined_item['continent'] = get_continent(ai_result.get('country'))
            
            return refined_item
        else:
            logger.warning("AI 응답에서 JSON을 찾을 수 없습니다. 원본 사용")
            return news_item
            
    except Exception as e:
        logger.error(f"AI 정제 실패: {e}, 원본 뉴스 사용")
        return news_item


def cross_validate_news(openai_news: List[Dict], claude_news: List[Dict]) -> List[Dict]:
    """
    OpenAI와 Claude API 결과를 교차검증하여 신뢰도 높은 뉴스 반환
    
    Args:
        openai_news: OpenAI API로 수집한 뉴스
        claude_news: Claude API로 수집한 뉴스
    
    Returns:
        교차검증된 뉴스 리스트 (신뢰도 점수 포함)
    """
    validated_news = []
    seen_titles = set()
    
    # 제목 유사도 비교 함수 (간단한 버전)
    def title_similarity(title1: str, title2: str) -> float:
        """두 제목의 유사도 계산 (0.0 ~ 1.0)"""
        title1_lower = title1.lower()
        title2_lower = title2.lower()
        
        # 완전 일치
        if title1_lower == title2_lower:
            return 1.0
        
        # 단어 기반 유사도
        words1 = set(title1_lower.split())
        words2 = set(title2_lower.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    # OpenAI 뉴스 처리
    for news in openai_news:
        title = news.get('title', '').lower()
        if title in seen_titles:
            continue
        
        # Claude 결과와 비교
        matched = False
        best_match_score = 0.0
        best_match = None
        
        for claude_item in claude_news:
            claude_title = claude_item.get('title', '').lower()
            similarity = title_similarity(title, claude_title)
            
            if similarity > 0.7:  # 70% 이상 유사하면 일치로 간주
                matched = True
                if similarity > best_match_score:
                    best_match_score = similarity
                    best_match = claude_item
        
        if matched and best_match:
            # 두 API가 일치하는 뉴스: 신뢰도 높음
            validated_item = news.copy()
            validated_item['confidence'] = 'high'
            validated_item['validation'] = f"OpenAI + Claude 일치 (유사도: {best_match_score:.0%})"
            validated_item['openai_summary'] = news.get('summary', '')
            validated_item['claude_summary'] = best_match.get('summary', '')
            # 더 긴 요약 사용
            if len(best_match.get('summary', '')) > len(news.get('summary', '')):
                validated_item['summary'] = best_match.get('summary', '')
            validated_news.append(validated_item)
            seen_titles.add(title)
            seen_titles.add(best_match.get('title', '').lower())
        else:
            # OpenAI만 찾은 뉴스: 신뢰도 중간
            validated_item = news.copy()
            validated_item['confidence'] = 'medium'
            validated_item['validation'] = 'OpenAI only'
            validated_news.append(validated_item)
            seen_titles.add(title)
    
    # Claude만 찾은 뉴스 추가
    for news in claude_news:
        title = news.get('title', '').lower()
        if title not in seen_titles:
            validated_item = news.copy()
            validated_item['confidence'] = 'medium'
            validated_item['validation'] = 'Claude only'
            validated_news.append(validated_item)
            seen_titles.add(title)
    
    # 신뢰도 순으로 정렬 (high > medium)
    validated_news.sort(key=lambda x: (x.get('confidence') == 'high', x.get('title', '')))
    
    logger.info(f"교차검증 완료: 총 {len(validated_news)}개 (High: {sum(1 for n in validated_news if n.get('confidence') == 'high')}, Medium: {sum(1 for n in validated_news if n.get('confidence') == 'medium')})")
    
    return validated_news


def fetch_news_with_cross_validation(keyword: str, countries: List[Dict] = None) -> List[Dict]:
    """
    OpenAI와 Claude API를 모두 사용하여 교차검증
    
    Args:
        keyword: 검색 키워드
        countries: 관련 국가 리스트
    
    Returns:
        교차검증된 뉴스 리스트
    """
    logger.info(f"교차검증 시작: {keyword}")
    
    # 두 API 모두 호출
    openai_news = fetch_news_from_openai(keyword, countries)
    time.sleep(1)  # API 부하 방지
    claude_news = fetch_news_from_claude(keyword, countries)
    
    # 교차검증
    if openai_news or claude_news:
        validated = cross_validate_news(openai_news, claude_news)
        return validated
    else:
        # 둘 다 실패 시 RSS 폴백
        logger.warning("OpenAI와 Claude 모두 실패, RSS로 폴백")
        return fetch_news_from_rss(keyword)


def remove_duplicates(existing_news: List[Dict], new_news: List[Dict]) -> List[Dict]:
    """
    중복 뉴스 제거 (URL 기준)
    
    Args:
        existing_news: 기존 뉴스 리스트
        new_news: 새로 수집한 뉴스 리스트
    
    Returns:
        중복 제거된 새 뉴스 리스트
    """
    existing_urls = {news['url'] for news in existing_news if news.get('url')}
    unique_news = [news for news in new_news if news.get('url') not in existing_urls]
    
    logger.info(f"중복 제거: {len(new_news)}개 중 {len(unique_news)}개 유니크")
    return unique_news


def load_existing_news() -> List[Dict]:
    """기존 CSV 파일에서 뉴스 로드"""
    if not NEWS_CSV.exists():
        logger.info("기존 뉴스 파일이 없습니다. 새로 생성합니다.")
        return []
    
    try:
        df = pd.read_csv(NEWS_CSV, encoding='utf-8-sig')
        return df.to_dict('records')
    except Exception as e:
        logger.error(f"기존 뉴스 파일 읽기 실패: {e}")
        return []


def save_to_csv(all_news: List[Dict]):
    """
    뉴스를 CSV 파일로 저장
    
    Args:
        all_news: 저장할 뉴스 리스트
    """
    if not all_news:
        logger.warning("저장할 뉴스가 없습니다.")
        return
    
    try:
        # 데이터 디렉토리 생성
        DATA_DIR.mkdir(exist_ok=True)
        
        # DataFrame 생성
        df = pd.DataFrame(all_news)
        
        # 컬럼 순서 지정 (교차검증 컬럼 포함)
        base_columns = ['date', 'country', 'continent', 'title', 'summary', 'url', 'source', 'category', 'traffic_impact']
        optional_columns = ['confidence', 'validation', 'openai_summary', 'claude_summary']
        
        # 모든 컬럼 확인
        all_columns = base_columns + [col for col in optional_columns if col in df.columns]
        df = df.reindex(columns=all_columns)
        
        # 날짜순 정렬 (최신순)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date', ascending=False)
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        # CSV 저장 (UTF-8 with BOM for Excel compatibility)
        df.to_csv(NEWS_CSV, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_MINIMAL)
        
        logger.info(f"뉴스 {len(all_news)}개를 {NEWS_CSV}에 저장했습니다.")
        
    except Exception as e:
        logger.error(f"CSV 저장 실패: {e}")
        raise


def main():
    """메인 함수"""
    logger.info("=" * 50)
    logger.info("뉴스 수집 시작 (RSS → AI 정제 방식)")
    logger.info("=" * 50)
    
    try:
        # 키워드 로드
        keywords_config = load_keywords()
        base_keywords = keywords_config.get('base_keywords', [])
        priority_countries = keywords_config.get('priority_countries', {})
        traffic_impact_keywords = keywords_config.get('traffic_impact_keywords', {})
        
        # 기존 뉴스 로드
        existing_news = load_existing_news()
        logger.info(f"기존 뉴스: {len(existing_news)}개")
        
        # 1단계: RSS로 뉴스 수집
        logger.info("=" * 50)
        logger.info("1단계: RSS로 뉴스 수집 중...")
        logger.info("=" * 50)
        
        all_raw_news = []
        
        # 기본 키워드로 검색
        for keyword in base_keywords:
            news = fetch_news_from_rss(keyword)
            all_raw_news.extend(news)
            time.sleep(1)  # API 부하 방지
        
        # 주요 국가별 검색
        for country, country_info in priority_countries.items():
            # 국가 키워드
            for keyword in country_info.get('keywords', []):
                news = fetch_news_from_rss(keyword)
                for item in news:
                    item['country'] = country
                    item['continent'] = get_continent(country)
                all_raw_news.extend(news)
                time.sleep(1)
            
            # 국가별 주제 키워드
            for topic in country_info.get('topics', []):
                keyword = f"{country} {topic}"
                news = fetch_news_from_rss(keyword)
                for item in news:
                    item['country'] = country
                    item['continent'] = get_continent(country)
                all_raw_news.extend(news)
                time.sleep(1)
        
        # 트래픽 영향 키워드 검색
        for category, keywords in traffic_impact_keywords.items():
            for keyword in keywords[:3]:  # 각 카테고리당 최대 3개 키워드
                news = fetch_news_from_rss(keyword)
                all_raw_news.extend(news)
                time.sleep(1)
        
        logger.info(f"RSS 수집 완료: {len(all_raw_news)}개 뉴스")
        
        # 2단계: AI로 정제
        logger.info("=" * 50)
        logger.info("2단계: AI로 뉴스 정제 중...")
        logger.info("=" * 50)
        
        # API 타입 결정
        api_type = os.getenv('NEWS_API_TYPE', 'openai').lower()
        if api_type not in ['openai', 'claude']:
            api_type = 'openai'
        
        logger.info(f"사용할 AI API: {api_type.upper()}")
        
        all_refined_news = []
        skipped_count = 0
        
        for i, news_item in enumerate(all_raw_news, 1):
            if i % 10 == 0:
                logger.info(f"정제 진행 중: {i}/{len(all_raw_news)}")
            
            refined = refine_news_with_ai(news_item, api_type)
            
            if refined is None:
                skipped_count += 1
            else:
                all_refined_news.append(refined)
            
            time.sleep(1)  # API Rate Limit 방지
        
        logger.info(f"AI 정제 완료: {len(all_refined_news)}개 (스킵: {skipped_count}개)")
        
        # 중복 제거
        unique_new_news = remove_duplicates(existing_news, all_refined_news)
        
        # 기존 뉴스와 합치기
        all_news = existing_news + unique_new_news
        
        # 저장
        if unique_new_news:
            save_to_csv(all_news)
            logger.info(f"✅ {len(unique_new_news)}개의 새 뉴스를 추가했습니다.")
            return 0  # 성공 (변경사항 있음)
        else:
            logger.info("새로운 뉴스가 없습니다.")
            return 1  # 변경사항 없음
            
    except Exception as e:
        logger.error(f"뉴스 수집 중 오류 발생: {e}", exc_info=True)
        return -1  # 실패


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)

