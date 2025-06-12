"""scenario/types.py — 시나리오 시스템 기본 타입 정의
====================================================

시나리오 시스템에서 사용하는 모든 기본 데이터 타입과 구조체
"""

from __future__ import annotations

from typing import Dict, Any, Callable, List, Optional
from enum import Enum
from pydantic import BaseModel

from google.adk.agents.invocation_context import InvocationContext

# ---------- Enums -----------------------------

class ComponentStatus(Enum):
    """컴포넌트 실행 상태"""
    PENDING = "pending"      # 아직 실행 안됨
    RUNNING = "running"      # 실행 중 (유저 인터렉션 필요)
    COMPLETED = "completed"  # 성공 완료
    FAILED = "failed"        # 실패

# ---------- Core Data Models -----------------------------

class ComponentResult(BaseModel):
    """컴포넌트 실행 결과"""
    status: ComponentStatus
    user_message: str = ""                    # 유저에게 보여줄 메시지 (후처리된)
    context_updates: Dict[str, Any] = {}      # Context에 업데이트할 데이터
    next_component_hints: Dict[str, Any] = {} # 다음 컴포넌트 결정용 힌트

class RoutingCondition(BaseModel):
    """라우팅 조건 정의"""
    target_component: str  # 다음에 실행할 컴포넌트 ID
    condition: Callable[[ComponentResult, InvocationContext], bool]
    
    class Config:
        arbitrary_types_allowed = True

# ---------- Forward Declarations -----------------------------

# ScenarioComponentAgent는 component.py에서 정의됨
# 순환 import를 피하기 위해 TYPE_CHECKING 사용
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from .base_component import ScenarioComponentAgent

class ScenarioComponent(BaseModel):
    """시나리오 컴포넌트 정의"""
    id: str                                        # 컴포넌트 식별자
    agent: Any                                     # 실제 실행 에이전트 (Runtime 검증)
    next_components: List[str] = []                # 기본 다음 컴포넌트들
    routing_conditions: List[RoutingCondition] = [] # 동적 라우팅 조건들
    parallel_group: Optional[str] = None           # 병렬 실행 그룹 (미래 확장용)
    
    class Config:
        arbitrary_types_allowed = True

class Scenario(BaseModel):
    """시나리오 정의"""
    name: str
    components: List[ScenarioComponent]
    entry_component: str                           # 시작 컴포넌트 ID
    failure_component: Optional[ScenarioComponent] = None  # 실패시 실행될 컴포넌트
    
    class Config:
        arbitrary_types_allowed = True

# ---------- State Management Types -----------------------------

class ScenarioState(BaseModel):
    """시나리오 실행 상태"""
    scenario_name: str
    current_component: str
    component_status: Dict[str, str] = {}  # component_id -> status

class ComponentData(BaseModel):
    """컴포넌트별 데이터"""
    component_id: str
    data: Dict[str, Any] = {} 
