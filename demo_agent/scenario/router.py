"""scenario/router.py — 시나리오 라우팅 로직
=============================================

컴포넌트 간 라우팅과 흐름 제어 로직
"""

import logging
from typing import Optional, Dict, List, Any

from google.adk.agents.invocation_context import InvocationContext

from .types import ScenarioComponent, ComponentResult, ComponentStatus

logger = logging.getLogger(__name__)

# ---------- Routing Engine -----------------------------

class ComponentRouter:
    """컴포넌트 라우팅 엔진"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        
    def route_to_next_component(
        self, 
        component: ScenarioComponent, 
        result: ComponentResult, 
        ctx: InvocationContext,
        components_by_id: Dict[str, ScenarioComponent]
    ) -> Optional[str]:
        """다음 컴포넌트 라우팅"""
        logger.info(f"[{self.agent_name}] 🧭 라우팅 시작: {component.id}")
        
        # 1. 라우팅 조건 확인 (우선순위)
        next_component = self._check_routing_conditions(component, result, ctx)
        if next_component:
            return next_component
        
        # 2. 기본 다음 컴포넌트
        next_component = self._get_default_next_component(component)
        if next_component:
            return next_component
        
        # 3. 더 이상 실행할 컴포넌트 없음
        logger.info(f"[{self.agent_name}] 🏁 시나리오 종료 - 더 이상 실행할 컴포넌트 없음")
        return None
    
    def _check_routing_conditions(
        self, 
        component: ScenarioComponent, 
        result: ComponentResult, 
        ctx: InvocationContext
    ) -> Optional[str]:
        """라우팅 조건 확인"""
        for routing_condition in component.routing_conditions:
            try:
                if routing_condition.condition(result, ctx):
                    logger.info(f"[{self.agent_name}] ✅ 라우팅 조건 매치: {routing_condition.target_component}")
                    return routing_condition.target_component
            except Exception as e:
                logger.warning(f"[{self.agent_name}] ⚠️ 라우팅 조건 평가 실패: {e}")
                continue
        
        return None
    
    def _get_default_next_component(self, component: ScenarioComponent) -> Optional[str]:
        """기본 다음 컴포넌트 가져오기"""
        if component.next_components:
            next_component = component.next_components[0]  # 첫 번째 기본 컴포넌트
            logger.info(f"[{self.agent_name}] 📋 기본 다음 컴포넌트: {next_component}")
            return next_component
        
        return None

# ---------- Flow Control -----------------------------

class FlowController:
    """시나리오 흐름 제어"""
    
    @staticmethod
    def should_continue_current_component(status: ComponentStatus) -> bool:
        """현재 컴포넌트를 계속 실행해야 하는지 판단"""
        return status == ComponentStatus.RUNNING
    
    @staticmethod
    def should_proceed_to_next(status: ComponentStatus) -> bool:
        """다음 컴포넌트로 진행해야 하는지 판단"""
        return status == ComponentStatus.COMPLETED
    
    @staticmethod
    def should_handle_failure(status: ComponentStatus) -> bool:
        """실패 처리가 필요한지 판단"""
        return status == ComponentStatus.FAILED
    
    @staticmethod
    def should_terminate(status: ComponentStatus) -> bool:
        """시나리오를 종료해야 하는지 판단"""
        return status in [ComponentStatus.FAILED]

# ---------- Component Validator -----------------------------

class ComponentValidator:
    """컴포넌트 유효성 검증"""
    
    @staticmethod
    def validate_component_exists(component_id: str, components_by_id: Dict[str, ScenarioComponent]) -> bool:
        """컴포넌트 존재 여부 확인"""
        exists = component_id in components_by_id
        if not exists:
            logger.error(f"컴포넌트 '{component_id}'를 찾을 수 없음")
        return exists
    
    @staticmethod
    def validate_routing_conditions(component: ScenarioComponent, components_by_id: Dict[str, ScenarioComponent]) -> List[str]:
        """라우팅 조건의 대상 컴포넌트들이 존재하는지 확인"""
        missing_components = []
        
        for condition in component.routing_conditions:
            if not ComponentValidator.validate_component_exists(condition.target_component, components_by_id):
                missing_components.append(condition.target_component)
        
        for next_comp in component.next_components:
            if not ComponentValidator.validate_component_exists(next_comp, components_by_id):
                missing_components.append(next_comp)
        
        return missing_components

# ---------- Routing Utilities -----------------------------

class RoutingUtils:
    """라우팅 유틸리티 함수들"""
    
    @staticmethod
    def create_simple_condition(expected_decision: str):
        """간단한 decision 기반 라우팅 조건 생성"""
        def condition(result: ComponentResult, ctx: InvocationContext) -> bool:
            return result.context_updates.get("decision") == expected_decision
        return condition
    
    @staticmethod
    def create_field_match_condition(field_name: str, expected_value: Any):
        """특정 필드 값 매칭 조건 생성"""
        def condition(result: ComponentResult, ctx: InvocationContext) -> bool:
            return result.context_updates.get(field_name) == expected_value
        return condition
    
    @staticmethod
    def create_context_condition(context_key: str, expected_value: Any):
        """컨텍스트 기반 조건 생성"""
        def condition(result: ComponentResult, ctx: InvocationContext) -> bool:
            return ctx.session.state.get(context_key) == expected_value
        return condition 
