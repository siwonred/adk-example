"""scenario/agent.py — 메인 ScenarioAgent 클래스
================================================

시나리오 기반 에이전트 시스템의 핵심 실행 엔진
"""

import logging
from typing import AsyncGenerator, Dict

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from .types import Scenario, ScenarioComponent, ComponentStatus
from .state_manager import ScenarioStateManager, ContextManager, StateCleanupManager
from .router import ComponentRouter, FlowController, ComponentValidator

logger = logging.getLogger(__name__)

# ---------- Main Scenario Agent -----------------------------

class ScenarioAgent(BaseAgent):
    """시나리오 기반 에이전트 시스템"""
    
    # Pydantic 필드 선언
    scenario: Scenario
    components_by_id: Dict[str, ScenarioComponent]
    state_manager: ScenarioStateManager
    context_manager: ContextManager
    router: ComponentRouter
    flow_controller: FlowController
    cleanup_manager: StateCleanupManager
    
    # Pydantic 설정
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self, scenario: Scenario):
        # 유효성 검증
        self._validate_scenario(scenario)
        
        # sub_agents 리스트 생성
        sub_agents = [comp.agent for comp in scenario.components]
        if scenario.failure_component:
            sub_agents.append(scenario.failure_component.agent)
        
        # 관리자 객체들 생성
        agent_name = f"scenario_agent_{scenario.name}"
        state_manager = ScenarioStateManager(scenario.name)
        context_manager = ContextManager(state_manager)  # state_manager 전달
        router = ComponentRouter(agent_name)
        flow_controller = FlowController()
        cleanup_manager = StateCleanupManager(agent_name)
        
        # BaseAgent 초기화 (Pydantic 방식)
        super().__init__(
            name=agent_name,
            description=f"시나리오 기반 에이전트: {scenario.name}",
            sub_agents=sub_agents,
            scenario=scenario,
            components_by_id={comp.id: comp for comp in scenario.components},
            state_manager=state_manager,
            context_manager=context_manager,
            router=router,
            flow_controller=flow_controller,
            cleanup_manager=cleanup_manager
        )
    
    def _validate_scenario(self, scenario: Scenario):
        """시나리오 유효성 검증"""
        components_by_id = {comp.id: comp for comp in scenario.components}
        
        # 진입점 컴포넌트 존재 확인
        if not ComponentValidator.validate_component_exists(scenario.entry_component, components_by_id):
            raise ValueError(f"진입점 컴포넌트 '{scenario.entry_component}'를 찾을 수 없습니다")
        
        # 각 컴포넌트의 라우팅 조건 검증
        for component in scenario.components:
            missing = ComponentValidator.validate_routing_conditions(component, components_by_id)
            if missing:
                logger.warning(f"컴포넌트 '{component.id}'에서 존재하지 않는 대상 컴포넌트들: {missing}")
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """메인 시나리오 실행 워크플로우"""
        logger.info(f"[{self.name}] 🚀 시나리오 '{self.scenario.name}' 시작")
        logger.debug(f"[{self.name}] 시작시 session state: {dict(ctx.session.state)}")
        
        try:
            # Step 1: Resume 상태 복원
            async for event in self.state_manager.restore_state(ctx, self.scenario.entry_component):
                yield event
            
            # 복원 후 현재 컴포넌트 ID 가져오기
            current_component_id = self.state_manager.get_current_component_id(ctx, self.scenario.entry_component)
            
            # Step 2: 시나리오 실행 루프
            async for event in self._execute_scenario_loop(ctx, current_component_id):
                yield event
            
            # Step 3: state에서 완료 여부 확인하여 정리
            if self.state_manager.is_scenario_completed(ctx):
                logger.info(f"[{self.name}] ✅ 시나리오 완전 완료, 상태 정리 시작")
                async for cleanup_event in self.cleanup_manager.cleanup_scenario_state(ctx, ctx.invocation_id):
                    yield cleanup_event
            else:
                logger.info(f"[{self.name}] 📋 시나리오 일시중단 (유저 입력 대기)")
            
        except Exception as e:
            logger.error(f"[{self.name}] 💥 시나리오 실행 중 오류: {e}")
            # 실패 컴포넌트 실행
            async for event in self._handle_scenario_failure(ctx):
                yield event
            # 실패 시에는 상태 정리
            async for cleanup_event in self.cleanup_manager.cleanup_scenario_state(ctx, ctx.invocation_id):
                yield cleanup_event
            raise
    
    async def _execute_scenario_loop(self, ctx: InvocationContext, initial_component_id: str) -> AsyncGenerator[Event, None]:
        """시나리오 실행 루프 - 완료 여부 반환"""
        current_component_id = initial_component_id
        
        while current_component_id:
            logger.info(f"[{self.name}] 🎯 컴포넌트 실행: {current_component_id}")
            
            # 컴포넌트 가져오기 및 검증
            component = self._get_component_safely(current_component_id)
            if not component:
                # 컴포넌트를 찾을 수 없음 → 시나리오 완료
                async for event in self.state_manager.set_scenario_completed(ctx, True, "component_not_found"):
                    yield event
                return
            
            # 컴포넌트 실행
            async for event in self._execute_component(ctx, component):
                yield event
            
            # 실행 결과 처리
            result = component.agent.create_component_result(ctx)
            logger.info(f"[{self.name}] 📊 컴포넌트 결과: {result.status}")
            
            # 상태 및 컨텍스트 업데이트 (즉시 적용)
            async for event in self._update_execution_state(ctx, current_component_id, result):
                yield event
            
            # 다음 액션 결정
            next_action = self._determine_next_action(component, result, ctx)
            
            if next_action == "continue":
                continue  # 같은 컴포넌트 계속
            elif next_action == "next":
                current_component_id = self._get_next_component_id(component, result, ctx)
                if not current_component_id:
                    # 다음 컴포넌트 없음 → 시나리오 완료
                    async for event in self.state_manager.set_scenario_completed(ctx, True, "no_next_component"):
                        yield event
                    return
            elif next_action == "failure":
                async for event in self._handle_component_failure(ctx):
                    yield event
                # 실패 처리 완료 → 시나리오 완료
                async for event in self.state_manager.set_scenario_completed(ctx, True, "failure_handled"):
                    yield event
                return
            else:  # terminate
                # 일시중단 (RUNNING) → 시나리오 일시중단
                async for event in self.state_manager.set_scenario_completed(ctx, False, "user_input_required"):
                    yield event
                logger.info(f"[{self.name}] 📋 시나리오 일시중단 (유저 입력 대기)")
                return
    
    def _get_component_safely(self, component_id: str) -> ScenarioComponent:
        """컴포넌트 안전하게 가져오기"""
        component = self.components_by_id.get(component_id)
        if not component:
            logger.error(f"[{self.name}] ❌ 컴포넌트 '{component_id}' 찾을 수 없음")
        return component
    
    async def _execute_component(self, ctx: InvocationContext, component: ScenarioComponent) -> AsyncGenerator[Event, None]:
        """컴포넌트 실행"""
        async for event in component.agent.run_async(ctx):
            yield event
    
    async def _update_execution_state(self, ctx: InvocationContext, component_id: str, result):
        """실행 상태 업데이트"""
        # 상태 관리자를 통한 업데이트
        async for event in self.state_manager.update_component_status(ctx, component_id, result.status):
            yield event
        
        async for event in self.context_manager.update_context(ctx, component_id, result):
            yield event
        
        # 현재 컴포넌트 업데이트 (RUNNING인 경우만)
        if result.status != ComponentStatus.RUNNING:
            next_component = self._get_next_component_id_preview(component_id, result, ctx)
            if next_component:
                async for event in self.state_manager.update_current_component(ctx, next_component):
                    yield event
    
    def _determine_next_action(self, component: ScenarioComponent, result, ctx: InvocationContext) -> str:
        """다음 액션 결정"""
        if result.status == ComponentStatus.RUNNING:
            logger.info(f"[{self.name}] 📋 컴포넌트가 유저 입력을 기다리고 있음, 시나리오 일시 중단")
            return "terminate"  # ✅ 유저 입력 대기로 시나리오 종료
        elif self.flow_controller.should_handle_failure(result.status):
            return "failure"
        elif self.flow_controller.should_proceed_to_next(result.status):
            return "next"
        else:
            return "terminate"
    
    def _get_next_component_id(self, component: ScenarioComponent, result, ctx: InvocationContext) -> str:
        """다음 컴포넌트 ID 가져오기"""
        return self.router.route_to_next_component(component, result, ctx, self.components_by_id)
    
    def _get_next_component_id_preview(self, component_id: str, result, ctx: InvocationContext) -> str:
        """다음 컴포넌트 ID 미리보기 (상태 업데이트용)"""
        component = self.components_by_id.get(component_id)
        if component:
            return self.router.route_to_next_component(component, result, ctx, self.components_by_id)
        return None
    
    async def _handle_component_failure(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """컴포넌트 실패 처리"""
        if self.scenario.failure_component:
            logger.info(f"[{self.name}] 🆘 실패 컴포넌트 실행")
            async for event in self.scenario.failure_component.agent.run_async(ctx):
                yield event
        else:
            logger.warning(f"[{self.name}] ⚠️ 실패 컴포넌트 없음")
    
    async def _handle_scenario_failure(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """시나리오 전체 실패 처리"""
        logger.error(f"[{self.name}] 💥 시나리오 전체 실패")
        async for event in self._handle_component_failure(ctx):
            yield event 
