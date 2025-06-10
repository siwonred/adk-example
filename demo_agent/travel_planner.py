"""travel_planner.py — ADK Travel Planner Agent
===============================================

여행 계획을 도와주는 Custom Agent
- 도시 입력 받기 (LLM 판단 + 코드 제어)
- 도시 정보 제공하기
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import AsyncGenerator, Literal, ClassVar, Optional
from pydantic import BaseModel

# ---------- ADK imports -----------------------------
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.runners import InMemoryRunner
from google.adk.events import Event, EventActions
from google.adk.models import LlmResponse
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
    model="gemini-2.5-flash-preview-05-20"
)

# ---------- Pydantic Schemas -----------------------------
class CitySelectionDecision(BaseModel):
    """도시 선택 판단 결과 스키마"""
    decision: Literal["complete", "continue"]
    city_name: str = ""
    confidence: Literal["high", "medium", "low"] = "low"
    reason: str = ""
    user_message: str = ""  # 유저에게 보여줄 메시지

# ---------- Travel Planner Router Agent -----------------------------
class TravelPlannerAgent(BaseAgent):
    """output_schema 기반 하이브리드 여행 계획 라우터"""
    
    # Pydantic 필드 선언
    city_input_agent: LlmAgent
    city_info_agent: LlmAgent
    
    # Pydantic 설정
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self):
        # JSON 후처리 함수 - user_message만 추출
        def extract_user_message(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
            """JSON 블록에서 user_message만 추출해서 유저에게 보여주고, 전체 JSON은 state에 저장
            
            📝 output_schema 활용 패턴들:
            1. 현재: JSON → user_message만 추출
            2. 가능: JSON → 마크다운 형식으로 변환
            3. 가능: JSON → 다국어 번역 후 표시
            4. 가능: JSON → 조건부 메시지 선택
            5. 가능: JSON → 완전히 다른 형태로 재구성
            
            🎯 핵심: output_schema는 구조화용, callback은 UX용으로 완전 분리!
            """
            logger.info(f"[callback] extract_user_message 시작")
            
            if llm_response.content and llm_response.content.parts and llm_response.content.parts[0].text:
                response_text = llm_response.content.parts[0].text
                logger.info(f"[callback] 원본 응답 길이: {len(response_text)}")
                logger.info(f"[callback] 원본 응답 앞 200자: {response_text[:200]}")
                
                try:
                    # ```json 블록 찾기
                    import re
                    json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
                    if json_match:
                        json_text = json_match.group(1)
                        logger.info(f"[callback] JSON 블록 발견, 추출 성공")
                    else:
                        # JSON 블록이 없으면 전체 텍스트에서 JSON 추출 시도
                        json_text = response_text
                        logger.info(f"[callback] JSON 블록 없음, 전체 텍스트 사용")
                    
                    logger.info(f"[callback] 추출된 JSON: {json_text}")
                    
                    # JSON 파싱
                    import json
                    decision_data = json.loads(json_text)
                    logger.info(f"[callback] JSON 파싱 성공: {decision_data}")
                    
                    callback_context.state["city_input_agent_output"] = decision_data
                    
                    # user_message만 추출해서 유저에게 보여주기
                    user_message = decision_data.get("user_message", "")
                    logger.info(f"[callback] 추출된 user_message: {user_message}")
                    
                    if user_message:
                        from google.genai.types import Content, Part
                        new_content = Content(
                            role="model",
                            parts=[Part(text=user_message)]
                        )
                        logger.info(f"[callback] user_message로 응답 생성 완료")
                        return LlmResponse(content=new_content)
                    
                except (json.JSONDecodeError, KeyError, AttributeError) as e:
                    # JSON 파싱 실패시 원본 사용
                    logger.warning(f"[callback] JSON 파싱 실패: {e}")
                    logger.warning(f"[callback] 파싱 실패한 텍스트: {response_text}")
                    pass
            else:
                logger.warning(f"[callback] LLM 응답이 비어있음")
            
            # 변경 없으면 None 반환 (원본 사용)
            logger.info(f"[callback] 원본 사용")
            return None
        
        # 도시 입력 에이전트 (LLM이 구조화된 판단 반환)
        city_input_agent = LlmAgent(
            name="city_input_agent",
            model=gemini.model,
            description="여행 도시를 확인하는 에이전트",
            instruction=(
                "# 🏙️ 도시 확인 에이전트\n\n"
                
                "## 🎯 역할\n"
                "사용자의 여행 의도에서 **구체적인 도시명**을 파악하고 확정하는 전문가입니다.\n\n"
                
                "## 📋 수행 작업\n"
                "1. 사용자 입력에서 도시명 추출 시도\n"
                "2. 도시명이 명확한지 판단\n"
                "3. 결과를 JSON 형식으로 반환\n\n"
                
                "## 📤 출력 형식\n"
                "반드시 다음 JSON 형식으로만 응답하세요:\n\n"
                "```json\n"
                "{\n"
                '  "decision": "complete" | "continue",\n'
                '  "city_name": "확정된 도시명 또는 빈 문자열",\n'
                '  "confidence": "high" | "medium" | "low",\n'
                '  "reason": "판단 근거",\n'
                '  "user_message": "사용자에게 전달할 메시지"\n'
                "}\n"
                "```\n\n"
                
                "## 🔍 판단 기준\n"
                "### ✅ `decision: \"complete\"` 조건\n"
                "- **구체적 도시명** 명시: 파리, 도쿄, 뉴욕, 서울 등\n"
                "- **명확성**: 다른 해석이 불가능\n"
                "- **confidence**: high/medium\n\n"
                
                "### 🔄 `decision: \"continue\"` 조건\n"
                "- **지역명만**: 유럽, 아시아, 동남아시아 등\n"
                "- **추상적 표현**: 따뜻한 곳, 시원한 곳, 유명한 곳 등\n"
                "- **모호함**: 여러 도시 가능성\n"
                "- **confidence**: low\n\n"
                
                "## 💬 메시지 작성 가이드\n"
                "### Complete인 경우\n"
                "- 간단한 확인: \"○○ 여행이시군요! 알겠습니다. 찾아볼께요!\"\n"
                "- 도시명만 언급, 추가 질문 없음\n\n"
                
                "### Continue인 경우\n"
                "- 도시명 구체화 요청\n"
                "- 단순하고 직접적인 질문\n"
                "- 유저가 넓은 범주를 말한 경우, 고르기 쉽게 예시 제시"
                "- 예: \"어떤 도시를 생각하고 계신가요?\"\n\n"
                
                "## 📚 예시\n\n"
                "**사용자 입력:** \"파리 가고 싶어요\"\n"
                "**모델 출력:**\n"
                "```json\n"
                "{\n"
                '  "decision": "complete",\n'
                '  "city_name": "파리",\n'
                '  "confidence": "high",\n'
                '  "reason": "명확한 도시명 제시됨",\n'
                '  "user_message": "파리 여행이시군요! 네 알겠습니다! 찾아보도록 하겠습니다 :)"\n'
                "}\n"
                "```\n\n"
                
                "**사용자 입력:** \"유럽 여행 생각 중이에요\"\n"
                "**모델 출력:**\n"
                "```json\n"
                "{\n"
                '  "decision": "continue",\n'
                '  "city_name": "",\n'
                '  "confidence": "low",\n'
                '  "reason": "지역명만 있고 구체적 도시 없음",\n'
                '  "user_message": "유럽의 어떤 도시를 생각하고 계신가요? 파리나 런던, 로마는 어떠세요?"\n'
                "}\n"
                "```\n\n"
                
                "## ⚠️ 중요 사항\n"
                "- **여행 계획은 묻지 마세요** (예산, 기간, 스타일, 활동)\n"
                "- **도시명 확보에만 집중**하세요\n"
                "- **JSON 형식을 정확히** 따르세요\n"
                "- **간결하고 명확한** 메시지를 작성하세요"
            ),
            after_model_callback=extract_user_message,  # 🎯 JSON에서 user_message만 추출 + state 저장
            disallow_transfer_to_peers=True  # 🚫 Peer transfer 금지
        )
        
        # 도시 정보 제공 에이전트  
        city_info_agent = LlmAgent(
            name="city_info_agent", 
            model=gemini.model,
            description="선택된 도시에 대한 상세 정보를 제공하는 에이전트",
            instruction=(
                "당신은 여행 정보 전문가입니다.\n"
                "**중요: 즉시 구체적이고 상세한 여행 정보를 제공하세요!**\n\n"
                
                "**반드시 포함할 내용:**\n"
                "1. 📍 도시 소개 (위치, 특징)\n"
                "2. 🏛️ 주요 관광지 3-4곳 (구체적인 장소명과 설명)\n"
                "3. 🍜 추천 음식 (대표 요리와 맛집)\n"
                "4. 💡 여행 팁 (교통, 날씨, 주의사항)\n"
                "5. ⏰ 추천 여행 기간\n\n"
                
                "**작성 원칙:**\n"
                "- '준비해드리겠습니다', '알려드릴게요' 같은 예고 말고 바로 정보 제공!\n"
                "- 구체적인 장소명, 음식명, 가격 정보 포함\n"
                "- 실용적이고 도움되는 팁 위주\n"
                "- 최소 200자 이상의 상세한 설명\n\n"
                
                "**좋은 예시 시작:**\n"
                "'가고시마는 일본 규슈 남부에 위치한 화산과 온천의 도시입니다. 🌋'\n\n"
                
                "**나쁜 예시 (금지!):**\n"
                "'가고시마 여행 정보를 준비해드리겠습니다!'\n"
                "'정보를 정리해서 알려드릴게요!'\n\n"
                
                "🎯 **핵심: 예고 없이 바로 상세 정보 제공!**"
            ),
            output_key="city_info",
            disallow_transfer_to_peers=True  # 🚫 Peer transfer 금지
        )
        
        # BaseAgent 초기화 (Pydantic 방식)
        super().__init__(
            name="travel_planner_agent",
            description="output_schema 기반 여행 계획 라우터",
            sub_agents=[city_input_agent, city_info_agent],
            city_input_agent=city_input_agent,
            city_info_agent=city_info_agent
        )
    
    async def _cleanup_state(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """여행 계획 관련 상태 정리 (Event state_delta 방식)"""
        # 🧹 정리할 상태 키들 정의 (함수 내부 상수)
        STATE_KEYS_TO_CLEANUP = [
            "target_city",
            "city_selection_complete",
            "city_input_agent_output",
            "city_info"
        ]
        
        # 🎯 ADK 올바른 방식: Event의 state_delta를 통한 상태 정리
        state_deltas = {}
        
        # 정리할 키들 확인 후 state_delta에 None 설정 (삭제 의미)
        keys_to_remove = []
        for key in STATE_KEYS_TO_CLEANUP:
            if key in ctx.session.state:
                keys_to_remove.append(key)
                state_deltas[key] = None  # None으로 설정하면 삭제
        
        if state_deltas:
            logger.info(f"[{self.name}] 🧹 state_delta로 상태 정리: {keys_to_remove}")
            
            # EventActions를 통해 state 변경 요청
            cleanup_actions = EventActions(state_delta=state_deltas)
            
            # Event를 yield하여 Runner가 상태 정리 처리
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                actions=cleanup_actions,
                content=None  # 내부 정리 작업이므로 content 없음
            )
            
            logger.info(f"[{self.name}] ✅ 상태 정리 Event 생성 완료")
        else:
            logger.debug(f"[{self.name}] 🔍 정리할 상태 없음")
    
    def _is_city_already_selected(self, ctx: InvocationContext) -> bool:
        """도시가 이미 선택되어 있는지 확인"""
        return bool(ctx.session.state.get("target_city"))
    
    async def _ensure_city_selection(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """도시 선택 시도 (한 번만, continue시 턴 종료)"""
        logger.info(f"[{self.name}] 🎯 도시 입력을 city_input_agent에게 위임")
        
        # city_input_agent 직접 호출 (after_model_callback이 JSON 자동 제거)
        async for event in self.city_input_agent.run_async(ctx):
            yield event
        
        # LLM 판단 결과 처리 (원본 응답에서 JSON 파싱)
        self._process_city_decision(ctx)
        
        logger.info(f"[{self.name}] 도시 선택 시도 완료")
    
    def _process_city_decision(self, ctx: InvocationContext) -> bool:
        """LLM의 도시 선택 판단 결과 처리 (output_schema 기반)"""
        logger.info(f"[{self.name}] 현재 session state 전체: {dict(ctx.session.state)}")
        
        decision_data = ctx.session.state.get("city_input_agent_output")
        try:
            # Pydantic 검증
            decision = CitySelectionDecision.model_validate(decision_data)
            logger.info(f"[{self.name}] LLM 판단: {decision.decision}/{decision.confidence} - {decision.city_name} ({decision.reason})")
            
            # 도시명 검증 추가
            if (decision.decision == "complete" and 
                decision.confidence in ["high", "medium"] and
                decision.city_name.strip()):  # 빈 문자열 체크
                
                ctx.session.state["target_city"] = decision.city_name.strip()
                ctx.session.state["city_selection_complete"] = True
                logger.info(f"[{self.name}] ✅ 도시 선택 완료: {decision.city_name}")
                logger.info(f"[{self.name}] ✅ target_city 저장 후 state: {dict(ctx.session.state)}")
                return True
            else:
                logger.info(f"[{self.name}] ❌ 계속 대화 필요: {decision.reason}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.name}] 예상치 못한 오류: {e}")
            return False
    
    async def _provide_city_info(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """선택된 도시의 정보 제공"""
        target_city = ctx.session.state.get("target_city")
        if not target_city:
            yield Event(
                author=self.name,
                content=UserContent(parts=[Part(text="죄송합니다. 도시 선택에 어려움이 있어서 여행 계획을 완료할 수 없습니다.")])
            )
            return
            
        logger.info(f"[{self.name}] 🎯 도시 정보 제공을 city_info_agent에게 위임: {target_city}")
        
        # city_info_agent 직접 호출
        async for event in self.city_info_agent.run_async(ctx):
            yield event
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """메인 워크플로우: Resume 지원 + 깔끔한 구조"""
        logger.info(f"[{self.name}] 🚀 여행 계획 라우터 시작")
        logger.info(f"[{self.name}] 🔍 시작시 session state: {dict(ctx.session.state)}")
        
        try:
            # Step 1: 도시 선택 확보 (Resume 체크 포함)
            if self._is_city_already_selected(ctx):
                existing_city = ctx.session.state.get("target_city")
                logger.info(f"[{self.name}] ✅ Resume: 기존 도시 사용 - {existing_city}")
            else:
                logger.info(f"[{self.name}] 🆕 새로운 세션: 도시 입력 시작")
                
                # city_input_agent 실행
                async for event in self._ensure_city_selection(ctx):
                    yield event
                
                # target_city로 선택 완료 여부 확인
                logger.info(f"[{self.name}] 🔍 선택 완료 체크 전 state: {dict(ctx.session.state)}")
                if not self._is_city_already_selected(ctx):
                    logger.info(f"[{self.name}] ❌ 도시 선택 미완료, 턴 종료 (continue 상태)")
                    return  # continue 판단시 턴 종료
                else:
                    logger.info(f"[{self.name}] ✅ 도시 선택 완료 확인됨!")
            
            # Step 2: 도시 정보 제공 (도시가 선택된 경우만)
            logger.info(f"[{self.name}] 🎯 도시 정보 제공을 city_info_agent에게 위임")
            async for event in self._provide_city_info(ctx):
                yield event
            
            logger.info(f"[{self.name}] 여행 계획 성공적으로 완료!")
            
        finally:
            # 🎯 ADK 방식: Event를 통한 상태 정리
            async for cleanup_event in self._cleanup_state(ctx):
                yield cleanup_event
            logger.info(f"[{self.name}] 상태 정리 완료, 다음번 새로운 도시 선택 가능")
