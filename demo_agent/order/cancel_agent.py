"""CancelOrderAgent - 주문 취소 전용 에이전트
==========================================

주문 취소 기능만을 전담하는 전문 에이전트
"""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Optional

# ---------- ADK imports -----------------------------
from google.adk.agents import LlmAgent
from google.adk.models import Gemini

# ---------- Local imports -----------------------------
from .data import choose_order, cancel_order

# ---------- Configuration -----------------------------
logger = logging.getLogger(__name__)

gemini = Gemini(
    api_key=os.getenv("GEMINI_API_KEY"),
    model_name="gemini-2.5-pro-preview-05-06"
)

# ---------- CancelOrderAgent Class Implementation -----------------------------
class CancelOrderAgent(LlmAgent):
    """주문 취소 전문 에이전트 클래스"""
    
    def __init__(self):
        """CancelOrderAgent 초기화"""
        super().__init__(
            name="cancel_order_agent",
            model=gemini,
            description="주문 취소 전문 에이전트",
            instruction=(
                "당신은 주문 취소 전문가입니다. 사용자의 주문 취소 요청을 처리해주세요.\n\n"
                "주문 취소 절차:\n"
                "1. 먼저 `choose_order('processing')`를 호출하여 취소 가능한 주문을 확인하세요\n"
                "2. 여러 주문이 있으면 주문 목록을 보여주고 사용자에게 선택을 요청하세요\n"
                "3. 사용자가 주문 ID(예: ORD001)를 제공하면 `choose_order(order_id='ORD001')`로 해당 주문을 선택하세요\n"
                "4. 최종 확인을 거친 후 `cancel_order(order_id='ORD001')`로 주문을 취소하세요\n"
                "5. 취소 결과를 친절하게 안내해주세요\n\n"
                "주의사항:\n"
                "- 'processing' 상태의 주문만 취소 가능합니다\n"
                "- 취소 전에 반드시 사용자에게 확인을 받으세요\n"
                "- 모든 응답은 한국어로 해주세요\n"
                "- 친절하고 명확하게 안내해주세요"
            ),
            tools=[choose_order, cancel_order],
            output_key="cancel_result"
        )
