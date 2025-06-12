"""travel_planner_v2.py — 시나리오 시스템을 활용한 여행 계획 에이전트
=======================================================================

기존 TravelPlannerAgent를 새로운 시나리오 시스템으로 리팩토링한 버전
- ScenarioComponentAgent 기반 컴포넌트들
- 자동 JSON 후처리 및 라우팅
- 깔끔한 상태 관리 및 Resume 지원
"""

import os
import logging
from typing import Literal
from pydantic import BaseModel

from google.adk.models import Gemini

from .scenario import (
    ScenarioAgent, ScenarioComponentAgent, Scenario, ScenarioComponent,
    RoutingCondition, RoutingUtils
)

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

# ---------- Pydantic Schema (기존과 동일) -----------------------------
class CitySelectionDecision(BaseModel):
    """도시 선택 판단 결과 스키마"""
    decision: Literal["complete", "continue"]
    city_name: str = ""
    confidence: Literal["high", "medium", "low"] = "low"
    reason: str = ""
    user_message: str = ""

# ---------- Component Definitions -----------------------------

class CityInputComponent(ScenarioComponentAgent):
    """도시 입력 전담 컴포넌트"""
    
    def __init__(self):
        super().__init__(
            name="city_input_agent",  # 기존 이름 유지 (state key 호환성)
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
                "- 유저가 넓은 범주를 말한 경우, 고르기 쉽게 예시 제시\n"
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
            )
        )

class CityInfoComponent(ScenarioComponentAgent):
    """도시 정보 제공 전담 컴포넌트"""
    
    def __init__(self):
        super().__init__(
            name="city_info_agent",  # 기존 이름 유지 (state key 호환성)
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
                
                "**출력 형식:**\n"
                "일반 텍스트로 상세한 여행 정보를 작성하세요. JSON이 아닌 자연스러운 설명 형태로 작성하세요.\n\n"
                
                "**좋은 예시 시작:**\n"
                "'가고시마는 일본 규슈 남부에 위치한 화산과 온천의 도시입니다. 🌋'\n\n"
                
                "**나쁜 예시 (금지!):**\n"
                "'가고시마 여행 정보를 준비해드리겠습니다!'\n"
                "'정보를 정리해서 알려드릴게요!'\n\n"
                
                "🎯 **핵심: 예고 없이 바로 상세 정보 제공!**"
            )
        )

# ---------- Scenario Factory -----------------------------

def create_travel_planner_scenario() -> Scenario:
    """여행 계획 시나리오 생성 (기존 2단계 구조 유지)"""
    
    # 컴포넌트 인스턴스 생성
    city_input = CityInputComponent()
    city_info = CityInfoComponent()
    
    # 시나리오 컴포넌트 정의
    city_input_comp = ScenarioComponent(
        id="city_input",
        agent=city_input,
        routing_conditions=[
            # complete 판단시 도시 정보 제공으로 이동
            RoutingCondition(
                target_component="city_info",
                condition=RoutingUtils.create_simple_condition("complete")
            )
            # continue 조건 제거: RUNNING 상태시 시나리오 자동 중단됨
        ]
    )
    
    city_info_comp = ScenarioComponent(
        id="city_info",
        agent=city_info,
        routing_conditions=[]  # 종료 컴포넌트
    )
    
    # 시나리오 구성
    scenario = Scenario(
        name="travel_planning_v2",
        entry_component="city_input",
        components=[city_input_comp, city_info_comp]
    )
    
    return scenario

def create_travel_planner_agent() -> ScenarioAgent:
    """리팩토링된 여행 계획 에이전트 생성"""
    scenario = create_travel_planner_scenario()
    
    return ScenarioAgent(scenario=scenario)

# ---------- 편의 함수 (기존 API 호환성) -----------------------------

def create_travel_planner() -> ScenarioAgent:
    """기존 API와 호환성을 위한 별칭"""
    return create_travel_planner_agent()

# ---------- 테스트 실행 -----------------------------

if __name__ == "__main__":
    print("🚀 리팩토링된 여행 계획 에이전트 테스트!")
    
    # 에이전트 생성
    agent = create_travel_planner_agent()
    
    print(f"✅ 에이전트 생성 성공: {agent.name}")
    print(f"📋 시나리오: {agent.scenario.name}")
    print(f"🧩 컴포넌트 수: {len(agent.components_by_id)}")
    print(f"🎯 진입점: {agent.scenario.entry_component}")
    
    print("\n📦 컴포넌트 목록:")
    for comp_id, component in agent.components_by_id.items():
        print(f"  - {comp_id}: {component.agent.description}")
        if component.routing_conditions:
            print(f"    라우팅 조건: {len(component.routing_conditions)}개")
    
    print("\n🎉 리팩토링 완료! 이제 InMemoryRunner로 실행하면 됩니다!") 
