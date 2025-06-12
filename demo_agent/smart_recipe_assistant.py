"""smart_recipe_assistant.py — 스마트 레시피 도우미
=======================================================

사용자의 재료를 파악하고 단계별로 요리를 도와주는 시나리오
"""

import os
from .scenario import ScenarioAgent, RoutingUtils
from .scenario.base_component import ScenarioComponentAgent
from .scenario.types import Scenario, ScenarioComponent, ComponentStatus, ComponentResult, RoutingCondition
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models import Gemini

# 공통 모델 설정
gemini = Gemini(
    api_key=os.getenv("GEMINI_API_KEY"),
    model="gemini-2.5-flash-preview-05-20"
)


class IngredientCollectorAgent(ScenarioComponentAgent):
    """재료 수집 및 파악 컴포넌트"""
    
    def __init__(self):
        super().__init__(
            name="ingredient_collector",
            model=gemini,
            description="사용자가 가진 재료를 파악하고 부족한 재료는 대안을 제안합니다",
            instruction="""당신은 요리 재료 전문가입니다.

## 📤 출력 형식
반드시 다음 JSON 형식으로만 응답하세요:

```json
{
  "decision": "complete" | "continue",
  "ingredients": ["확정된 재료들"],
  "user_message": "사용자에게 전달할 메시지"
}
```

## 🔍 판단 기준
### ✅ `decision: "complete"` 조건
- 기본 요리가 가능한 재료들이 있는 경우
- 재료들을 정리하고 레시피 추천으로 진행

### 🔄 `decision: "continue"` 조건  
- 재료가 불충분하거나 더 구체적 확인이 필요한 경우
- 부족한 재료의 대안을 제시하고 사용자 확인 요청

## 📚 예시

**사용자 입력:** "계란이랑 양파 있어요"
```json
{
  "decision": "continue",
  "ingredients": ["계란", "양파"],
  "user_message": "계란과 양파 확인했습니다! 요리용 기름(올리브오일, 버터, 식용유)은 있으신가요? 소금과 후추도 있다면 더 맛있게 만들 수 있어요."
}
```

**사용자 입력:** "네 다 있어요"
```json
{
  "decision": "complete", 
  "ingredients": ["계란", "양파", "기름", "소금", "후추"],
  "user_message": "완벽합니다! 이제 맛있는 요리를 추천해드릴게요."
}
```"""
        )


class RecipeRecommenderAgent(ScenarioComponentAgent):
    """레시피 추천 컴포넌트"""
    
    def __init__(self):
        super().__init__(
            name="recipe_recommender",
            model=gemini, 
            description="재료에 맞는 레시피를 추천하고 요리 경험 수준을 파악합니다",
            instruction="""당신은 레시피 추천 전문가입니다.

## 📤 출력 형식
반드시 다음 JSON 형식으로만 응답하세요:

```json
{
  "decision": "complete",
  "skill_level": "beginner" | "intermediate" | "advanced",
  "recipe": "추천요리명",
  "user_message": "사용자에게 전달할 메시지"
}
```

## 🔍 판단 기준
사용자의 요리 경험 수준을 파악하고 적절한 `skill_level` 설정:
- **`"beginner"`**: 간단하고 실패 확률이 낮은 요리
- **`"intermediate"`**: 약간의 기술이 필요한 요리  
- **`"advanced"`**: 창의적이고 도전적인 요리

## 📚 예시
```json
{
  "decision": "complete",
  "skill_level": "beginner", 
  "recipe": "간단한 계란볶음",
  "user_message": "계란볶음은 어떠세요? 초보자도 쉽게 만들 수 있는 요리입니다!"
}
```"""
        )


