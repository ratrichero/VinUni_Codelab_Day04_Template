"""
Demo Script — Lab #4: VinAssistant Showcase
Cho phép chạy demo tự động 5 kịch bản chuẩn hoặc nhập câu hỏi trực tiếp để thuyết trình/báo cáo.
"""

import os
import sys
import json

# Thêm starter-code vào đường dẫn tìm kiếm module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "starter-code"))

from template import ChatbotBaseline, ToolCallingAgent

def print_separator(title=""):
    print("\n" + "=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)

def run_scenario(query_id, query_text, description):
    print_separator(f"Kịch Bản {query_id}: {description}")
    print(f"👤 Khách hàng: \"{query_text}\"\n")

    # 1. Chatbot Baseline
    baseline = ChatbotBaseline()
    res_base = baseline.query(query_text)
    print("🤖 [Chatbot Baseline - Không dùng tool]:")
    print(f"   💬 Phản hồi: {res_base['answer']}")
    print(f"   ⚙️ Tool calls: {res_base['tool_calls']}")

    print("\n" + "-" * 50 + "\n")

    # 2. ToolCallingAgent
    agent = ToolCallingAgent(max_iterations=5)
    res_agent = agent.run(query_text)
    print("🚀 [VinAssistant Agent - Có Tool Calling & ReAct Loop]:")
    print(f"   💬 Trả lời: {res_agent['answer']}")
    print(f"   🔄 Số bước (Iterations): {res_agent['iterations']}")
    print("   📋 Trace ReAct:")
    for step in res_agent["trace"]:
        print(f"      - Bước {step.get('iteration', 1)}: Thought: \"{step.get('thought')}\"")
        print(f"        -> Action: {step.get('action')}")
        if step.get('action_input'):
            print(f"        -> Input: {json.dumps(step.get('action_input'), ensure_ascii=False)}")
        if step.get('observation') is not None:
            obs = step.get('observation')
            obs_preview = str(obs) if len(str(obs)) < 120 else str(obs)[:120] + "..."
            print(f"        -> Observation: {obs_preview}")

def main():
    queries_file = os.path.join(os.path.dirname(__file__), "raw-data", "customer_queries.json")
    scenarios = []
    if os.path.exists(queries_file):
        with open(queries_file, "r", encoding="utf-8") as f:
            scenarios = json.load(f)

    print("\n" + "🌟" * 35)
    print("   DEMO LAB #4 — VINASSISTANT TOOL CALLING ENGINE")
    print("   Học viên: VinUni AI Training Program")
    print("🌟" * 35)

    print("\nChọn chế độ demo:")
    print("  1. Chạy tự động qua 5 kịch bản chuẩn (TC01 -> TC05)")
    print("  2. Chế độ trò chuyện tương tác (Nhập câu hỏi tự do)")
    print("  3. Thoát")

    mode = input("\nNhập lựa chọn (1, 2, hoặc 3) [Mặc định: 1]: ").strip() or "1"

    if mode == "1":
        for s in scenarios:
            run_scenario(s["id"], s["query"], s.get("category", ""))
        print_separator("TỔNG KẾT DEMO HOÀN TẤT")
    elif mode == "2":
        agent = ToolCallingAgent(max_iterations=5)
        print_separator("CHẾ ĐỘ TƯƠNG TÁC (Gõ 'exit' để thoát)")
        while True:
            try:
                user_msg = input("\n👤 Bạn: ").strip()
                if not user_msg:
                    continue
                if user_msg.lower() in ["exit", "quit", "thoat", "thoát"]:
                    break
                res = agent.run(user_msg)
                print(f"🤖 VinAssistant: {res['answer']}")
                print(f"   (Iterations: {res['iterations']} | Tools gọi: {[s.get('action') for s in res['trace'] if s.get('action') != 'none']})")
            except (KeyboardInterrupt, EOFError):
                break
        print("\nĐã kết thúc phiên tương tác.")
    else:
        print("Đã thoát.")

if __name__ == "__main__":
    main()
