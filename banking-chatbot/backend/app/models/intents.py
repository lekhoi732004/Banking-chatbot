"""
Intent definitions for the Banking Chatbot.
"""

from enum import Enum
from typing import Dict, List


class IntentType(str, Enum):
    """Supported intent types."""
    CHITCHAT = "chitchat"
    TRA_CUU_TY_GIA = "tra_cuu_ty_gia"
    TRA_CUU_LAI_SUAT = "tra_cuu_lai_suat"
    TU_VAN_MO_TAI_KHOAN = "tu_van_mo_tai_khoan"
    TU_VAN_THE_TIN_DUNG = "tu_van_the_tin_dung"
    TU_VAN_VAY_VON = "tu_van_vay_von"
    TU_VAN_TIET_KIEM = "tu_van_tiet_kiem"
    TRA_CUU_BIEU_PHI = "tra_cuu_bieu_phi"
    TINH_TOAN_LAI_SUAT = "tinh_toan_lai_suat"


# Intents that use RAG pipeline
RAG_INTENTS = {
    IntentType.TU_VAN_MO_TAI_KHOAN,
    IntentType.TU_VAN_THE_TIN_DUNG,
    IntentType.TU_VAN_VAY_VON,
    IntentType.TU_VAN_TIET_KIEM,
    IntentType.TRA_CUU_BIEU_PHI,
}

# Intents that use external API
API_INTENTS = {
    IntentType.TRA_CUU_TY_GIA,
    IntentType.TRA_CUU_LAI_SUAT,
}

# Intent descriptions for classifier prompt
INTENT_DESCRIPTIONS: Dict[str, str] = {
    "chitchat": "Chào hỏi, hỏi thăm, nói chuyện phiếm, cảm ơn, tạm biệt, hỏi bot là ai",
    "tra_cuu_ty_gia": "Hỏi tỷ giá ngoại tệ, quy đổi tiền tệ, giá USD/EUR/JPY/GBP hôm nay",
    "tra_cuu_lai_suat": "Hỏi lãi suất tiết kiệm, lãi suất cho vay, lãi suất ngân hàng hiện tại",
    "tu_van_mo_tai_khoan": "Hỏi về thủ tục mở tài khoản, điều kiện, giấy tờ cần mang, các loại tài khoản",
    "tu_van_the_tin_dung": "Hỏi về thẻ tín dụng, các loại thẻ, hạn mức, phí thường niên, đăng ký thẻ",
    "tu_van_vay_von": "Hỏi về vay vốn, vay mua nhà, vay mua xe, hồ sơ vay, quy trình thẩm định, lãi suất vay",
    "tu_van_tiet_kiem": "Hỏi về gửi tiết kiệm, kỳ hạn, rút trước hạn, tiết kiệm online, tích lũy",
    "tra_cuu_bieu_phi": "Hỏi về phí dịch vụ, phí chuyển khoản, phí ATM, phí SMS banking, phí duy trì",
    "tinh_toan_lai_suat": "Tính toán tiền lãi gửi tiết kiệm (tiền gửi) hoặc tính toán lịch trả nợ vay (dư nợ, lãi vay, trả gốc và lãi hàng tháng)",
}

# Example queries for each intent (few-shot)
INTENT_EXAMPLES: Dict[str, List[str]] = {
    "chitchat": [
        "Xin chào",
        "Cảm ơn bạn nhé",
        "Bạn là ai?",
        "Tạm biệt",
    ],
    "tra_cuu_ty_gia": [
        "Tỷ giá USD hôm nay bao nhiêu?",
        "1000 đô la Mỹ đổi được bao nhiêu tiền Việt?",
        "Giá Euro hiện tại?",
    ],
    "tra_cuu_lai_suat": [
        "Lãi suất gửi tiết kiệm 12 tháng?",
        "Lãi suất vay mua nhà hiện tại?",
        "Gửi tiền ngân hàng lãi suất bao nhiêu?",
    ],
    "tu_van_mo_tai_khoan": [
        "Tôi muốn mở tài khoản cần gì?",
        "Mở tài khoản online được không?",
        "Trẻ em có mở tài khoản được không?",
    ],
    "tu_van_the_tin_dung": [
        "Có những loại thẻ tín dụng nào?",
        "Phí thường niên thẻ Visa Platinum?",
        "Thu nhập bao nhiêu thì được mở thẻ tín dụng?",
    ],
    "tu_van_vay_von": [
        "Tôi muốn vay mua nhà cần chuẩn bị hồ sơ gì?",
        "Quy trình thẩm định vay như thế nào?",
        "Vay tín chấp tối đa được bao nhiêu?",
    ],
    "tu_van_tiet_kiem": [
        "Gửi tiết kiệm kỳ hạn nào lãi cao nhất?",
        "Rút tiết kiệm trước hạn bị mất lãi không?",
        "Tiết kiệm online có gì khác tại quầy?",
    ],
    "tra_cuu_bieu_phi": [
        "Phí chuyển khoản liên ngân hàng bao nhiêu?",
        "Rút tiền ATM ngoại mạng mất phí không?",
        "Phí SMS banking hàng tháng?",
    ],
    "tinh_toan_lai_suat": [
        "Tôi có 500 triệu gửi tiết kiệm kì hạn 9 tháng vậy sau 2 chu kì tôi có bao nhiêu tiền",
        "Gửi tiết kiệm 100 triệu kỳ hạn 6 tháng sau 1 năm nhận bao nhiêu tiền lãi",
        "Tính tiền lãi gửi online 50 triệu kỳ hạn 3 tháng sau 3 năm",
        "Tôi muốn vay 1 tỷ mua nhà trong 10 năm với lãi suất 8% thì mỗi tháng trả bao nhiêu tiền",
        "Tính lịch trả nợ vay mua xe 300 triệu lãi suất 9% trong 5 năm",
        "Nếu vay 500 triệu trả trong 2 năm dư nợ giảm dần thì tổng lãi bao nhiêu",
    ],
}