class SimpleCookingGuideAgent(ScenarioComponentAgent):
    """간단한 요리 가이드 컴포넌트"""
    
    def __init__(self):
        super().__init__(
            name="simple_cooking_guide",
            model=gemini,
            description="초보자를 위한 단계별 간단한 요리 가이드를 제공합니다",
            instruction="""당신은 친절한 요리 선생님입니다.

초보자를 위해 추천된 요리를 만드는 방법을 아주 상세하고 쉽게 설명해주세요.

## 📤 출력 형식
반드시 다음 JSON 형식으로만 응답하세요:

```json
{
  "decision": "complete",
  "cooking_time": "예상소요시간",
  "difficulty": "쉬움",
  "user_message": "단계별 상세한 요리 가이드 (준비단계, 요리과정, 완성방법, 실패하지 않는 팁 포함)"
}
```

user_message에 다음 내용을 포함해주세요:
1. 준비 단계 (재료 손질, 도구 준비)
2. 요리 과정 (각 단계를 구체적으로)  
3. 완성 및 확인 방법
4. 실패하지 않는 팁들

**중요: JSON 형식만 사용하고, 일반 텍스트와 섞지 마세요!**"""
        )


class DetailedCookingGuideAgent(ScenarioComponentAgent):
    """상세한 요리 가이드 컴포넌트"""
    
    def __init__(self):
        super().__init__(
            name="detailed_cooking_guide",
            model=gemini,
            description="중급자를 위한 상세한 요리 가이드와 기법을 제공합니다",
            instruction="""당신은 전문 요리사입니다.

중급자를 위해 추천된 요리를 만드는 방법을 전문적으로 설명해주세요.

## 📤 출력 형식
반드시 다음 JSON 형식으로만 응답하세요:

```json
{
  "decision": "complete",
  "cooking_time": "예상소요시간", 
  "difficulty": "보통",
  "user_message": "전문적인 요리 가이드 (재료 손질, 화력 조절, 맛의 층, 플레이팅, 프로 팁 포함)"
}
```

user_message에 다음 요소들을 포함해주세요:
1. 재료별 손질 기법과 포인트
2. 화력 조절과 타이밍
3. 맛의 층을 쌓는 방법
4. 플레이팅과 마무리
5. 더 맛있게 만드는 프로 팁들

**중요: JSON 형식만 사용하고, 일반 텍스트와 섞지 마세요!**"""
        )


class AdvancedTipsProviderAgent(ScenarioComponentAgent):
    """고급 팁 제공 컴포넌트"""
    
    def __init__(self):
        super().__init__(
            name="advanced_tips_provider",
            model=gemini,
            description="고급자를 위한 창의적 요리 팁과 변형 레시피를 제공합니다",
            instruction="""당신은 창의적인 셰프입니다.

고급자를 위해 추천된 요리를 기반으로 한 창의적인 변형과 고급 기법을 제안해주세요.

## 📤 출력 형식
반드시 다음 JSON 형식으로만 응답하세요:

```json
{
  "decision": "complete",
  "cooking_time": "예상소요시간",
  "difficulty": "고급", 
  "user_message": "창의적인 고급 요리 가이드 (고급 버전, 변형 아이디어, 전문 기법, 페어링 추천 포함)"
}
```

user_message에 다음 내용들을 포함해주세요:
1. 기본 레시피의 고급 버전
2. 창의적인 변형 아이디어 (퓨전, 플레이팅 등)
3. 전문가 수준의 기법과 팁
4. 와인 페어링이나 사이드 디시 추천
5. 혁신적이고 인상적인 업그레이드 방법

**중요: JSON 형식만 사용하고, 일반 텍스트와 섞지 마세요!**"""
        )


