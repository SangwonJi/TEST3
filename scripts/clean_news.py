"""
news.csv에서 게임/트래픽과 무관한 뉴스를 정리하는 스크립트
"""
import pandas as pd
import os
import re

NEWS_CSV = 'data/news.csv'

# 제외할 키워드 패턴
EXCLUDE_KEYWORDS = [
    # 군사/방산
    '자주포', '전차', '미사일', '무기', '군수', '방산', '국방',
    'K9', 'K2', '한화에어로', '한화디펜스', 'defense contract',
    '방위사업', 'military contract', 'arms deal',
    'DMZ', 'Korean War soldiers', '유해 발굴', '전사자',
    # 연예/시상식 (트래픽 무관)
    'MAMA', 'Awards', '시상식', 'mourning', 'tragedy', 'Hong Kong tragedy',
    'K-pop', 'idol', '아이돌',
    # 일반 시위 (인터넷 차단 없으면 무관)
    'PROTEST', 'protest', 'immigration protest', 'hindu protest',
    # 광고/마케팅
    '캠페인', 'campaign', '프로모션', 'promotion', '팝업', 'popup',
    '콜라보', 'collaboration', '신제품',
    # 연예/엔터
    '걸그룹', '보이그룹', '아이돌', '콘서트', '앨범', '팬미팅',
    '뮤직비디오', 'idol', 'concert', 'album',
    # 음식/브랜드
    '던킨', '스타벅스', '맥도날드', '버거킹', '엠앤엠', 'M&M',
    # 패션/뷰티
    '패션', '뷰티', '화장품', '의류',
    # 정치/외교
    '대통령', '국회', '외교부', '장관', '정상회담',
    # 스포츠 (e스포츠 제외)
    '프로축구', '프로야구', 'FIFA', 'NBA', 'MLB',
]

# 반드시 포함해야 하는 게임 키워드 (게임 뉴스용)
GAMING_REQUIRED = [
    'pubg', '펍지', '배틀그라운드', 'krafton', '크래프톤', 'bgmi',
    'free fire', '프리파이어', 'call of duty', '콜오브듀티',
    'mobile game', '모바일 게임', '모바일게임',
    'esports', 'e-sports', '이스포츠', 'pmgc', 'pmpl',
    '게임 업데이트', '게임 패치', '게임 대회'
]

# 트래픽 영향 키워드 (트래픽 뉴스용)
TRAFFIC_REQUIRED = [
    '인터넷 차단', 'internet shutdown', '통신 장애', 'network outage',
    '정전', 'power outage', '지진', 'earthquake', '태풍', 'typhoon',
    '홍수', 'flood', '전쟁', 'war', '폭발', 'explosion', '테러',
    '공휴일', 'holiday', '연휴', '명절', '방학', '시험',
    '시위', 'protest', '폭동', 'riot', '계엄', 'curfew'
]


def should_exclude(title: str, summary: str) -> bool:
    """뉴스가 제외 대상인지 확인"""
    text = f"{title} {summary}".lower()
    
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in text:
            return True
    return False


def is_valid_gaming_news(title: str, summary: str) -> bool:
    """유효한 게임 뉴스인지 확인"""
    text = f"{title} {summary}".lower()
    
    for keyword in GAMING_REQUIRED:
        if keyword.lower() in text:
            return True
    return False


def is_valid_traffic_news(title: str, summary: str) -> bool:
    """유효한 트래픽 영향 뉴스인지 확인"""
    text = f"{title} {summary}".lower()
    
    for keyword in TRAFFIC_REQUIRED:
        if keyword.lower() in text:
            return True
    return False


def clean_news():
    if not os.path.exists(NEWS_CSV):
        print(f"Error: {NEWS_CSV} not found.")
        return
    
    df = pd.read_csv(NEWS_CSV, encoding='utf-8-sig')
    original_count = len(df)
    print(f"원본 뉴스 개수: {original_count}")
    
    # 삭제할 인덱스 리스트
    to_remove = []
    
    for idx, row in df.iterrows():
        title = str(row.get('title', ''))
        summary = str(row.get('summary', ''))
        news_type = str(row.get('news_type', ''))
        
        # 1. 제외 키워드 체크
        if should_exclude(title, summary):
            to_remove.append(idx)
            continue
        
        # 2. 게임 뉴스인데 게임 키워드가 없는 경우
        if news_type == 'gaming' and not is_valid_gaming_news(title, summary):
            # 트래픽 영향 뉴스인지 확인
            if is_valid_traffic_news(title, summary):
                # 트래픽 뉴스로 재분류
                df.at[idx, 'news_type'] = 'traffic_impact'
            else:
                to_remove.append(idx)
            continue
        
        # 3. news_type이 비어있는 경우
        if not news_type or news_type == '' or news_type == 'nan':
            if is_valid_gaming_news(title, summary):
                df.at[idx, 'news_type'] = 'gaming'
            elif is_valid_traffic_news(title, summary):
                df.at[idx, 'news_type'] = 'traffic_impact'
            else:
                to_remove.append(idx)
            continue
    
    # 삭제
    df = df.drop(to_remove)
    
    # 저장
    df.to_csv(NEWS_CSV, index=False, encoding='utf-8-sig')
    
    removed_count = len(to_remove)
    final_count = len(df)
    
    print("\n" + "="*50)
    print(f"[OK] Cleaning Complete")
    print(f"   Original: {original_count}")
    print(f"   Removed: {removed_count}")
    print(f"   Final: {final_count}")
    print("="*50)
    
    # 통계
    print("\n[STATS] News Type Distribution:")
    print(df['news_type'].value_counts())


if __name__ == "__main__":
    clean_news()

