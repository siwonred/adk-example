"""Order Data & Business Logic
=============================

주문 관련 공통 데이터와 비즈니스 로직을 담은 공유 모듈
모든 주문 관련 에이전트에서 공통으로 사용하는 데이터와 함수들
"""

from typing import Dict, List, Optional

# ---------- Shared Order Data -----------------------------
_orders: List[Dict[str, str]] = [
    {"id": "ORD001", "item": "스마트폰", "status": "processing", "price": "800,000원"},
    {"id": "ORD002", "item": "노트북", "status": "shipped", "price": "1,200,000원"},
    {"id": "ORD003", "item": "태블릿", "status": "processing", "price": "600,000원"},
]

# ---------- Common Business Logic Functions -----------------------------
def get_orders(status: Optional[str] = None) -> Dict[str, any]:
    """주문 목록 조회"""
    if status is None:
        filtered = _orders
    else:
        filtered = [o for o in _orders if o["status"] == status]
    return {
        "status": "success",
        "orders": filtered,
        "count": len(filtered)
    }

def get_order_by_id(order_id: str) -> Dict[str, any]:
    """특정 주문 조회"""
    for order in _orders:
        if order["id"] == order_id:
            return {"status": "success", "order": order}
    return {"status": "error", "message": f"주문 {order_id}를 찾을 수 없습니다."}

def cancel_order(order_id: str) -> Dict[str, str]:
    """주문 취소"""
    for order in _orders:
        if order["id"] == order_id:
            if order["status"] == "processing":
                order["status"] = "cancelled"
                return {"status": "success", "message": f"주문 {order_id}가 성공적으로 취소되었습니다."}
            else:
                return {"status": "error", "message": f"주문 {order_id}는 현재 상태({order['status']})에서 취소할 수 없습니다."}
    return {"status": "error", "message": f"주문 {order_id}를 찾을 수 없습니다."}

def create_order(item: str, price: str) -> Dict[str, any]:
    """새 주문 생성"""
    new_id = f"ORD{len(_orders) + 1:03d}"
    new_order = {
        "id": new_id,
        "item": item,
        "status": "processing",
        "price": price
    }
    _orders.append(new_order)
    return {"status": "success", "order": new_order, "message": f"새 주문 {new_id}가 생성되었습니다."}

def choose_order(state: Optional[str] = None, order_id: Optional[str] = None) -> Dict:
    """주문 선택 툴 - order_id가 없으면 목록 조회, 있으면 해당 주문 선택"""
    
    # 사용자가 특정 주문 ID를 선택한 경우
    if order_id:
        for order in _orders:
            if order["id"] == order_id and (not state or order["status"] == state):
                return {
                    "status": "success",
                    "selected_order_id": order_id,
                    "options": [],
                    "message": f"주문 {order_id}({order['item']})를 선택했습니다."
                }
        return {
            "status": "error", 
            "selected_order_id": None,
            "options": [],
            "message": f"주문 {order_id}를 찾을 수 없거나 상태가 맞지 않습니다."
        }
    
    # 주문 목록 조회 및 자동 선택 로직
    orders = get_orders(state)
    if orders["status"] == "success":
        if len(orders["orders"]) == 1:
            return {
                "status": "success",
                "selected_order_id": orders["orders"][0]["id"],
                "options": orders["orders"],
                "message": f"주문 {orders['orders'][0]['id']}를 선택했습니다."
            }
        else:
            return {
                "status": "pending",
                "selected_order_id": None,
                "options": orders["orders"],
                "message": "주문이 2개 이상이므로 사용자에게 주문을 선택하라고 해주세요."
            }
    else:
        return {
            "status": "error",
            "selected_order_id": None, 
            "options": [],
            "message": "주문 목록을 가져오는데 실패했습니다."
        } 