class FinalTipsProviderAgent(ScenarioComponentAgent):
    """마무리 팁 제공 컴포넌트"""
    
    def __init__(self):
        super().__init__(
            name="final_tips_provider",
            model=gemini,
            description="요리 완성 후 마무리 팁과 보관법을 제공합니다",
            instruction="""당신은 생활 요리 전문가입니다.

요리가 완성되었습니다! 🍳

## 📤 출력 형식
반드시 다음 JSON 형식으로만 응답하세요:

```json
{
  "decision": "complete",
  "status": "cooking_completed",
  "user_message": "축하와 격려가 담긴 마무리 팁 (맛있게 먹는 방법, 보관법, 개선 포인트, 응용 메뉴 포함)"
}
```

## 📋 user_message에 반드시 포함할 내용:
1. **🎉 축하 메시지**: 따뜻한 격려와 성취감 표현
2. **🍽️ 맛있게 먹는 방법**: 온도, 곁들일 음식, 플레이팅 팁
3. **📦 보관법과 재가열**: 냉장/냉동 보관 방법, 재가열 팁
4. **📈 개선 포인트**: 다음에 더 맛있게 만드는 방법
5. **🍴 응용 메뉴**: 이 요리를 활용한 다른 요리 제안

## 📚 예시
```json
{
  "decision": "complete",
  "status": "cooking_completed", 
  "user_message": "정말 맛있어 보이는 계란 당근 볶음밥이 완성되었네요! 👏 고슬고슬한 밥알과 알록달록한 재료들이 한눈에 봐도 먹음직스럽네요!🍽️ **맛있게 드세요**: 따뜻할 때 바로 드시고, 김치나 단무지와 함께 드시면 더욱 맛있어요.\\n\\n📦 **보관법**: 완전히 식힌 후 밀폐용기에 냉장보관(2-3일), 냉동보관(1개월) 가능합니다.\\n\\n📈 **다음엔 더 맛있게**: 다진 마늘을 먼저 볶아 향을 내거나, 참기름을 마지막에 둘러주세요.\\n\\n🍴 **응용 메뉴**: 치즈를 올려 치즈볶음밥, 계란지단으로 감싸 오므라이스로 만들어보세요!"
}
```

**중요: JSON 형식만 사용하고, 일반 텍스트와 섞지 마세요!**"""
        )


def create_smart_recipe_assistant_agent():
    """스마트 레시피 도우미 시나리오 에이전트 생성"""
    
    # 컴포넌트들 생성
    ingredient_collector = IngredientCollectorAgent()
    recipe_recommender = RecipeRecommenderAgent() 
    simple_guide = SimpleCookingGuideAgent()
    detailed_guide = DetailedCookingGuideAgent()
    advanced_tips = AdvancedTipsProviderAgent()
    final_tips = FinalTipsProviderAgent()
    
    # 시나리오 구성
    scenario = Scenario(
        name="smart_recipe_assistant",
        description="사용자의 재료로 요리를 추천하고 단계별 가이드를 제공하는 시나리오",
        entry_component="ingredient_collector",
        components=[
            ScenarioComponent(
                id="ingredient_collector",
                agent=ingredient_collector,
                routing_conditions=[
                    RoutingCondition(
                        target_component="recipe_recommender",
                        condition=RoutingUtils.create_simple_condition("complete")
                    )
                    # "continue" 조건은 제거: RUNNING 상태로 자동 턴 종료됨
                ]
            ),
            ScenarioComponent(
                id="recipe_recommender", 
                agent=recipe_recommender,
                routing_conditions=[
                    RoutingCondition(
                        target_component="simple_cooking_guide",
                        condition=RoutingUtils.create_field_match_condition("skill_level", "beginner")
                    ),
                    RoutingCondition(
                        target_component="detailed_cooking_guide",
                        condition=RoutingUtils.create_field_match_condition("skill_level", "intermediate")
                    ),
                    RoutingCondition(
                        target_component="advanced_tips_provider",
                        condition=RoutingUtils.create_field_match_condition("skill_level", "advanced")
                    )
                ]
            ),
            ScenarioComponent(
                id="simple_cooking_guide",
                agent=simple_guide,
                routing_conditions=[
                    RoutingCondition(
                        target_component="final_tips_provider",
                        condition=RoutingUtils.create_simple_condition("complete")
                    )
                ]
            ),
            ScenarioComponent(
                id="detailed_cooking_guide",
                agent=detailed_guide, 
                routing_conditions=[
                    RoutingCondition(
                        target_component="final_tips_provider",
                        condition=RoutingUtils.create_simple_condition("complete")
                    )
                ]
            ),
            ScenarioComponent(
                id="advanced_tips_provider",
                agent=advanced_tips,
                routing_conditions=[
                    RoutingCondition(
                        target_component="final_tips_provider",
                        condition=RoutingUtils.create_simple_condition("complete")
                    )
                ]
            ),
            ScenarioComponent(
                id="final_tips_provider",
                agent=final_tips,
                routing_conditions=[]  # 시나리오 종료
            )
        ]
    )
    
    from .scenario import ScenarioAgent
    return ScenarioAgent(scenario) 
