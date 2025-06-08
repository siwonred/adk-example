"""travel_planner.py — ADK Travel Planner Agent
===============================================

여행 계획을 도와주는 Custom Agent
- 도시 입력 받기
- 도시 정보 제공하기
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import AsyncGenerator

# ---------- ADK imports -----------------------------
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.runners import InMemoryRunner
from google.adk.events import Event
from google.genai.types import UserContent, Part
from google.adk.models import Gemini

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

# ---------- Travel Planner Custom Agent -----------------------------
class TravelPlannerAgent(BaseAgent):
    """여행 계획을 도와주는 Custom Agent"""
    
    # Pydantic 필드 선언
    city_input_agent: LlmAgent
    city_info_agent: LlmAgent
    
    # Pydantic 설정
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self):
        # 내부에서 사용할 LlmAgent들 정의
        city_input_agent = LlmAgent(
            name="city_input_agent",
            model=gemini,
            description="사용자에게 여행하고 싶은 도시를 묻는 에이전트",
            instruction=(
                "당신은 친근한 여행 상담사입니다. "
                "사용자에게 어떤 도시로 여행을 가고 싶은지 물어보세요. "
                "사용자가 도시를 말하면, 정확한 도시명만 간단하게 반환하세요. "
                "예: '서울', '도쿄', '파리' 등 "
                "영어 도시명은 한국어로 번역해서 반환하세요. "
                "모호한 답변이면 다시 구체적인 도시명을 요청하세요."
            ),
            output_key="target_city"  # state['target_city']에 저장
        )
        
        city_info_agent = LlmAgent(
            name="city_info_agent", 
            model=gemini,
            description="도시 정보를 제공하는 에이전트",
            instruction=(
                "당신은 여행 정보 전문가입니다. "
                "state['target_city']에 저장된 도시에 대한 정보를 제공하세요. "
                "다음 정보를 포함해서 친근하게 설명해주세요:\n"
                "1. 도시 소개 (위치, 특징)\n"
                "2. 주요 관광지 3-4곳\n"
                "3. 추천 음식\n"
                "4. 여행 팁 (교통, 날씨 등)\n"
                "5. 추천 여행 기간\n\n"
                "정보는 구체적이고 실용적으로 제공해주세요."
            ),
            output_key="city_info"  # state['city_info']에 저장
        )
        
        # BaseAgent 초기화 (Pydantic 방식)
        super().__init__(
            name="travel_planner_agent",
            description="여행 계획을 도와주는 통합 에이전트",
            sub_agents=[city_input_agent, city_info_agent],
            city_input_agent=city_input_agent,
            city_info_agent=city_info_agent
        )
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Custom Agent의 핵심 실행 로직"""
        logger.info(f"[{self.name}] 여행 계획 도우미를 시작합니다!")
        
        # 1단계: 도시 입력 받기
        logger.info(f"[{self.name}] 1단계: 도시 입력 받기")
        async for event in self.city_input_agent.run_async(ctx):
            logger.info(f"[{self.name}] City Input Event: {event}")
            yield event
        
        # 도시가 입력되었는지 확인
        target_city = ctx.session.state.get("target_city")
        if not target_city:
            logger.error(f"[{self.name}] 도시 정보를 받지 못했습니다.")
            return
        
        logger.info(f"[{self.name}] 선택된 도시: {target_city}")
        
        # 2단계: 도시 정보 제공
        logger.info(f"[{self.name}] 2단계: {target_city} 정보 제공")
        async for event in self.city_info_agent.run_async(ctx):
            logger.info(f"[{self.name}] City Info Event: {event}")
            yield event
        
        logger.info(f"[{self.name}] 여행 계획 도우미 완료!")
