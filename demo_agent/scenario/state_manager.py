"""scenario/state_manager.py — 시나리오 상태 관리 유틸리티
============================================================

시나리오 실행 상태를 관리하는 유틸리티 클래스들
"""

import logging
from typing import Dict, Any, Optional, List

from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from .types import ScenarioState, ComponentData, ComponentResult, ComponentStatus

logger = logging.getLogger(__name__)

# ---------- State Management -----------------------------

class ScenarioStateManager:
    """시나리오 상태 관리자"""
    
    def __init__(self, scenario_name: str):
        self.scenario_name = scenario_name
    
    async def _apply_state_delta(self, ctx: InvocationContext, state_updates: dict):
        """내부 헬퍼: state 변경을 즉시 Event로 적용"""
        if not state_updates:
            return
            
        logger.debug(f"[{self.scenario_name}] 🔄 즉시 state 적용: {list(state_updates.keys())}")
        
        yield Event(
            author=f"state_manager_{self.scenario_name}",
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta=state_updates),
            content=None
        )
    
    async def restore_state(self, ctx: InvocationContext, entry_component: str):
        """시나리오 상태 복원 (Resume 지원)"""
        scenario_state = ctx.session.state.get("scenario_state")
        
        # scenario_state가 None이거나 빈 딕셔너리인 경우 새로운 시나리오 시작
        if not scenario_state or not scenario_state.get("scenario_name"):
            async for event in self._create_new_scenario_state(ctx, entry_component):
                yield event
            return  # async generator에서는 값 없이 return
        
        # 같은 시나리오이고 현재 컴포넌트가 있는 경우 Resume
        if scenario_state.get("scenario_name") == self.scenario_name:
            current_component = scenario_state.get("current_component")
            if current_component:
                logger.info(f"[{self.scenario_name}] 🔄 Resume: 기존 컴포넌트 계속 - {current_component}")
                return  # async generator에서는 값 없이 return
        
        # 다른 시나리오이거나 컴포넌트 정보가 없는 경우 새로운 시나리오 시작
        async for event in self._create_new_scenario_state(ctx, entry_component):
            yield event
    
    async def _create_new_scenario_state(self, ctx: InvocationContext, entry_component: str):
        """새로운 시나리오 상태 생성 (즉시 적용)"""
        logger.info(f"[{self.scenario_name}] 🆕 새로운 시나리오 시작")
        
        # ✅ 즉시 적용
        new_state = {
            "scenario_name": self.scenario_name,
            "current_component": entry_component,
            "component_status": {}
        }
        
        async for event in self._apply_state_delta(ctx, {"scenario_state": new_state}):
            yield event
    
    async def update_component_status(self, ctx: InvocationContext, component_id: str, status: ComponentStatus):
        """컴포넌트 상태 업데이트 (즉시 적용)"""
        # 현재 scenario_state 가져오기
        current_state = self._get_current_scenario_state(ctx)
        current_state["component_status"] = current_state.get("component_status", {})
        current_state["component_status"][component_id] = status.value
        
        # ✅ 즉시 적용
        async for event in self._apply_state_delta(ctx, {"scenario_state": current_state}):
            yield event
        
        logger.debug(f"[{self.scenario_name}] 컴포넌트 상태 업데이트: {component_id} -> {status.value}")
    
    async def update_current_component(self, ctx: InvocationContext, component_id: str):
        """현재 컴포넌트 업데이트 (즉시 적용)"""
        # 현재 scenario_state 가져오기
        current_state = self._get_current_scenario_state(ctx)
        current_state["current_component"] = component_id
        
        # ✅ 즉시 적용
        async for event in self._apply_state_delta(ctx, {"scenario_state": current_state}):
            yield event
        
        logger.debug(f"[{self.scenario_name}] 현재 컴포넌트 업데이트: {component_id}")
    
    def _get_current_scenario_state(self, ctx: InvocationContext) -> dict:
        """현재 scenario_state 가져오기"""
        return ctx.session.state.get("scenario_state", {}).copy() if ctx.session.state.get("scenario_state") else {}
    
    def get_component_status(self, ctx: InvocationContext, component_id: str) -> Optional[ComponentStatus]:
        """컴포넌트 상태 조회"""
        scenario_state = ctx.session.state.get("scenario_state", {})
        status_str = scenario_state.get("component_status", {}).get(component_id)
        
        if status_str:
            try:
                return ComponentStatus(status_str)
            except ValueError:
                logger.warning(f"[{self.scenario_name}] 잘못된 상태 값: {status_str}")
        
        return None
    
    async def set_scenario_completed(self, ctx: InvocationContext, completed: bool, reason: str = ""):
        """시나리오 완료 상태 설정 (즉시 적용)"""
        # 현재 scenario_state 가져오기
        current_state = self._get_current_scenario_state(ctx)
        current_state["completed"] = completed
        current_state["completion_reason"] = reason
        
        # ✅ 즉시 적용
        async for event in self._apply_state_delta(ctx, {"scenario_state": current_state}):
            yield event
        
        logger.info(f"[{self.scenario_name}] 시나리오 완료 상태 설정: {completed} (이유: {reason})")
    
    def is_scenario_completed(self, ctx: InvocationContext) -> bool:
        """시나리오 완료 상태 확인"""
        current_state = self._get_current_scenario_state(ctx)
        return current_state.get("completed", False)
    
    def get_current_component_id(self, ctx: InvocationContext, default_entry: str) -> str:
        """현재 컴포넌트 ID 가져오기"""
        scenario_state = ctx.session.state.get("scenario_state", {})
        return scenario_state.get("current_component", default_entry)
    


