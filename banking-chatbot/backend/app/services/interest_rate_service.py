"""
Interest Rate Service — Reads mock interest rate data from JSON file.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import MOCK_DATA_DIR
from app.models.schemas import InterestRateResponse

logger = logging.getLogger(__name__)


class InterestRateService:
    """Service to load and query interest rate data from mock JSON."""

    def __init__(self):
        self._data: Optional[Dict[str, Any]] = None
        self._load_data()

    def _load_data(self):
        """Load interest rate data from JSON file."""
        json_path = MOCK_DATA_DIR / "interest_rates.json"
        try:
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info("Loaded interest rate data from %s", json_path)
            else:
                logger.warning("Interest rate file not found: %s", json_path)
                self._data = self._get_default_data()
        except Exception as e:
            logger.error("Failed to load interest rates: %s", e)
            self._data = self._get_default_data()

    def get_all_rates(self) -> InterestRateResponse:
        """Get all interest rates."""
        return InterestRateResponse(
            data=self._data or {},
            updated_at=self._data.get("updated_at", "N/A") if self._data else "N/A",
            source="VietBank (tham khảo)",
        )

    def get_savings_rates(self, channel: str = "all") -> Dict[str, Any]:
        """Get savings interest rates.

        Args:
            channel: 'online', 'tai_quay', or 'all'
        """
        if not self._data or "tiet_kiem" not in self._data:
            return {}

        savings = self._data["tiet_kiem"]
        if channel == "all":
            return savings
        return savings.get(channel, {})

    def get_loan_rates(self, loan_type: str = "all") -> Dict[str, Any]:
        """Get loan interest rates.

        Args:
            loan_type: 'mua_nha', 'mua_xe', 'tieu_dung', 'tin_chap', or 'all'
        """
        if not self._data or "cho_vay" not in self._data:
            return {}

        loans = self._data["cho_vay"]
        if loan_type == "all":
            return loans
        return loans.get(loan_type, {})

    def format_rates_for_llm(self) -> str:
        """Format all interest rates as a readable string for LLM context."""
        if not self._data:
            return "Không có dữ liệu lãi suất."

        lines = [
            f"📊 Biểu lãi suất VietBank — Cập nhật: {self._data.get('updated_at', 'N/A')}",
            f"Đơn vị: {self._data.get('don_vi', '%/năm')}",
            "",
        ]

        # 1. Savings rates
        savings = self._data.get("tiet_kiem", {})
        if savings:
            online = savings.get("online", {})
            tai_quay = savings.get("tai_quay", {})
            khong_ky_han = savings.get("khong_ky_han", 0.2)

            lines.append("### 💰 Lãi suất tiết kiệm")
            lines.append("")
            lines.append("| Kỳ hạn | Tiết kiệm Online | Tiết kiệm tại quầy |")
            lines.append("|---|---|---|")
            lines.append(f"| **Không kỳ hạn** | {khong_ky_han}%/năm | {khong_ky_han}%/năm |")

            # Sort terms numerically
            def term_sort_key(term_key: str):
                try:
                    num = int(term_key.split("_")[0])
                    if "nam" in term_key:
                        num *= 12
                    return num
                except Exception:
                    return 999

            all_terms = sorted(list(set(online.keys()) | set(tai_quay.keys())), key=term_sort_key)
            for term in all_terms:
                term_display = term.replace("_", " ").replace("thang", "tháng")
                term_display = term_display.capitalize()
                rate_online = f"{online.get(term, '-')}%/năm" if term in online else "-"
                rate_quay = f"{tai_quay.get(term, '-')}%/năm" if term in tai_quay else "-"
                lines.append(f"| **{term_display}** | {rate_online} | {rate_quay} |")
            lines.append("")

        # 2. Loan rates
        loans = self._data.get("cho_vay", {})
        if loans:
            lines.append("### 🏠 Lãi suất cho vay")
            lines.append("")
            lines.append("| Sản phẩm vay | Lãi suất năm đầu | Lãi suất từ năm 2 | Biên độ | Mô tả / Ưu đãi |")
            lines.append("|---|---|---|---|---|")

            loan_names = {
                "mua_nha": "Vay mua nhà/đất",
                "mua_xe": "Vay mua xe",
                "tieu_dung": "Vay tiêu dùng",
                "tin_chap": "Vay tín chấp",
            }

            for loan_key, loan_name in loan_names.items():
                if loan_key in loans:
                    loan_data = loans[loan_key]
                    if loan_key == "tin_chap":
                        co_dinh = f"{loan_data.get('co_dinh', '-')}%/năm"
                        mo_ta = loan_data.get('mo_ta', '-')
                        lines.append(f"| **{loan_name}** | {co_dinh} (Cố định) | - | - | {mo_ta} |")
                    else:
                        nam_dau = f"{loan_data.get('nam_dau', '-')}%/năm"
                        tu_nam_2 = f"{loan_data.get('tu_nam_2', '-')}%/năm"
                        bien_do = f"+{loan_data.get('bien_do', '-')}%/năm"
                        mo_ta = loan_data.get('mo_ta', '-')
                        lines.append(f"| **{loan_name}** | {nam_dau} | {tu_nam_2} | {bien_do} | {mo_ta} |")
            lines.append("")

        # 3. Credit Card rates
        cc_data = self._data.get("the_tin_dung", {})
        if cc_data:
            lines.append("### 💳 Lãi suất thẻ tín dụng")
            lines.append("")
            lines.append("| Loại giao dịch / Phí | Lãi suất áp dụng | Chi tiết / Mô tả |")
            lines.append("|---|---|---|")
            
            lines.append(f"| **Lãi suất tiêu dùng** | {cc_data.get('lai_suat_tieu_dung', '-')}%/năm | Áp dụng cho các giao dịch thanh toán mua sắm hàng hóa |")
            lines.append(f"| **Lãi suất rút tiền mặt** | {cc_data.get('lai_suat_rut_tien_mat', '-')}%/năm | Áp dụng từ ngày thực hiện rút tiền mặt tại ATM |")
            
            tra_gop = cc_data.get('lai_suat_tra_gop', {})
            if isinstance(tra_gop, dict):
                lines.append(f"| **Lãi suất trả góp (0%)** | 0% | {tra_gop.get('0_phan_tram', 'Áp dụng tại đối tác liên kết')} |")
                lines.append(f"| **Lãi suất trả góp thường** | {tra_gop.get('thong_thuong', '-')}%/năm | Áp dụng cho các chương trình trả góp tự do |")
                
            lines.append(f"| **Phạt trả chậm** | {cc_data.get('lai_suat_phat_tra_cham', '-')} | Áp dụng khi thanh toán trễ hạn tối thiểu |")
            lines.append("")

        # 4. Payment Account rates
        ac_data = self._data.get("tai_khoan_thanh_toan", {})
        if ac_data:
            lines.append("### 🏦 Lãi suất tài khoản thanh toán")
            lines.append("")
            lines.append("| Loại số dư | Lãi suất | Mô tả |")
            lines.append("|---|---|---|")
            lines.append(f"| **Số dư tài khoản** | {ac_data.get('lai_suat_so_du', '-')}%/năm | {ac_data.get('mo_ta', 'Tính trên số dư cuối ngày')} |")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _get_default_data() -> Dict[str, Any]:
        """Return default/fallback interest rate data."""
        return {
            "tiet_kiem": {
                "online": {
                    "1_thang": 3.1, "3_thang": 3.4, "6_thang": 4.1,
                    "9_thang": 4.1, "12_thang": 5.0, "18_thang": 5.3,
                    "24_thang": 5.3, "36_thang": 5.5,
                },
                "tai_quay": {
                    "1_thang": 2.9, "3_thang": 3.2, "6_thang": 3.9,
                    "9_thang": 3.9, "12_thang": 4.8, "18_thang": 5.1,
                    "24_thang": 5.1, "36_thang": 5.3,
                },
                "khong_ky_han": 0.2,
            },
            "cho_vay": {
                "mua_nha": {"nam_dau": 6.5, "tu_nam_2": 9.5},
                "mua_xe": {"nam_dau": 7.0, "tu_nam_2": 10.0},
                "tieu_dung": {"nam_dau": 8.0, "tu_nam_2": 11.5},
                "tin_chap": {"co_dinh": 12.0},
            },
            "updated_at": "2026-06-04",
            "don_vi": "%/năm",
        }


# Global singleton
interest_rate_service = InterestRateService()
