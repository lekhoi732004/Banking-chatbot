"""
Calculator Service — Parses natural language financial questions and computes exact savings/loan interest.
Uses LLM to extract parameters, then computes values programmatically to ensure mathematical correctness.
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.services.interest_rate_service import interest_rate_service
from app.services.llm_service import get_llm

logger = logging.getLogger(__name__)


class CalculatorService:
    """Service to extract financial parameters and compute savings/loan schedules."""

    def __init__(self):
        self._extractor_prompt = """Bạn là trợ lý ảo phân tích và trích xuất dữ liệu từ câu hỏi tính toán lãi suất hoặc dư nợ của khách hàng ngân hàng.

Hãy trích xuất các thông số sau và trả về ở định dạng JSON duy nhất. Không thêm bất kỳ giải thích nào trước hoặc sau JSON. Không bọc trong ```json hay ```.

Các thông số cần trích xuất:
- calculation_type: "savings" (gửi tiết kiệm/tích lũy) hoặc "loan" (vay vốn/dư nợ) hoặc "unknown".
- principal: Số tiền gốc gửi hoặc vay (quy đổi hoàn toàn ra đơn vị VND, ví dụ: 500 triệu = 500000000.0, 1 tỷ = 1000000000.0, 100tr = 100000000.0, 2,5 tỷ = 2500000000.0). Nếu không tìm thấy, trả về null.
- interest_rate: Lãi suất năm dưới dạng phần trăm (ví dụ: 6.5% -> 6.5, 8%/năm -> 8.0). Nếu không có lãi suất cụ thể trong câu hỏi, trả về null.
- term_months: Kỳ hạn của gói tiết kiệm hoặc kỳ hạn vay tính bằng tháng (ví dụ: kì hạn 9 tháng -> 9, kỳ hạn 1 năm -> 12, kỳ hạn 24 tháng -> 24). Nếu không có, trả về null.
- duration_months: Tổng thời gian gửi hoặc vay tính bằng tháng (ví dụ: gửi trong 2 năm -> 24, vay 10 năm -> 120, gửi 18 tháng -> 18, sau 2 chu kỳ kì hạn 9 tháng -> 18). Nếu không có, trả về null.
- periods: Số chu kỳ gửi tiết kiệm nếu khách đề cập rõ (ví dụ: sau 2 chu kỳ -> 2, sau 3 chu kỳ -> 3). Nếu không có, trả về null.
- loan_product: Loại sản phẩm vay nếu đề cập, chọn một trong: "mua_nha", "mua_xe", "tieu_dung", "tin_chap" hoặc null.
- saving_channel: Kênh gửi tiết kiệm, chọn một trong: "online", "tai_quay" hoặc null.

Ví dụ 1: "Tôi có 500 triệu gửi tiết kiệm kì hạn 9 tháng vậy sau 2 chu kì tôi có bao nhiêu tiền"
Trả về:
{{
  "calculation_type": "savings",
  "principal": 500000000.0,
  "interest_rate": null,
  "term_months": 9,
  "duration_months": null,
  "periods": 2,
  "loan_product": null,
  "saving_channel": null
}}

Ví dụ 2: "vay 1 tỷ mua nhà trong 10 năm với lãi suất 8% thì mỗi tháng trả bao nhiêu"
Trả về:
{{
  "calculation_type": "loan",
  "principal": 1000000000.0,
  "interest_rate": 8.0,
  "term_months": null,
  "duration_months": 120,
  "periods": null,
  "loan_product": "mua_nha",
  "saving_channel": null
}}