# ---------- Context Management -----------------------------

class ContextManager:
    """컨텍스트 데이터 관리자"""
    
    def __init__(self, state_manager: ScenarioStateManager):
        self.state_manager = state_manager
    
    async def update_context(self, ctx: InvocationContext, component_id: str, result: ComponentResult):
        """컨텍스트 업데이트 (즉시 적용)"""
        # ✅ ADK Delta 방식: component_data 업데이트
        current_component_data = ctx.session.state.get("component_data", {}).copy() if ctx.session.state.get("component_data") else {}
        current_component_data[component_id] = result.context_updates
        
        # 상태 업데이트 준비
        state_updates = {"component_data": current_component_data}
        
        # ✅ ADK Delta 방식: 글로벌 컨텍스트도 추가
        for key, value in result.context_updates.items():
            state_updates[key] = value
        
        # 즉시 적용
        async for event in self.state_manager._apply_state_delta(ctx, state_updates):
            yield event
        
        logger.debug(f"컨텍스트 업데이트 완료: {component_id}")
    
    @staticmethod
    def get_component_data(ctx: InvocationContext, component_id: str) -> Dict[str, Any]:
        """컴포넌트 데이터 조회"""
        component_data = ctx.session.state.get("component_data", {})
        return component_data.get(component_id, {})
    
    @staticmethod
    def get_global_data(ctx: InvocationContext, key: str, default=None):
        """글로벌 데이터 조회"""
        return ctx.session.state.get(key, default)

# ---------- State Cleanup -----------------------------

class StateCleanupManager:
    """상태 정리 관리자"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
    
    async def cleanup_scenario_state(self, ctx: InvocationContext, invocation_id: str):
        """시나리오 상태 정리"""
        cleanup_keys = [
            "scenario_state",
            "component_data"
        ]
        
        state_deltas = {}
        keys_to_remove = []
        
        for key in cleanup_keys:
            if key in ctx.session.state:
                keys_to_remove.append(key)
                state_deltas[key] = None  # 삭제
        
        if state_deltas:
            logger.info(f"[{self.agent_name}] 🧹 시나리오 상태 정리: {keys_to_remove}")
            cleanup_actions = EventActions(state_delta=state_deltas)
            
            yield Event(
                author=self.agent_name,
                invocation_id=invocation_id,
                actions=cleanup_actions,
                content=None
            )
            
            logger.info(f"[{self.agent_name}] ✅ 상태 정리 완료")
    
    async def cleanup_component_outputs(self, ctx: InvocationContext, invocation_id: str, component_names: List[str]):
        """컴포넌트 출력 정리"""
        state_deltas = {}
        
        for component_name in component_names:
            output_key = f"{component_name}_output"
            if output_key in ctx.session.state:
                state_deltas[output_key] = None
        
        if state_deltas:
            logger.info(f"[{self.agent_name}] 🧹 컴포넌트 출력 정리")
            cleanup_actions = EventActions(state_delta=state_deltas)
            
            yield Event(
                author=self.agent_name,
                invocation_id=invocation_id,
                actions=cleanup_actions,
                content=None
            ) 
