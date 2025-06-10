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
from google.adk.events import Event
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
    model_name="gemini-2.5-pro-preview-05-06"
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
    
    # 상태 정리 대상 키들 정의 (클래스 변수)
    STATE_KEYS_TO_CLEANUP: ClassVar[list[str]] = [
        "target_city",
        "city_selection_complete",
        "city_input_agent_output",
        "city_info"
    ]
    
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
                    
                    # 전체 JSON을 state에 저장 (파싱용)
                    json_string = json.dumps(decision_data)
                    callback_context.state["city_input_agent_output"] = json_string
                    logger.info(f"[callback] state에 저장 완료, 타입: {type(json_string)}")
                    logger.info(f"[callback] 저장된 데이터: {json_string}")
                    
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
            model=gemini,
            description="유저와 대화하며 여행 도시를 선택하는 에이전트",
            instruction=(
                "당신은 친근한 여행 상담사입니다.\n"
                "사용자와 자연스럽게 대화하며 여행하고 싶은 도시를 파악하세요.\n\n"
                
                "**중요: 응답은 반드시 다음 JSON 형식으로 시작해야 합니다:**\n"
                "```json\n"
                "{\n"
                '  "decision": "complete" 또는 "continue",\n'
                '  "city_name": "확정된 도시명 (확실하지 않으면 빈 문자열)",\n'
                '  "confidence": "high", "medium", 또는 "low",\n'
                '  "reason": "판단 이유 설명",\n'
                '  "user_message": "사용자에게 보여줄 친근한 메시지"\n'
                "}\n"
                "```\n\n"
                
                "**응답 가이드:**\n"
                "- decision: 사용자가 구체적인 도시를 명확히 언급했으면 'complete', 더 정보가 필요하면 'continue'\n"
                "- city_name: 사용자가 명확히 언급한 도시명 (확실하지 않으면 빈 문자열)\n"
                "- confidence: 도시 선택의 확실성 정도 (high/medium/low)\n"
                "- reason: 판단한 이유를 간단히 설명\n"
                "- user_message: 사용자에게 보여줄 친근하고 도움이 되는 메시지\n\n"
                
                "**user_message 작성 가이드:**\n"
                "- 도시가 확정되면: 그 도시에 대한 긍정적 코멘트와 여행 계획 도움 의사\n"
                "- 더 정보 필요시: 구체적인 선택지나 질문을 제안해서 대화 유도\n"
                "- 항상 친근하고 도움이 되는 톤으로 작성\n\n"
                "- 도시에 대해서 골랐다면, 질문을 더 하지 말고 잘 마무리해줘.\n"
                
                "예시:\n"
                "사용자: '파리로 여행가고 싶어요' → user_message: '파리 정말 좋은 선택이네요! 낭만의 도시 파리는 에펠탑, 루브르 박물관 등 볼거리가 정말 많죠. 파리 여행 계획을 도와드릴게요!'\n"
                "사용자: '유럽 어디로 갈까요?' → user_message: '유럽 여행 정말 좋죠! 어떤 스타일의 여행을 원하세요? 낭만적인 파리, 역사적인 로마, 현대적인 런던 등 다양한 선택지가 있어요. 특별히 관심 있는 활동이나 분위기가 있으신가요?'"
            ),
            # output_schema=CitySelectionDecision,  # 🚫 제거: validation 충돌 방지
            # output_key="city_input_agent_output",  # 🚫 제거: callback과 키 충돌 방지
            after_model_callback=extract_user_message,  # 🎯 JSON에서 user_message만 추출 + state 저장
            disallow_transfer_to_peers=True  # 🚫 Peer transfer 금지
        )
        
        # 도시 정보 제공 에이전트  
        city_info_agent = LlmAgent(
            name="city_info_agent", 
            model=gemini,
            description="선택된 도시에 대한 상세 정보를 제공하는 에이전트",
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
    
    def _cleanup_state(self, ctx: InvocationContext) -> None:
        """여행 계획 관련 상태 정리"""
        removed_keys = []
        for key in self.STATE_KEYS_TO_CLEANUP:
            if ctx.session.state.pop(key, None) is not None:
                removed_keys.append(key)
        
        if removed_keys:
            logger.info(f"[{self.name}] 상태 정리 완료: {removed_keys}")
        else:
            logger.debug(f"[{self.name}] 정리할 상태 없음")
    
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
        logger.info(f"[{self.name}] 여기도달함!!!!")
        self._process_city_decision(ctx)
        
        logger.info(f"[{self.name}] 도시 선택 시도 완료")
    
    def _process_city_decision(self, ctx: InvocationContext) -> bool:
        """LLM의 도시 선택 판단 결과 처리 (output_schema 기반)"""
        logger.info(f"[{self.name}] 현재 session state 전체: {dict(ctx.session.state)}")
        
        agent_response = ctx.session.state.get("city_input_agent_output")
        logger.info(f"[{self.name}] agent_response: {agent_response}")
        logger.info(f"[{self.name}] agent_response 타입: {type(agent_response)}")
        logger.info(f"[{self.name}] agent_response 길이: {len(agent_response) if agent_response else 'None'}")
        
        if not agent_response:
            logger.warning(f"[{self.name}] LLM 응답 없음")
            return False
        
        # agent_response가 이미 dict인지 string인지 확인
        if isinstance(agent_response, dict):
            logger.info(f"[{self.name}] agent_response는 이미 dict 형태: {agent_response}")
            decision_data = agent_response
        elif isinstance(agent_response, str):
            logger.info(f"[{self.name}] agent_response는 string, JSON 파싱 시도")
            try:
                # output_schema로 생성된 JSON 직접 파싱
                import json
                decision_data = json.loads(agent_response)
                logger.info(f"[{self.name}] 파싱된 decision_data: {decision_data}")
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.error(f"[{self.name}] JSON 파싱 실패: {e}")
                logger.error(f"[{self.name}] 파싱 실패한 원본 데이터: '{agent_response}'")
                return False
        else:
            logger.error(f"[{self.name}] 예상치 못한 agent_response 타입: {type(agent_response)}")
            return False
            
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
            async for event in self._provide_city_info(ctx):
                yield event
            
            logger.info(f"[{self.name}] 여행 계획 성공적으로 완료!")
            
        finally:
            # 성공/실패 상관없이 상태 정리
            self._cleanup_state(ctx)
            logger.info(f"[{self.name}] 상태 정리 완료, 다음번 새로운 도시 선택 가능")
