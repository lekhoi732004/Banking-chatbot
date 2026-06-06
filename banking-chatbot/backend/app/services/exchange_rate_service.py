"""
Exchange Rate Service — Fetches real-time rates from Vietcombank.
Includes in-memory caching with TTL and fallback strategy.
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import httpx

from app.config import EXCHANGE_RATE_CACHE_TTL, VCB_EXCHANGE_RATE_URL
from app.models.schemas import ExchangeRate, ExchangeRateResponse

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Service to fetch and cache exchange rates from Vietcombank."""

    def __init__(self):
        self._cache: Optional[ExchangeRateResponse] = None
        self._cache_time: float = 0
        self._http_client = httpx.AsyncClient(timeout=10.0)

    async def get_rates(self) -> ExchangeRateResponse:
        """Get exchange rates, using cache if valid."""
        # Check cache
        if self._cache and (time.time() - self._cache_time) < EXCHANGE_RATE_CACHE_TTL:
            logger.debug("Returning cached exchange rates")
            response = self._cache.model_copy()
            response.cached = True
            return response

        # Fetch fresh data
        try:
            rates = await self._fetch_from_vcb()
            self._cache = rates
            self._cache_time = time.time()
            return rates
        except Exception as e:
            logger.error(f"Failed to fetch exchange rates: {e}")
            # Return stale cache if available
            if self._cache:
                logger.warning("Returning stale cached data")
                response = self._cache.model_copy()
                response.cached = True
                return response
            # Return empty response
            return ExchangeRateResponse(
                rates=[],
                updated_at="N/A",
                source="Vietcombank (lỗi kết nối)",
                cached=False,
            )

    async def get_rate_by_currency(self, currency_code: str) -> Optional[ExchangeRate]:
        """Get exchange rate for a specific currency."""
        response = await self.get_rates()
        currency_code = currency_code.upper().strip()
        for rate in response.rates:
            if rate.currency_code == currency_code:
                return rate
        return None

    async def _fetch_from_vcb(self) -> ExchangeRateResponse:
        """Fetch exchange rates from Vietcombank XML API."""
        logger.info("Fetching exchange rates from Vietcombank...")
        response = await self._http_client.get(VCB_EXCHANGE_RATE_URL)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.text)

        # Get update time
        datetime_elem = root.find(".//DateTime")
        updated_at = datetime_elem.text if datetime_elem is not None else "N/A"

        # Vietnamese currency names mapping
        vnm_names = {
            "USD": "Đô la Mỹ",
            "EUR": "Euro",
            "GBP": "Bảng Anh",
            "JPY": "Yên Nhật",
            "AUD": "Đô la Úc",
            "CAD": "Đô la Canada",
            "CHF": "Franc Thụy Sĩ",
            "SGD": "Đô la Singapore",
            "KRW": "Won Hàn Quốc",
            "CNY": "Nhân dân tệ",
            "HKD": "Đô la Hồng Kông",
            "NZD": "Đô la New Zealand",
            "THB": "Baht Thái Lan",
            "SEK": "Krona Thụy Điển",
            "NOK": "Krone Na Uy",
            "DKK": "Krone Đan Mạch",
            "RUB": "Rúp Nga",
            "INR": "Rupee Ấn Độ",
            "KWD": "Dinar Kuwait",
            "MYR": "Ringgit Malaysia",
            "SAR": "Riyal Ả Rập Xê Út",
            "LAK": "Kip Lào",
            "KHR": "Riel Campuchia",
        }

        # Parse exchange rates
        rates: List[ExchangeRate] = []
        for exrate in root.findall(".//Exrate"):
            code = exrate.get("CurrencyCode", "").strip()
            name = vnm_names.get(code, exrate.get("CurrencyName", code).strip())
            buy = exrate.get("Buy", "")
            transfer = exrate.get("Transfer", "")
            sell = exrate.get("Sell", "")

            rates.append(ExchangeRate(
                currency_code=code.strip(),
                currency_name=name.strip(),
                buy_cash=self._parse_float(buy),
                buy_transfer=self._parse_float(transfer),
                sell=self._parse_float(sell),
            ))

        logger.info(f"Fetched {len(rates)} exchange rates from Vietcombank")
        return ExchangeRateResponse(
            rates=rates,
            updated_at=updated_at,
            source="Vietcombank",
            cached=False,
        )

    @staticmethod
    def _parse_float(value: str) -> Optional[float]:
        """Parse a float value, handling commas and empty strings."""
        if not value or value.strip() == "-":
            return None
        try:
            return float(value.strip().replace(",", ""))
        except (ValueError, TypeError):
            return None

    def format_rates_for_llm(self, response: ExchangeRateResponse) -> str:
        """Format exchange rates as a readable string for LLM context."""
        if not response.rates:
            return "Không thể lấy dữ liệu tỷ giá. Vui lòng thử lại sau."

        lines = [
            f"📊 Tỷ giá ngoại tệ Vietcombank — Cập nhật: {response.updated_at}",
            f"{'Nguồn' if not response.cached else 'Nguồn (cache)'}: {response.source}",
            "",
            "| Ngoại tệ | Tên ngoại tệ | Mua tiền mặt | Mua chuyển khoản | Giá bán |",
            "|---|---|---|---|---|",
        ]

        # Show most common currencies first
        priority = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "SGD", "KRW", "CNY"]
        sorted_rates = sorted(
            response.rates,
            key=lambda r: priority.index(r.currency_code) if r.currency_code in priority else 999,
        )

        for rate in sorted_rates:
            buy_cash = f"{rate.buy_cash:,.0f} đ" if rate.buy_cash else "-"
            buy_transfer = f"{rate.buy_transfer:,.0f} đ" if rate.buy_transfer else "-"
            sell = f"{rate.sell:,.0f} đ" if rate.sell else "-"
            lines.append(f"| **{rate.currency_code}** | {rate.currency_name} | {buy_cash} | {buy_transfer} | {sell} |")

        return "\n".join(lines)


# Global singleton
exchange_rate_service = ExchangeRateService()
