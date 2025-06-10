"""scenario — 시나리오 기반 에이전트 시스템
==========================================

여러 서브 에이전트들을 순서대로 실행하는 시나리오 시스템

## 주요 구성 요소
- ScenarioAgent: 메인 시나리오 실행 엔진
- ScenarioComponentAgent: 개별 컴포넌트 베이스 클래스
- Scenario, ScenarioComponent: 시나리오 정의 구조
- ComponentResult, ComponentStatus: 실행 결과 타입들

## 사용 예시
```python
from scenario import (
    ScenarioAgent, ScenarioComponentAgent, Scenario, ScenarioComponent,
    RoutingCondition, ComponentStatus
)

# 1. 컴포넌트 정의
class MyComponent(ScenarioComponentAgent):
    def __init__(self):
        super().__init__(
            name="my_component",
            model=your_model,
            description="내 컴포넌트",
            instruction="JSON 형식으로 응답하세요..."
        )

# 2. 시나리오 구성
scenario = Scenario(
    name="my_scenario",
    entry_component="comp1",
    components=[
        ScenarioComponent(id="comp1", agent=MyComponent()),
        # ... 더 많은 컴포넌트들
    ]
)

# 3. 실행
agent = ScenarioAgent(scenario)
# runner.run_async(agent) 등으로 실행
```
"""

# 핵심 클래스들
from .agent import ScenarioAgent
from .base_component import ScenarioComponentAgent

# 타입 정의들
from .types import (
    ComponentStatus,
    ComponentResult,
    RoutingCondition,
    ScenarioComponent,
    Scenario,
    ScenarioState,
    ComponentData
)

# 유틸리티들
from .router import (
    ComponentRouter,
    FlowController,
    ComponentValidator,
    RoutingUtils
)

from .state_manager import (
    ScenarioStateManager,
    ContextManager,
    StateCleanupManager
)

from .utils import (
    JSONProcessor,
    StatusHelper,
    create_json_callback
)

# 하위 호환성
StatusDeterminer = StatusHelper

# 버전 정보
__version__ = "1.0.0"

# 외부에 노출할 주요 인터페이스
__all__ = [
    # 핵심 클래스
    "ScenarioAgent",
    "ScenarioComponentAgent",
    
    # 타입 정의
    "ComponentStatus",
    "ComponentResult", 
    "RoutingCondition",
    "ScenarioComponent",
    "Scenario",
    "ScenarioState",
    "ComponentData",
    
    # 라우팅 유틸리티
    "RoutingUtils",
    
    # 상태 관리 (고급 사용)
    "ScenarioStateManager",
    "ContextManager",
    
    # JSON 처리 (고급 사용)
    "JSONProcessor",
    "StatusDeterminer",
] 
