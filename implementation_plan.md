# Implementation Plan — Lab #4: System Prompt Engineering & Tool Calling Engine

Xây dựng hệ thống Agent với System Prompt chuyên nghiệp và cơ chế Tool Calling cho trợ lý ảo VinAssistant theo đúng tài liệu `student_guide.md` và vượt qua 8/8 test cases của `autograder/test_agent.py`.

## User Review Required
> [!NOTE]
> Bài lab được thiết kế chạy ở chế độ **Mock Simulator** (không cần `GEMINI_API_KEY`), mô phỏng logic Function Calling chính xác theo intent detection, ReAct trace và schema của LLM. Toàn bộ mã nguồn sẽ được viết và kiểm thử tự động bằng `pytest`.

## Proposed Changes

### Component 1: Hoàn thiện Tool Functions & Schemas (`starter-code/tools.py`)

#### [MODIFY] [tools.py](file:///d:/VinUniAI/Codelab_Day04_Template/starter-code/tools.py)
- **`search_product_catalog(category: str, max_price: int)`**:
  - Đọc `product_catalog.json` từ `RAW_DATA_DIR`.
  - Chuẩn hóa so sánh `category.lower()`.
  - Lọc sản phẩm có `price_vnd <= max_price`.
  - Trả về danh sách dict các sản phẩm.
- **`submit_support_ticket(customer_name: str, issue_description: str, priority: str)`**:
  - Đọc `support_tickets.json` hiện có nếu tồn tại (tránh ghi đè).
  - Sinh mã ticket format `TK-{today}-{seq:03d}` (với `today = datetime.now().strftime("%Y%m%d")`).
  - Append ticket mới với các trường: `ticket_id`, `customer_name`, `issue_description`, `priority`, `status="open"`, `created_at`, `category="general"`.
  - Ghi lại file với `ensure_ascii=False, indent=2`.
  - Trả về dict xác nhận có `ticket_id`, `customer_name`, `priority`, `status`, `message`.
- **`TOOL_DEFINITIONS`**:
  - Cung cấp JSON Schema chuẩn cho 2 tools (`search_product_catalog` và `submit_support_ticket`) gồm `name`, `description`, `parameters` (type, properties, required, enum).

---

### Component 2: Hoàn thiện Agent & Baseline (`starter-code/template.py`)

#### [MODIFY] [template.py](file:///d:/VinUniAI/Codelab_Day04_Template/starter-code/template.py)
- **TODO 1: `SYSTEM_PROMPT`**:
  - Cấu trúc đầy đủ 5 phần chuẩn production:
    1. Persona (VinAssistant - Vingroup)
    2. Available Tools (`search_product_catalog`, `submit_support_ticket`)
    3. Core Rules (Không bịa đặt thông tin, gọi tool khi cần dữ liệu thực)
    4. Operational Boundaries (Chỉ hỗ trợ hệ sinh thái Vingroup)
    5. Output Contract (Thought / Action / Observation / Final Answer)
- **TODO 2: `ChatbotBaseline`**:
  - Triển khai `query(user_input)`: Trả về câu trả lời baseline dạng mock hallucination, `tool_calls: []`, `status: "success"`, `mode: "mock_baseline"`.
- **TODO 3: Intent Detection & Extraction**:
  - Xây dựng hàm/logic bóc tách intent và tham số từ câu query:
    - Nhận biết catalog search: từ khóa xe điện (`xe_dien`), du lịch/nghỉ dưỡng (`du_lich`), trích xuất mức giá (ví dụ: `600 triệu` -> `600000000`, `6 triệu` -> `6000000`, `200 triệu` -> `200000000`).
    - Nhận biết ticket submission: tên khách hàng (regex `tên tôi là ...` hoặc `tôi tên ...`), mô tả sự cố (lỗi, sự cố, hỏng...), mức độ ưu tiên (`gấp`/`nghiêm trọng` -> `high`, `trung bình` -> `medium`, `thấp` -> `low`).
    - Nhận biết FAQ: hỏi chính sách, bảo hành, pin...
- **TODO 4: Agent Loop & Execution**:
  - Triển khai `run(user_input)`:
    - Quản lý `iterations` (đảm bảo cho các single query trả về `iterations: 1`).
    - Thực thi tool dựa trên intent đã nhận diện.
    - Lưu từng bước vào `self.trace` (`thought`, `action`, `observation`).
    - Tổng hợp kết quả trả về `answer`:
      - Nếu kết quả tìm kiếm rỗng: fallback thông báo "Rất tiếc, không tìm thấy sản phẩm phù hợp...".
      - Nếu tìm thấy xe/resort: trả lời kèm tên sản phẩm (`VF 3`, `VF 5`,...).
      - Nếu tạo ticket: thông báo mã ticket `TK-...` và tên khách hàng.
      - Nếu FAQ: trả lời về chính sách bảo hành (pin xe điện 10 năm hoặc 200.000 km).

## Verification Plan

### Automated Tests
- Chạy toàn bộ pytest suite:
  ```bash
  python -m pytest autograder/test_agent.py -v
  ```
- Kỳ vọng: Toàn bộ 8/8 test cases `PASSED`.

### Manual Verification
- Chạy trực tiếp `python starter-code/template.py` để kiểm tra luồng in ra màn hình của Baseline và ToolCallingAgent với log trace JSON.