Câu hỏi hiện tại của khách hàng:
"{question}"
"""

    async def calculate(self, question: str, chat_history: str = "") -> str:
        """Parse question, perform interest calculations, and return a formatted Vietnamese response."""
        try:
            # Step 1: Extract parameters using LLM
            params = await self._extract_parameters(question)
            logger.info("Extracted calculator parameters: %s", params)

            calc_type = params.get("calculation_type", "unknown")

            if calc_type == "savings":
                return self._process_savings(params)
            elif calc_type == "loan":
                return self._process_loan(params)
            else:
                return (
                    "Dạ, em hiểu là anh/chị đang muốn tính toán lãi suất hoặc dư nợ. "
                    "Tuy nhiên, em chưa xác định rõ anh/chị muốn tính toán **gửi tiết kiệm** hay **vay vốn**.\n\n"
                    "Anh/chị vui lòng đưa ra câu hỏi cụ thể hơn nhé. Ví dụ:\n"
                    "- *\"Tôi muốn gửi tiết kiệm 200 triệu kì hạn 6 tháng trong 2 chu kỳ.\"*\n"
                    "- *\"Tính lịch trả nợ vay 1 tỷ mua nhà trong 10 năm lãi suất 8%/năm.\"*"
                )

        except Exception as e:
            logger.error("Calculation failed: %s", e, exc_info=True)
            return (
                "Xin lỗi anh/chị, em gặp khó khăn khi xử lý yêu cầu tính toán này. "
                "Anh/chị vui lòng kiểm tra lại thông tin số tiền, kỳ hạn và thử lại nhé. 🙏"
            )

    async def _extract_parameters(self, question: str) -> Dict[str, Any]:
        """Call LLM to parse question into JSON parameters."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._extractor_prompt),
        ])
        llm = get_llm()
        chain = prompt | llm | StrOutputParser()

        raw_output = await chain.ainvoke({"question": question})
        cleaned_output = self._clean_json_output(raw_output)

        try:
            return json.loads(cleaned_output)
        except Exception as e:
            logger.warning("Failed to parse extracted JSON: %s. Raw output: %s", e, raw_output)
            # Simple fallback regex extraction
            return self._fallback_regex_extract(question)

    def _clean_json_output(self, text: str) -> str:
        """Strip think tags and find the JSON structure in LLM output."""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = text.replace('/no_think', '').replace('/think', '').strip()
        # Find JSON block
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return text

    def _fallback_regex_extract(self, question: str) -> Dict[str, Any]:
        """Simple regex fallback if LLM output fails to parse as JSON."""
        params = {
            "calculation_type": "unknown",
            "principal": None,
            "interest_rate": None,
            "term_months": None,
            "duration_months": None,
            "periods": None,
            "loan_product": None,
            "saving_channel": None,
        }
        
        q_lower = question.lower()
        # Detect type
        if any(kw in q_lower for kw in ["gửi", "tiet kiem", "tiết kiệm", "tích lũy", "tich luy"]):
            params["calculation_type"] = "savings"
        elif any(kw in q_lower for kw in ["vay", "nợ", "no", "mượn", "gốc đều", "giảm dần"]):
            params["calculation_type"] = "loan"

        # Try to find a currency amount (e.g. 500 triệu -> 500,000,000)
        million_match = re.search(r'(\d+([.,]\d+)?)\s*(triệu|tr|m)\b', q_lower)
        billion_match = re.search(r'(\d+([.,]\d+)?)\s*(tỷ|ty|t)\b', q_lower)
        if million_match:
            val = float(million_match.group(1).replace(",", "."))
            params["principal"] = val * 1_000_000
        elif billion_match:
            val = float(billion_match.group(1).replace(",", "."))
            params["principal"] = val * 1_000_000_000
            
        # Try to find a term/duration (e.g., 9 tháng, 1 năm)
        thang_matches = re.findall(r'(\d+)\s*tháng', q_lower)
        nam_matches = re.findall(r'(\d+)\s*năm', q_lower)
        
        if thang_matches:
            params["term_months"] = int(thang_matches[0])
        elif nam_matches:
            params["duration_months"] = int(nam_matches[0]) * 12

        return params

    def _process_savings(self, params: Dict[str, Any]) -> str:
        """Handle savings calculation."""
        principal = params.get("principal")
        
        # If no principal provided, prompt user with an example
        if not principal:
            demo_params = params.copy()
            demo_params["principal"] = 100_000_000.0  # Default 100 million for demonstration
            demo_text = self._process_savings(demo_params)
            return (
                "Dạ, để em tính tiền lãi chính xác, anh/chị vui lòng cung cấp thêm **số tiền muốn gửi** ạ.\n\n"
                "Dưới đây là bảng tính toán tham khảo với số tiền gửi mẫu là **100.000.000 đ**:\n\n"
                f"{demo_text}"
            )

        term_months = params.get("term_months")
        if not term_months:
            term_months = 12  # Default to 12 months if unspecified
            assumed_term = True
        else:
            assumed_term = False

        periods = params.get("periods")
        duration_months = params.get("duration_months")

        # Compute durations and periods
        if periods and not duration_months:
            duration_months = term_months * periods
        elif duration_months and not periods:
            periods = max(1.0, duration_months / term_months)
        else:
            # If neither specified, assume 1 period
            periods = 1
            duration_months = term_months

        # Fetch rates from VietBank data
        rate_specified = params.get("interest_rate")
        
        if rate_specified is not None:
            rate_online = rate_specified
            rate_quay = rate_specified
            custom_rate = True
        else:
            rate_online = self._lookup_savings_rate(term_months, "online")
            rate_quay = self._lookup_savings_rate(term_months, "tai_quay")
            custom_rate = False

        # Calculate Online compound (Lãi nhập gốc sau mỗi chu kỳ)
        # Rate per period = rate_per_year * (term_months / 12)
        rate_per_period_online = (rate_online / 100) * (term_months / 12)
        final_compound_online = principal * ((1 + rate_per_period_online) ** periods)
        interest_compound_online = final_compound_online - principal

        # Calculate Online simple (Lãi không nhập gốc)
        interest_simple_online = principal * (rate_online / 100) * (duration_months / 12)
        final_simple_online = principal + interest_simple_online

        # Calculate Counter compound
        rate_per_period_quay = (rate_quay / 100) * (term_months / 12)
        final_compound_quay = principal * ((1 + rate_per_period_quay) ** periods)
        interest_compound_quay = final_compound_quay - principal

        # Calculate Counter simple
        interest_simple_quay = principal * (rate_quay / 100) * (duration_months / 12)
        final_simple_quay = principal + interest_simple_quay

        # Format currencies
        p_str = self._format_vnd(principal)
        dur_str = f"{duration_months} tháng" if duration_months % 12 != 0 else f"{int(duration_months/12)} năm"
        term_str = f"{term_months} tháng"

        # Build response message
        if isinstance(periods, int):
            periods_display = str(periods)
        elif isinstance(periods, float) and periods.is_integer():
            periods_display = str(int(periods))
        else:
            periods_display = f"{periods:.2f}"

        lines = [
            f"💰 **BẢNG TÍNH TOÁN LÃI TIẾT KIỆM VIETBANK**",
            f"- **Số tiền gốc gửi**: {p_str}",
            f"- **Kỳ hạn gửi**: {term_str}" + (" *(giả định)*" if assumed_term else ""),
            f"- **Tổng thời gian gửi**: {dur_str} ({periods_display} chu kỳ)",
        ]

        if custom_rate:
            lines.append(f"- **Lãi suất áp dụng**: {rate_specified}%/năm *(theo yêu cầu)*")
        else:
            lines.append(f"- **Lãi suất hiện tại**: Online: {rate_online}%/năm | Tại quầy: {rate_quay}%/năm")
        
        lines.append("")
        lines.append("### 📊 Kết quả dự tính tiền lãi nhận được:")
        lines.append("")
        lines.append("| Kênh gửi / Phương án nhận lãi | Lãi suất | Tổng lãi nhận được | Tổng số tiền nhận (Gốc + Lãi) |")
        lines.append("|---|---|---|---|")
        
        # Online rows
        lines.append(
            f"| 🖥️ **Tiết kiệm Online** (Lãi nhập gốc - Kép) | {rate_online}%/năm | **{self._format_vnd(interest_compound_online)}** | **{self._format_vnd(final_compound_online)}** |"
        )
        lines.append(
            f"| 🖥️ **Tiết kiệm Online** (Lãi nhận cuối kỳ - Đơn) | {rate_online}%/năm | {self._format_vnd(interest_simple_online)} | {self._format_vnd(final_simple_online)} |"
        )
        
        if not custom_rate:
            # Counter rows
            lines.append(
                f"| 🏦 **Tiết kiệm Tại quầy** (Lãi nhập gốc - Kép) | {rate_quay}%/năm | **{self._format_vnd(interest_compound_quay)}** | **{self._format_vnd(final_compound_quay)}** |"
            )
            lines.append(
                f"| 🏦 **Tiết kiệm Tại quầy** (Lãi nhận cuối kỳ - Đơn) | {rate_quay}%/năm | {self._format_vnd(interest_simple_quay)} | {self._format_vnd(final_simple_quay)} |"
            )

        lines.append("")
        lines.append("> **💡 Lời khuyên:** Anh/chị nên chọn gửi **Tiết kiệm Online** và chọn phương thức **Tái tục lãi nhập gốc** để nhận được mức lãi suất cao hơn và tận dụng lợi ích từ lãi kép.")
        lines.append("")
        lines.append(f"*(Thông số tra cứu dựa trên biểu lãi suất cập nhật ngày {interest_rate_service.get_all_rates().updated_at})*")

        return "\n".join(lines)

    def _process_loan(self, params: Dict[str, Any]) -> str:
        """Handle loan calculation."""
        principal = params.get("principal")
        
        # If no principal provided, prompt user with an example
        if not principal:
            demo_params = params.copy()
            demo_params["principal"] = 500_000_000.0  # Default 500 million for demonstration
            demo_text = self._process_loan(demo_params)
            return (
                "Dạ, để em lập lịch trả nợ chi tiết, anh/chị vui lòng cung cấp thêm **số tiền vay** ạ.\n\n"
                "Dưới đây là ví dụ tính toán trả nợ vay mẫu với số tiền vay là **500.000.000 đ**:\n\n"
                f"{demo_text}"
            )

        duration_months = params.get("duration_months")
        if not duration_months:
            duration_months = 60  # Default to 5 years (60 months)
            assumed_duration = True
        else:
            assumed_duration = False

        loan_product = params.get("loan_product") or "mua_nha"
        rate_specified = params.get("interest_rate")

        # Determine annual rates
        rate_first_year = 0.0
        rate_later = 0.0
        is_floating = False

        if rate_specified is not None:
            rate_first_year = rate_specified
            rate_later = rate_specified
            is_floating = False
            custom_rate = True
        else:
            custom_rate = False
            # Look up loan rates
            rates = interest_rate_service.get_loan_rates(loan_product)
            if rates:
                if "co_dinh" in rates:
                    rate_first_year = rates["co_dinh"]
                    rate_later = rates["co_dinh"]
                    is_floating = False
                else:
                    rate_first_year = rates.get("nam_dau", 7.0)
                    rate_later = rates.get("tu_nam_2", 10.0)
                    is_floating = True
            else:
                # Default rates if lookup fails
                rate_first_year = 7.5
                rate_later = 10.5
                is_floating = True

        # Calculate repayment plans
        # Plan 1: Dư nợ giảm dần (Amortized / Declining balance)
        total_interest_reducing = 0.0
        monthly_principal = principal / duration_months
        schedule_reducing = []

        for m in range(1, duration_months + 1):
            rem_principal = principal - (m - 1) * monthly_principal
            
            # Apply floating rate if applicable
            if is_floating and m > 12:
                current_rate = rate_later
            else:
                current_rate = rate_first_year
                
            interest_m = rem_principal * (current_rate / 100) / 12
            total_interest_reducing += interest_m
            payment_m = monthly_principal + interest_m
            
            # Save first month, year 2 transition, and last month for schedule summary
            if m == 1 or m == 2 or m == 12 or m == 13 or m == duration_months:
                schedule_reducing.append((m, rem_principal, monthly_principal, interest_m, payment_m))

        # Plan 2: Dư nợ gốc cố định (Flat interest)
        # Same rate throughout. If floating, we use the average or the first year rate for simplicity of Flat calculation.
        flat_rate = rate_first_year
        monthly_interest_flat = principal * (flat_rate / 100) / 12
        total_interest_flat = monthly_interest_flat * duration_months
        monthly_payment_flat = monthly_principal + monthly_interest_flat

        # Format currencies
        p_str = self._format_vnd(principal)
        dur_str = f"{duration_months} tháng" if duration_months % 12 != 0 else f"{int(duration_months/12)} năm"
        
        product_names = {
            "mua_nha": "Vay mua nhà/đất",
            "mua_xe": "Vay mua xe",
            "tieu_dung": "Vay tiêu dùng",
            "tin_chap": "Vay tín chấp",
        }
        prod_display = product_names.get(loan_product, "Vay tiêu dùng")

        lines = [
            f"🏠 **BẢNG TÍNH LỊCH TRẢ NỢ VAY VIETBANK**",
            f"- **Số tiền vay (Gốc)**: {p_str}",
            f"- **Thời hạn vay**: {dur_str}" + (" *(giả định)*" if assumed_duration else ""),
            f"- **Sản phẩm vay**: {prod_display}",
        ]

        if custom_rate:
            lines.append(f"- **Lãi suất**: {rate_specified}%/năm cố định *(theo yêu cầu)*")
        elif is_floating:
            lines.append(f"- **Lãi suất ưu đãi năm đầu**: {rate_first_year}%/năm")
            lines.append(f"- **Lãi suất từ năm thứ 2 (dự kiến)**: {rate_later}%/năm *(thả nổi)*")
        else:
            lines.append(f"- **Lãi suất cố định**: {rate_first_year}%/năm")

        lines.append("")
        lines.append("### 1. Phương án Dư nợ giảm dần (Khuyên dùng)")
        lines.append("*Gốc chia đều mỗi tháng, lãi giảm dần theo dư nợ thực tế.*")
        lines.append("")
        lines.append(f"- **Tháng trả đầu tiên (cao nhất)**: {self._format_vnd(monthly_principal + principal * (rate_first_year / 100) / 12)}")
        
        if is_floating and duration_months > 12:
            rem_p_13 = principal - 12 * monthly_principal
            lines.append(f"- **Tháng trả thứ 13 (bắt đầu thả nổi)**: {self._format_vnd(monthly_principal + rem_p_13 * (rate_later / 100) / 12)}")
            
        lines.append(f"- **Tháng trả cuối cùng (thấp nhất)**: {self._format_vnd(monthly_principal + monthly_principal * (rate_later / 100) / 12)}")
        lines.append(f"- **Tổng số tiền lãi phải trả**: **{self._format_vnd(total_interest_reducing)}**")
        lines.append(f"- **Tổng gốc và lãi phải trả**: **{self._format_vnd(principal + total_interest_reducing)}**")
        
        # Repayment schedule preview table
        lines.append("")
        lines.append("#### 📋 Lịch trả nợ trích mẫu (Dư nợ giảm dần):")
        lines.append("")
        lines.append("| Tháng | Dư nợ gốc đầu kỳ | Tiền gốc hàng tháng | Tiền lãi hàng tháng | Tổng trả hàng tháng |")
        lines.append("|---|---|---|---|---|")
        
        # Sort schedule details by month
        shown_months = set()
        for item in schedule_reducing:
            m, rem, g, l, tot = item
            if m not in shown_months:
                shown_months.add(m)
                lines.append(f"| Tháng {m} | {self._format_vnd(rem)} | {self._format_vnd(g)} | {self._format_vnd(l)} | {self._format_vnd(tot)} |")
                if m == 2 and duration_months > 13:
                    lines.append("| ... | ... | ... | ... | ... |")
                elif m == 13 and duration_months > 14:
                    lines.append("| ... | ... | ... | ... | ... |")

        # Flat interest plan details
        lines.append("")
        lines.append("### 2. Phương án Dư nợ gốc cố định")
        lines.append("*Gốc và lãi chia đều đóng cố định bằng nhau mỗi tháng.*")
        lines.append("")
        lines.append(f"- **Số tiền trả cố định mỗi tháng**: {self._format_vnd(monthly_payment_flat)}")
        lines.append(f"- **Tổng số tiền lãi phải trả**: {self._format_vnd(total_interest_flat)}")
        lines.append(f"- **Tổng gốc và lãi phải trả**: {self._format_vnd(principal + total_interest_flat)}")
        
        # Compare saving between two options
        saving = total_interest_flat - total_interest_reducing
        if saving > 0:
            lines.append("")
            lines.append(f"💡 **So sánh:** Phương án **Dư nợ giảm dần** giúp anh/chị tiết kiệm được **{self._format_vnd(saving)}** tiền lãi so với phương án cố định.")

        lines.append("")
        lines.append(f"*(Thông số lãi suất vay và biên độ được cập nhật tham khảo theo biểu phí VietBank ngày {interest_rate_service.get_all_rates().updated_at})*")

        return "\n".join(lines)

    def _lookup_savings_rate(self, term_months: int, channel: str = "online") -> float:
        """Look up interest rates by term in months, falling back to lower terms if exact match is missing."""
        rates = interest_rate_service.get_savings_rates(channel)
        term_key = f"{term_months}_thang"
        
        if term_key in rates:
            return rates[term_key]
            
        # Parse months from keys to find closest lower term
        available_months = []
        for key in rates.keys():
            if "_" in key:
                parts = key.split("_")
                if parts[1] == "thang" and parts[0].isdigit():
                    available_months.append(int(parts[0]))
                    
        if not available_months:
            return rates.get("khong_ky_han", 0.2)
            
        available_months.sort()
        nearest_term = 0
        for m in available_months:
            if m <= term_months:
                nearest_term = m
            else:
                break
                
        if nearest_term > 0:
            return rates.get(f"{nearest_term}_thang", 0.2)
            
        return rates.get("khong_ky_han", 0.2)

    def _format_vnd(self, amount: float) -> str:
        """Format raw float amount into VND string representation (e.g. 500.000.000 đ)."""
        return f"{int(round(amount)):,}".replace(",", ".") + " đ"


# Global singleton
calculator_service = CalculatorService()
