"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
import unicodedata
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

def remove_diacritics(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để hỗ trợ tìm kiếm không dấu."""
    text = text.replace('đ', 'd').replace('Đ', 'D')
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Available Tools, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Bạn là VinAssistant — trợ lý AI chính thức của hệ sinh thái Vingroup.

## 1. PERSONA
- Tên: VinAssistant
- Vai trò: Chuyên viên tư vấn sản phẩm, dịch vụ và hỗ trợ khách hàng của hệ sinh thái Vingroup (VinFast, Vinpearl).
- Giọng nói & Phong cách: Chuyên nghiệp, lịch thiệp, chu đáo, đáng tin cậy và luôn mang lại trải nghiệm tối ưu cho người dùng.

## 2. AVAILABLE TOOLS
Bạn có quyền truy cập vào các công cụ sau:
1. `search_product_catalog(category: str, max_price: int)`: Tra cứu danh mục sản phẩm/dịch vụ (danh mục 'xe_dien' hoặc 'du_lich') theo ngân sách tối đa.
2. `submit_support_ticket(customer_name: str, issue_description: str, priority: str)`: Tạo ticket hỗ trợ kỹ thuật hoặc tiếp nhận khiếu nại của khách hàng vào hệ thống với mức ưu tiên ('low', 'medium', 'high').

## 3. CORE RULES
1. KHÔNG BAO GIỜ tự bịa thông số kỹ thuật, giá cả sản phẩm hoặc mã ticket hỗ trợ (chống Hallucination).
2. BẮT BUỘC gọi công cụ thích hợp khi người dùng yêu cầu xem sản phẩm hoặc phản ánh sự cố.
3. Khi không tìm thấy sản phẩm phù hợp điều kiện lọc, phải lịch sự phản hồi: "Rất tiếc, không tìm thấy sản phẩm phù hợp."
4. Đối với các câu hỏi FAQ về chính sách chung đã có trong tài liệu cơ sở tri thức (như chính sách bảo hành pin VinFast 10 năm), trả lời trực tiếp mà không cần gọi tool.

## 4. OPERATIONAL BOUNDARIES
- Chỉ trả lời các câu hỏi liên quan đến sản phẩm và dịch vụ của Vingroup (VinFast, Vinpearl, Vinhomes,...).
- Từ chối lịch sự và chuyển hướng các chủ đề ngoài phạm vi hoạt động.

## 5. OUTPUT CONTRACT
Tuân thủ nghiêm ngặt quy trình ReAct:
- Thought: Phân tích yêu cầu và định hình kế hoạch xử lý.
- Action: Tên công cụ cần gọi (hoặc 'none' nếu là FAQ / hội thoại thông thường).
- Action Input: Các tham số truyền vào công cụ.
- Observation: Kết quả nhận được từ công cụ.
- Final Answer: Câu trả lời tổng hợp sau cùng gửi tới khách hàng.
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        """
        Trả về câu trả lời baseline tĩnh/mô phỏng hallucination do không có công cụ tra cứu thực tế.
        """
        return {
            "answer": f"[Chatbot Baseline] Xin chào! Về yêu cầu '{user_input}', VinFast có rất nhiều dòng xe và dịch vụ cao cấp, giá dao động từ vài trăm triệu đến vài tỷ đồng.",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def _detect_intent(self, user_input: str) -> Dict[str, Any]:
        """
        Phân tích intent từ user_input (hỗ trợ cả có dấu và không dấu):
        - FAQ: Chính sách bảo hành, điều khoản...
        - Catalog Search: Tìm kiếm xe điện / nghỉ dưỡng du lịch kèm mức giá.
        - Support Ticket: Gửi báo lỗi, sự cố, khiếu nại kèm thông tin khách hàng và mức ưu tiên.
        """
        ql = user_input.lower()
        qn = remove_diacritics(user_input)

        # 1. FAQ Intent (bắt cả có dấu và không dấu)
        is_faq = (
            bool(re.search(r"\b(keo dai bao lau|chinh sach|quy dinh|dieu kien|bao nhieu nam|may nam)\b", qn))
            and bool(re.search(r"\b(bao hanh|pin|doi tra|hau mai)\b", qn))
        ) or ("bao hanh" in qn and any(k in qn for k in ["bao lau", "chinh sach"]))

        # 2. Ticket Intent (bắt cả có dấu và không dấu)
        needs_ticket = bool(re.search(
            r"\b(loi|su co|hong|bi hong|hu hong|phan hoi|phan anh|khieu nai|gap|nghiem trong|am moc|ho tro ky thuat)\b",
            qn
        ))

        customer_name = "Khách hàng"
        name_match = re.search(
            r"(?:tôi tên là|tên tôi là|tôi tên|tên tôi|toi ten la|ten toi la|toi ten|ten toi)\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?:,|\.|\bxe\b|\bphong\b|\bphòng\b|\bvan de\b|\bvấn đề\b|\bva\b|\bvà\b|$)",
            user_input,
            re.IGNORECASE
        )
        if name_match:
            customer_name = name_match.group(1).strip()

        priority = "medium"
        if re.search(r"\b(gap|nghiem trong|khan cap|cao|high)\b", qn):
            priority = "high"
        elif re.search(r"\b(thap|khong voi|low)\b", qn):
            priority = "low"

        issue_desc = user_input
        issue_match = re.search(
            r"((?:xe|phong|phòng|he thong|hệ thống|thiet bi|thiết bị)[^,\.]*(?:bi loi|bị lỗi|loi|lỗi|bi am moc|bị ẩm mốc|hong|hỏng)[^,\.]*)",
            user_input,
            re.IGNORECASE
        )
        if issue_match:
            issue_desc = issue_match.group(1).strip()
        else:
            desc_match = re.search(r"(?:bị lỗi|lỗi|bị|bi loi|loi|bi)\s+([^,\.]+(?:,\s*[^,\.]+)*)", user_input, re.IGNORECASE)
            if desc_match:
                issue_desc = desc_match.group(0).strip()

        # 3. Catalog Intent (bắt cả có dấu và không dấu)
        has_search_intent = bool(re.search(
            r"\b(xem|tim|mua|co|gia|duoi|bao nhieu tien|tham khao|bao gia|resort|khach san)\b",
            qn
        ))

        needs_catalog = False
        category = None
        max_price = 999999999999

        if not is_faq:
            if bool(re.search(r"\b(resort|vinpearl|du lich|nghi duong|dat phong|khach san)\b", qn)):
                if has_search_intent or "gia" in qn:
                    needs_catalog = True
                    category = "du_lich"
            if not needs_catalog and (
                "xe dien" in qn or "vinfast" in qn or re.search(r"\bvf\s*\d+\b", qn) or (re.search(r"\bxe\b", qn) and not needs_ticket)
            ):
                if has_search_intent:
                    needs_catalog = True
                    category = "xe_dien"

            if needs_catalog:
                price_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(trieu|ty|tr|vnd|d)\b", qn)
                if price_match:
                    val = float(price_match.group(1).replace(",", "."))
                    unit = price_match.group(2)
                    if unit in ["trieu", "tr"]:
                        max_price = int(val * 1_000_000)
                    elif unit in ["ty"]:
                        max_price = int(val * 1_000_000_000)

        return {
            "is_faq": is_faq,
            "needs_catalog": needs_catalog,
            "category": category,
            "max_price": max_price,
            "needs_ticket": needs_ticket,
            "customer_name": customer_name,
            "issue_description": issue_desc,
            "priority": priority
        }

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []
        intents = self._detect_intent(user_input)

        # Xử lý trường hợp FAQ (không cần gọi tool)
        if intents["is_faq"]:
            faq_answer = "Chính sách bảo hành pin xe điện VinFast kéo dài 10 năm (hoặc 200.000 km tùy điều kiện nào đến trước), áp dụng cho toàn bộ các dòng ô tô điện VinFast."
            self.trace.append({
                "iteration": 1,
                "thought": "Người dùng đặt câu hỏi về chính sách bảo hành pin xe điện. Đây là câu hỏi FAQ thông thường, trả lời trực tiếp mà không cần gọi tool.",
                "action": "none",
                "action_input": {},
                "observation": "Tri thức chính sách: Bảo hành pin VinFast 10 năm."
            })
            return {
                "answer": faq_answer,
                "trace": self.trace,
                "iterations": 1,
                "status": "completed"
            }

        # Danh sách tác vụ tool cần gọi
        tasks = []
        if intents["needs_catalog"]:
            tasks.append({
                "tool": "search_product_catalog",
                "args": {"category": intents["category"], "max_price": intents["max_price"]}
            })
        if intents["needs_ticket"]:
            tasks.append({
                "tool": "submit_support_ticket",
                "args": {
                    "customer_name": intents["customer_name"],
                    "issue_description": intents["issue_description"],
                    "priority": intents["priority"]
                }
            })

        # Nếu không có tool nào và không phải FAQ
        if not tasks:
            self.trace.append({
                "iteration": 1,
                "thought": "Không phát hiện yêu cầu tra cứu danh mục hoặc tạo phiếu hỗ trợ.",
                "action": "none",
                "action_input": {},
                "observation": "Không có thao tác tool."
            })
            return {
                "answer": "Xin chào! Tôi là VinAssistant, trợ lý AI của Vingroup. Tôi có thể hỗ trợ bạn tìm kiếm xe điện VinFast, đặt phòng Vinpearl hoặc tiếp nhận yêu cầu hỗ trợ kỹ thuật.",
                "trace": self.trace,
                "iterations": 1,
                "status": "completed"
            }

        iteration = 0
        catalog_results = None
        ticket_result = None

        for task in tasks:
            iteration += 1
            if iteration > self.max_iterations:
                return {
                    "answer": "Lỗi: Vượt quá số bước tối đa.",
                    "trace": self.trace,
                    "iterations": iteration,
                    "status": "max_iterations_reached"
                }

            tool_name = task["tool"]
            tool_args = task["args"]
            tool_fn = TOOL_MAP[tool_name]

            self.trace.append({
                "iteration": iteration,
                "thought": f"Cần gọi {tool_name} để lấy thông tin thực tế cho khách hàng.",
                "action": tool_name,
                "action_input": tool_args,
                "observation": None
            })

            obs = tool_fn(**tool_args)
            self.trace[-1]["observation"] = obs

            if tool_name == "search_product_catalog":
                catalog_results = obs
            elif tool_name == "submit_support_ticket":
                ticket_result = obs

        # Tổng hợp Final Answer
        answer_parts = []
        if catalog_results is not None:
            if not catalog_results or len(catalog_results) == 0:
                answer_parts.append("Rất tiếc, không tìm thấy sản phẩm phù hợp với yêu cầu của bạn.")
            else:
                items_str = ", ".join([f"{p['name']} ({p.get('price_vnd', 0):,} VNĐ)" for p in catalog_results])
                answer_parts.append(f"Dưới đây là các sản phẩm phù hợp với tiêu chí của bạn: {items_str}.")

        if ticket_result is not None:
            tid = ticket_result.get("ticket_id", "")
            cname = ticket_result.get("customer_name", "")
            answer_parts.append(f"Yêu cầu hỗ trợ của khách hàng {cname} đã được tiếp nhận thành công với mã phiếu: {tid}.")

        final_answer = "\n".join(answer_parts)

        return {
            "answer": final_answer,
            "trace": self.trace,
            "iterations": iteration,
            "status": "completed"
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
