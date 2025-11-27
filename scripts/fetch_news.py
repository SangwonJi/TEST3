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
        
        # 컬럼 순서 지정
        columns = ['date', 'country', 'continent', 'title', 'summary', 'url', 'source', 'category']
        df = df.reindex(columns=columns)
        
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
    logger.info("뉴스 수집 시작")
    logger.info("=" * 50)
    
    try:
        # 키워드 로드
        keywords_config = load_keywords()
        base_keywords = keywords_config.get('base_keywords', [])
        country_keywords = keywords_config.get('country_keywords', {})
        
        # 기존 뉴스 로드
        existing_news = load_existing_news()
        logger.info(f"기존 뉴스: {len(existing_news)}개")
        
        # 새 뉴스 수집
        all_new_news = []
        
        # 기본 키워드로 검색
        for keyword in base_keywords:
            news = fetch_news_from_rss(keyword)
            all_new_news.extend(news)
            time.sleep(2)  # API 부하 방지
        
        # 국가별 키워드로 검색
        for country, country_keyword_list in country_keywords.items():
            for keyword in country_keyword_list:
                news = fetch_news_from_rss(keyword)
                all_new_news.extend(news)
                time.sleep(2)
        
        # 중복 제거
        unique_new_news = remove_duplicates(existing_news, all_new_news)
        
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

