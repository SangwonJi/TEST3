# API 설정 가이드

## 📰 뉴스 검색 방법

이 프로젝트는 여러 방법으로 뉴스를 검색할 수 있습니다:

### 1. RSS 피드 (기본, API 키 불필요) ✅

**완전 무료, API 키 불필요!**

- Google News RSS 피드를 사용하여 실시간 뉴스 검색
- 상승/하락 국가와 관련된 뉴스를 자동으로 필터링
- 별도 설정 불필요, 바로 사용 가능

### 2. Gemini API (선택사항, 무료 티어) 🤖

**Google AI Studio에서 무료 API 키 발급 가능**

1. **API 키 발급:**
   - https://aistudio.google.com/app/apikey 접속
   - Google 계정으로 로그인
   - "Create API Key" 클릭
   - API 키 복사

2. **로컬 개발 설정:**
   ```bash
   # config.js.example을 config.js로 복사
   cp config.js.example config.js
   
   # config.js 파일 편집
   # GEMINI_API_KEY에 발급받은 키 입력
   ```

3. **GitHub Pages 배포 시:**
   - GitHub 저장소 → Settings → Secrets and variables → Actions
   - "New repository secret" 클릭
   - Name: `GEMINI_API_KEY`
   - Value: 발급받은 API 키 입력
   - GitHub Actions가 자동으로 config.js 생성

### 3. GPT API (선택사항) 🤖

**OpenAI API 키 필요 (유료 또는 무료 크레딧)**

1. **API 키 발급:**
   - https://platform.openai.com/api-keys 접속
   - 계정 생성 및 API 키 발급

2. **설정:**
   - `config.js`에 `GPT_API_KEY` 추가
   - 또는 GitHub Secrets에 추가

## 🚀 사용 방법

### 기본 사용 (RSS만)

별도 설정 없이 바로 사용 가능합니다!

### Gemini/GPT 사용

1. `config.js` 파일 생성 (로컬 개발)
2. API 키 입력
3. `index.html`에서 해당 함수 주석 해제

## 📝 참고사항

- **RSS 피드**: 무료, API 키 불필요, 즉시 사용 가능
- **Gemini API**: 무료 티어 제공, API 키 필요
- **GPT API**: 유료 (무료 크레딧 제공), API 키 필요

## 🔒 보안

- `config.js`는 `.gitignore`에 포함되어 있어 GitHub에 업로드되지 않습니다
- GitHub Secrets를 사용하면 안전하게 API 키를 관리할 수 있습니다
- 클라이언트 사이드에서 API 키를 사용하므로, 제한된 API 키 사용을 권장합니다

