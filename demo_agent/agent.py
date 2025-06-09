"""adk_agents.py — Google ADK (2025‑06) demo
================================================

Multi-agent system with weather, order management, travel planning, and RAG capabilities.
"""

from __future__ import annotations

import asyncio
import os
from typing import Dict, List, Optional
import logging

# ---------- ADK imports -----------------------------
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
from google.genai.types import UserContent, Part
from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from .travel_planner import TravelPlannerAgent
from .order import OrderAgent

# ---------- Configuration -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

gemini = Gemini(
    api_key=os.getenv("GEMINI_API_KEY"),
    model_name="gemini-2.5-pro-preview-05-06"
)

# ---------- Mock Data and Backend Functions -----------------------------
_FAKE_FORECASTS = {
    "seoul": "맑음, 25 °C",
    "busan": "부분적으로 흐림, 23 °C",
    "tokyo": "비, 21 °C",
}

_DOCS = [
    {
        "id": "doc1",
        "content": (
            "Google ADK(Agent Development Kit)는 코드를 중심으로 AI 에이전트를 손쉽게 "
            "구축·배포할 수 있게 해 주는 오픈소스 프레임워크입니다."
        ),
    },
    {
        "id": "doc2",
        "content": "Routing 기능을 통해 하나의 엔드포인트에서 여러 하위 에이전트를 호출할 수 있습니다.",
    },
]

def get_weather(location: str) -> Dict[str, str]:
    """Return current weather (very fake!)."""
    forecast = _FAKE_FORECASTS.get(location.lower(), "구름 조금, 24  °C")
    return {"status": "success", "report": forecast}

def retrieve_doc(query: str) -> Dict[str, str]:
    """Extremely naïve keyword matcher that returns one best doc."""
    best = max(_DOCS, key=lambda d: sum(tok in d["content"] for tok in query.split()))
    return {"status": "success", "snippet": best["content"]}

# ---------- Agents Definition -----------------------------
weather_agent = Agent(
    name="weather_agent",
    model=gemini,
    description="Provides quick weather summaries.",
    instruction=(
        "If the user asks about weather, call `get_weather(location)` and present the report "
        "politely in Korean. If the user doesn't specify a city, default to Seoul."),
    tools=[get_weather],
)

rag_agent = Agent(
    name="rag_agent",
    model=gemini,
    description="General Q&A backed by a mini RAG store.",
    instruction=(
        "Use `retrieve_doc(query)` whenever external knowledge is needed. "
        "Cite the snippet in your answer."),
    tools=[retrieve_doc],
)

travel_planner_agent = TravelPlannerAgent()

order_agent = OrderAgent()

root_agent = Agent(
    name="router",
    model=gemini,
    description="Routes incoming messages to specialised sub-agents.",
    instruction=(
        "Analyse the user request and decide which sub-agent is best suited.\n"
        "Rules:\n"
        "• Contains '날씨' or 'weather' → delegate to `weather_agent`.\n"
        "• Contains '주문', '취소', 'order', 'cancel', '조회', '생성', '목록', '상태', '확인', '주문하기', '주문생성', '주문취소', '주문조회', '구매', '결제', '배송' or anything order-related → delegate to `order_agent`.\n"
        "• Contains '여행', 'travel plan' → delegate to `travel_planner_agent`.\n"
        "• Otherwise → delegate to `rag_agent`.\n"
        "Use the `delegate(to=...)` action to transfer control."),
    sub_agents=[weather_agent, order_agent, rag_agent, travel_planner_agent],
)

# ---------- Main Execution -----------------------------
async def main():
    print("🔧 ADK multi‑agent demo.  Type 'exit' to quit.")
    app_name = "adk-multi-agent-demo"
    user_id = "local-user"

    runner = InMemoryRunner(root_agent, app_name=app_name)

    # async 세션 생성
    session = await runner.session_service.create_session(app_name=app_name, user_id=user_id)

    while True:
        try:
            # async 입력 패턴 사용
            new_message = await asyncio.to_thread(input, "\n👤 > ")
        except (EOFError, KeyboardInterrupt):
            break
        
        if new_message.lower().strip() in ["exit", "quit", "bye"]:
            break
            
        content = UserContent(parts=[Part(text=new_message)])
        
        # async generator 패턴 사용
        async for event in runner.run_async(user_id=session.user_id, session_id=session.id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts:
                print("🤖 >", event.content.parts[0].text)

if __name__ == "__main__":
    asyncio.run(main())
