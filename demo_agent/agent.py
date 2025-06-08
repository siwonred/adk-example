"""adk_agents.py — Google ADK (2025‑06) demo
================================================

Order cancellation agent with interactive order selection.
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

_orders: List[Dict[str, str]] = [
    {"id": "A001", "item": "블루투스 이어버드", "status": "processing"},
    {"id": "A002", "item": "USB‑C 충전기", "status": "processing"},
]

def get_weather(location: str) -> Dict[str, str]:
    """Return current weather (very fake!)."""
    forecast = _FAKE_FORECASTS.get(location.lower(), "구름 조금, 24  °C")
    return {"status": "success", "report": forecast}

def retrieve_doc(query: str) -> Dict[str, str]:
    """Extremely naïve keyword matcher that returns one best doc."""
    best = max(_DOCS, key=lambda d: sum(tok in d["content"] for tok in query.split()))
    return {"status": "success", "snippet": best["content"]}

def get_orders(state: Optional[str] = None) -> Dict[str, List[Dict[str, str]]]:
    """Return orders, optionally filtering by status/state string."""
    if state is None:
        filtered = _orders
    else:
        filtered = [o for o in _orders if o["status"] == state]
    return {
        "status": "success",
        "orders": filtered,
    }

def cancel_order(order_id: str) -> Dict[str, str]:
    """Cancel an order by ID."""
    for o in _orders:
        if o["id"] == order_id and o["status"] == "processing":
            o["status"] = "cancelled"
            return {"status": "success", "result": f"주문 {order_id} 취소 완료"}
    return {"status": "error", "error_message": "해당 주문을 찾을 수 없거나 이미 취소되었습니다."}

# ---------- Core Business Logic -----------------------------
def choose_order(state: Optional[str] = None, order_id: Optional[str] = None) -> Dict:
    """주문 선택 툴 - order_id가 없으면 목록 조회, 있으면 해당 주문 선택"""
    
    # 사용자가 특정 주문 ID를 선택한 경우
    if order_id:
        for order in _orders:
            if order["id"] == order_id and (not state or order["status"] == state):
                return {
                    "status": "success",
                    "selected_order_id": order_id,
                    "options": [],
                    "message": f"주문 {order_id}({order['item']})를 선택했습니다."
                }
        return {
            "status": "error", 
            "selected_order_id": None,
            "options": [],
            "message": f"주문 {order_id}를 찾을 수 없거나 상태가 맞지 않습니다."
        }
    
    # 주문 목록 조회 및 자동 선택 로직
    orders = get_orders(state)
    if orders["status"] == "success":
        if len(orders["orders"]) == 1:
            return {
                "status": "success",
                "selected_order_id": orders["orders"][0]["id"],
                "options": orders["orders"],
                "message": f"주문 {orders['orders'][0]['id']}를 선택했습니다."
            }
        else:
            return {
                "status": "pending",
                "selected_order_id": None,
                "options": orders["orders"],
                "message": "주문이 2개 이상이므로 사용자에게 주문을 선택하라고 해주세요."
            }
    else:
        return {
            "status": "error",
            "selected_order_id": None, 
            "options": [],
            "message": "주문 목록을 가져오는데 실패했습니다."
        }

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

cancel_order_agent = LlmAgent(
    name="cancel_order_agent",
    model=gemini,
    instruction=(
        "Help users cancel orders. Start by calling `choose_order()` to see orders. "
        "If multiple orders, show list and ask user to pick one. "
        "When user gives order ID like A001, "
        "  call `choose_order(order_id='A001')` then "
        "  ask for final confirmation and then "
        "  call `cancel_order(order_id='A001')`. "
        "Respond in Korean."
    ),
    tools=[choose_order, cancel_order],
)

travel_planner_agent = TravelPlannerAgent()

root_agent = Agent(
    name="router",
    model=gemini,
    description="Routes incoming messages to specialised sub-agents.",
    instruction=(
        "Analyse the user request and decide which sub-agent is best suited.\n"
        "Rules:\n"
        "• Contains '날씨' or 'weather' → delegate to `weather_agent`.\n"
        "• Contains '취소', 'cancel', or looks like an order cancellation → delegate to `cancel_order_agent`.\n"
        "• Contains '여행', 'travel plan' → delegate to `travel_planner_agent`.\n"
        "• Otherwise → delegate to `rag_agent`.\n"
        "Use the `delegate(to=...)` action to transfer control."),
    sub_agents=[weather_agent, cancel_order_agent, rag_agent, travel_planner_agent],
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
