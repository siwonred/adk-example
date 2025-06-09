"""OrderAgent - 주문 처리 전용 에이전트
=============================================

주문 생성, 조회, 수정, 취소 등의 주문 관련 업무를 처리하는 전문 에이전트
"""

from __future__ import annotations

import os
import logging
from typing import AsyncGenerator, Dict, List, Optional

# ---------- ADK imports -----------------------------
from google.adk.agents import BaseAgent, Agent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.models import Gemini
from typing import AsyncGenerator

# ---------- Local imports -----------------------------
from .data import get_orders, get_order_by_id, create_order
from .cancel_agent import CancelOrderAgent

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

# ---------- OrderAgent Class Implementation -----------------------------

class OrderAgent(LlmAgent):
    """주문 처리 전문 에이전트 클래스"""
    
    # Pydantic 필드 선언
    order_inquiry_agent: LlmAgent
    order_creation_agent: LlmAgent
    cancel_order_agent: CancelOrderAgent
    
    # Pydantic 설정
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self):
        """OrderAgent 초기화"""
        
        # 1. 주문 조회 에이전트
        order_inquiry_agent = LlmAgent(
            name="order_inquiry_agent",
            model=gemini,
            description="주문 조회 및 상태 확인을 담당하는 에이전트",
            instruction=(
                "당신은 주문 조회 전문가입니다. "
                "사용자의 요청에 따라 주문 정보를 조회해주세요.\n"
                "사용할 수 있는 기능:\n"
                "- get_orders(): 전체 주문 목록 조회\n"
                "- get_orders(status='processing'): 처리중인 주문만 조회\n"
                "- get_order_by_id(order_id): 특정 주문 상세 조회\n\n"
                "주문 정보를 친절하고 명확하게 안내해주세요."
            ),
            tools=[get_orders, get_order_by_id],
        )
        
        # 2. 주문 생성 에이전트
        order_creation_agent = LlmAgent(
            name="order_creation_agent",
            model=gemini,
            description="새로운 주문을 생성하는 에이전트",
            instruction=(
                "당신은 주문 생성 전문가입니다. "
                "사용자가 새로운 주문을 생성하려고 할 때:\n"
                "1. 상품명과 가격을 확인하세요\n"
                "2. create_order(item, price) 함수를 사용해 주문을 생성하세요\n"
                "3. 생성된 주문 정보를 확인해주세요\n\n"
                "주문 생성 과정을 단계별로 안내해주세요."
            ),
            tools=[create_order],
        )
        
        # 3. 주문 취소 에이전트 (클래스 인스턴스 생성)
        cancel_order_agent = CancelOrderAgent()
        
        # LlmAgent 초기화
        super().__init__(
            name="order_agent",
            model=gemini,
            description=(
                "주문(Order) 관련 모든 업무를 전담하는 전문 에이전트입니다.\n\n"
                "🔍 [주문 조회 서비스] - order_inquiry_agent로 라우팅:\n"
                "• 키워드: '조회', '목록', '확인', '상태', '보기', 'list', 'check', 'view', 'status'\n"
                "• 예시: '주문 목록 보여줘', '주문 상태 확인', '내 주문 조회', '주문 정보 알려줘'\n"
                "• 기능: 전체/특정 주문 조회, 주문 상태 확인, 주문 목록 표시\n\n"
                "➕ [주문 생성 서비스] - order_creation_agent로 라우팅:\n"
                "• 키워드: '생성', '주문하기', '새 주문', '주문 생성', 'create', 'new', '구매', '결제'\n"
                "• 예시: '새 주문 만들어줘', '상품 주문하고 싶어', '주문 생성해줘', '이거 사고 싶어'\n"
                "• 기능: 새로운 주문 생성, 상품명/가격 입력받아 주문 처리\n\n"
                "❌ [주문 취소 서비스] - cancel_order_agent로 라우팅:\n"
                "• 키워드: '취소', 'cancel', '삭제', 'delete', '주문 취소', '취소하기'\n"
                "• 예시: '주문 취소해줘', '주문을 취소하고 싶어', 'cancel my order'\n"
                "• 기능: 처리중인 주문 취소, 취소 가능 주문 목록 표시, 확인 절차\n\n"
                "⚡ 라우팅 우선순위: 취소 > 생성 > 조회 (기본값)"
            ),
            instruction=(
                "당신은 주문 관련 업무를 전담하는 라우팅 매니저입니다.\n"
                "사용자의 요청을 분석하여 적절한 하위 에이전트에게 작업을 위임하세요.\n\n"
                "라우팅 규칙:\n"
                "1. 취소 관련 키워드 ('취소', 'cancel', '삭제') → cancel_order_agent 실행\n"
                "2. 생성/주문 관련 키워드 ('생성', '주문하기', '새 주문', '구매') → order_creation_agent 실행\n"
                "3. 조회/확인 관련 키워드 ('조회', '목록', '확인', '상태') → order_inquiry_agent 실행\n"
                "4. 애매한 경우 → 사용자에게 명확히 물어보기\n\n"
                "각 하위 에이전트를 실행할 때는 사용자 요청을 그대로 전달하세요."
            ),
            sub_agents=[order_inquiry_agent, order_creation_agent, cancel_order_agent],
            order_inquiry_agent=order_inquiry_agent,
            order_creation_agent=order_creation_agent,
            cancel_order_agent=cancel_order_agent
        )
