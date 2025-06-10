"""scenario/utils.py — 시나리오 시스템 유틸리티
=============================================

JSON 처리, 상태 판단 등 공통 유틸리티 함수들
"""

import json
import re
import logging
from typing import Optional, Dict, Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai.types import Content, Part

from .types import ComponentStatus

logger = logging.getLogger(__name__)

# ---------- JSON Processing -----------------------------

class JSONProcessor:
    """JSON 후처리 유틸리티"""
    
    @staticmethod
    def extract_json_from_response(response_text: str) -> Optional[Dict[str, Any]]:
        """응답 텍스트에서 JSON 추출"""
        try:
            # ```json 블록 찾기
            json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # JSON 블록이 없으면 전체 텍스트 사용
                json_text = response_text
            
            return json.loads(json_text)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"JSON 파싱 실패: {e}")
            return None
    
    @staticmethod
    def extract_user_message(data: Dict[str, Any]) -> str:
        """JSON 데이터에서 user_message 추출"""
        return data.get("user_message", "")

# ---------- Callback Factory -----------------------------

def create_json_callback(component_name: str):
    """JSON 후처리 콜백 생성 팩토리"""
    
    def extract_user_message_callback(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
        """JSON에서 user_message만 추출하고 전체 JSON은 state에 저장"""
        logger.debug(f"[{component_name}] JSON 후처리 콜백 시작")
        
        if not llm_response.content or not llm_response.content.parts or not llm_response.content.parts[0].text:
            logger.warning(f"[{component_name}] LLM 응답이 비어있음")
            return None
        
        response_text = llm_response.content.parts[0].text
        
        # JSON 추출
        component_output = JSONProcessor.extract_json_from_response(response_text)
        if component_output is None:
            logger.warning(f"[{component_name}] JSON 파싱 실패, 원본 사용")
            return None
        
        logger.debug(f"[{component_name}] JSON 파싱 성공: {component_output}")
        
        # state에 컴포넌트 출력 저장
        callback_context.state[f"{component_name}_output"] = component_output
        
        # user_message만 추출해서 유저에게 보여주기
        user_message = JSONProcessor.extract_user_message(component_output)
        logger.debug(f"[{component_name}] 추출된 user_message: {user_message}")
        
        if user_message:
            new_content = Content(
                role="model",
                parts=[Part(text=user_message)]
            )
            return LlmResponse(content=new_content)
        
        return None
    
    return extract_user_message_callback

# ---------- Status Utilities -----------------------------

class StatusHelper:
    """컴포넌트 상태 관련 헬퍼 함수들"""
    
    @staticmethod
    def from_decision(decision: str) -> ComponentStatus:
        """decision 필드 기반 상태 변환"""
        decision_map = {
            "complete": ComponentStatus.COMPLETED,
            "continue": ComponentStatus.RUNNING,
            "failed": ComponentStatus.FAILED
        }
        return decision_map.get(decision, ComponentStatus.COMPLETED)
    
    @staticmethod
    def is_terminal(status: ComponentStatus) -> bool:
        """종료 상태인지 확인"""
        return status in [ComponentStatus.COMPLETED, ComponentStatus.FAILED]
    
    @staticmethod
    def needs_continuation(status: ComponentStatus) -> bool:
        """계속 실행이 필요한지 확인"""
        return status == ComponentStatus.RUNNING 
