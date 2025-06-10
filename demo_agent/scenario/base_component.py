"""scenario/base_component.py — ScenarioComponentAgent 베이스 클래스
================================================================

시나리오 컴포넌트의 베이스 클래스만 정의
"""

import logging
from typing import Dict, Any

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import InvocationContext

from .types import ComponentResult, ComponentStatus
from .utils import JSONProcessor, create_json_callback

logger = logging.getLogger(__name__)

# ---------- Base Component Agent -----------------------------

class ScenarioComponentAgent(LlmAgent):
    """시나리오 컴포넌트의 베이스 클래스"""
    
    def __init__(self, name: str, model, description: str, instruction: str, **kwargs):
        # JSON 후처리 콜백 생성 (utils의 팩토리 함수 사용)
        json_callback = create_json_callback(name)
        
        # LlmAgent 초기화
        super().__init__(
            name=name,
            model=model,
            description=description,
            instruction=instruction,
            after_model_callback=json_callback,
            disallow_transfer_to_peers=True,
            **kwargs
        )
    
    def create_component_result(self, ctx: InvocationContext) -> ComponentResult:
        """컴포넌트 실행 후 결과 생성"""
        logger.info(f"[{self.name}] ComponentResult 생성 시작")
        
        # JSON 결과 가져오기
        component_output = ctx.session.state.get(f"{self.name}_output", {})
        logger.debug(f"[{self.name}] 컴포넌트 출력: {component_output}")
        
        # 상태 판단
        status = self._determine_status(component_output, ctx)
        
        # ComponentResult 생성
        result = ComponentResult(
            status=status,
            user_message="",  # 이미 이벤트로 전달됨
            context_updates=component_output,
            next_component_hints=component_output.get("routing_hints", {})
        )
        
        logger.debug(f"[{self.name}] ComponentResult: {result}")
        return result
    
    def _determine_status(self, component_output: Dict[str, Any], ctx: InvocationContext) -> ComponentStatus:
        """컴포넌트 출력에서 상태 판단 (오버라이드 가능)"""
        # 기본 구현: decision 필드 기반 판단
        decision = component_output.get("decision", "")
        
        if decision == "complete":
            return ComponentStatus.COMPLETED
        elif decision == "continue":
            return ComponentStatus.RUNNING
        elif decision == "failed":
            return ComponentStatus.FAILED
        else:
            # 기본적으로 완료로 간주
            return ComponentStatus.COMPLETED 
