# 🤖 Google ADK (Agent Development Kit) Demo

우리 팀을 위한 **Google ADK** 학습 및 데모 프로젝트입니다.

## 📖 ADK란?

**Google Agent Development Kit (ADK)**는 Google에서 개발한 오픈소스 AI 에이전트 개발 프레임워크입니다.

### 🌟 주요 특징
- **🔧 쉬운 에이전트 개발**: LLM 기반 에이전트를 간단하게 구축
- **🔀 멀티 에이전트 시스템**: 여러 에이전트 간의 협업 및 라우팅
- **🛠️ 풍부한 도구 통합**: Function Tools, API 연동 등
- **💾 상태 관리**: 세션 기반 상태 저장 및 공유
- **🌐 웹 UI 제공**: 브라우저에서 에이전트 테스트 가능

## 📁 프로젝트 구조

```
adk-example/
├── demo_agent/              # 📦 Demo Agent 패키지
│   ├── __init__.py         # 패키지 초기화
│   ├── __main__.py         # 모듈 실행 엔트리포인트
│   ├── travel_planner.py   # 여행 계획 에이전트 (Custom Agent)
│   └── agent.py           # 메인 데모 에이전트
├── .gitignore             # Python용 gitignore
└── README.md              # 이 파일
```

## 🚀 데모 실행 방법

### 1. 환경 변수 설정

Gemini API 키를 설정하세요:

```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

### 2. 콘솔에서 에이전트 실행

#### 📝 Demo Agent 실행

**방법 1: 모듈로 실행 (권장)**
```bash
python -m demo_agent
```

**방법 2: 직접 실행**
```bash
cd demo_agent
python agent.py
```

**기능:**
- 여러 에이전트를 통합한 데모
- Travel Planner Agent 포함
- 멀티 에이전트 라우팅 시스템
- 기본적인 ADK 패턴 학습용

### 3. 웹 UI에서 데모하기

ADK Web UI를 사용하여 브라우저에서 에이전트를 테스트할 수 있습니다:

```bash
adk web --port 8000
```

웹 브라우저에서 다음 주소로 접속:
```
http://localhost:8000
```

**웹 UI 기능:**
- 🎯 직관적인 채팅 인터페이스
- 📊 실시간 이벤트 로그 확인
- 🔍 세션 상태 디버깅
- 🔧 에이전트 도구 호출 추적

## 📚 학습 포인트

### 1. **LlmAgent** (기본 패턴)
```python
agent = LlmAgent(
    name="simple_agent",
    model=gemini,
    instruction="You are a helpful assistant",
    output_key="result"  # 자동으로 state에 저장
)
```

### 2. **Custom Agent** (고급 패턴)
```python
class MyCustomAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        # 복잡한 워크플로우 로직
        async for event in self.sub_agent.run_async(ctx):
            yield event
```

### 3. **멀티 에이전트 라우팅**
```python
root_agent = Agent(
    sub_agents=[weather_agent, order_agent, rag_agent],
    instruction="Analyze request and delegate to best agent"
)
```

### 4. **상태 관리**
```python
# 상태 저장
ctx.session.state["key"] = "value"

# 상태 읽기
value = ctx.session.state.get("key")
```

## 🛠️ 개발 팁

### 환경 설정
```bash
# Python 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows

# ADK 설치
pip install google-adk
```

### 디버깅
- **콘솔 로그**: 에이전트 실행 과정을 자세히 확인
- **웹 UI**: 시각적으로 에이전트 동작 이해
- **상태 출력**: `print(ctx.session.state)` 로 현재 상태 확인

### 모듈 Import 에러 해결
```python
# ✅ 패키지 내부에서 상대 import 사용
from .travel_planner import TravelPlannerAgent

# ✅ 외부에서 모듈로 실행
python -m demo_agent

# ❌ 직접 실행시 import 에러 발생 가능성
python demo_agent/agent.py  # 외부에서 실행시 에러 가능
```

### 최신 패턴 사용
```python
# ✅ 권장: async 패턴
async for event in runner.run_async(...):
    pass

# ❌ 비권장: sync 패턴 (deprecated)
events = runner.run(...)
```

## 🎯 다음 단계

1. **🔧 툴 통합**: 외부 API, 데이터베이스 연동
2. **📊 고급 워크플로우**: SequentialAgent, ParallelAgent 활용
3. **☁️ 클라우드 배포**: Google Cloud Run, Vertex AI 연동
4. **🔒 보안**: API 키 관리, 인증 시스템 구축

## 📖 참고 자료

- **공식 문서**: [ADK Documentation](https://google.github.io/adk-docs/)
- **GitHub**: [google/adk](https://github.com/google/adk)
- **예제 모음**: [ADK Samples](https://github.com/google/adk/tree/main/samples)

---

**Happy Agent Building! 🎉** 