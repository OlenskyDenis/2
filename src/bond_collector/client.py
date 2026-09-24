"""HTTP-клієнт для взаємодії з публічним API Приват24 (T010, T011)."""
from datetime import date, datetime
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

from src.bond_collector.interfaces import BaseBondSource
from src.bond_collector.models import Bond, CashFlowEvent, CashFlowType

logger = logging.getLogger(__name__)


class Privat24APIError(Exception):
    """Помилка взаємодії з API Приват24."""
    pass


def parse_date(date_str: Optional[str]) -> date:
    """Парсить дату з форматів 'DD.MM.YYYY' або 'YYYY-MM-DD'."""
    if not date_str:
        return date.today()
    clean_str = date_str[:10]
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            pass
    return date.today()


class Privat24Client(BaseBondSource):
    """Клієнт для публічних ендпоінтів Приват24 (ОВДП)."""

    DEFAULT_HOST = "https://next.privat24.ua"
    DEFAULT_TIMEOUT = 10.0

    def __init__(self, host: str = DEFAULT_HOST, timeout: float = DEFAULT_TIMEOUT):
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://next.privat24.ua",
            "Referer": "https://next.privat24.ua/bonds/list",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        self.xref: Optional[str] = None
        self.base_url: str = "api/p24/pub/"

    def _apply_jitter(self, min_ms: int = 50, max_ms: int = 100) -> None:
        """Затримка між точковими запитами (50–100 мс) для захисту від троттлінгу."""
        sleep_sec = random.uniform(min_ms / 1000.0, max_ms / 1000.0)
        time.sleep(sleep_sec)

    def init_session(self) -> Tuple[str, str]:
        """Ініціалізує нову гостьову сесію в Приват24 та отримує xref токен."""
        url = f"{self.host}/api/p24/init"
        try:
            resp = self.session.post(url, json={}, timeout=self.timeout)
            resp.raise_for_status()
            raw_data = resp.json()
            payload = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else raw_data

            if isinstance(payload, dict):
                self.xref = payload.get("xref")
                self.base_url = payload.get("base_url", "api/p24/pub/")

            if not self.xref:
                raise Privat24APIError(f"Сервер не повернув токен 'xref': {raw_data}")
            return self.xref, self.base_url
        except Exception as e:
            raise Privat24APIError(f"Помилка ініціалізації сесії Приват24: {e}") from e

    def _ensure_session(self) -> None:
        """Гарантує наявність дійсного xref токена."""
        if not self.xref:
            self.init_session()

    def get_raw_bonds(self, retry_on_expired: bool = True) -> List[Dict[str, Any]]:
        """Отримує сирий список котирувань ОВДП через ендпоінт bargaining."""
        self._ensure_session()
        url = f"{self.host}/{self.base_url}bonds"
        payload = {"action": "bargaining", "xref": self.xref}

        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            raw_data = resp.json()

            # Обробка застарілої сесії (код 95 або session_was_expired)
            if isinstance(raw_data, dict):
                code = raw_data.get("code")
                msg = str(raw_data.get("message", ""))
                if code == 95 or "session_was_expired" in msg:
                    if retry_on_expired:
                        logger.warning("Сесія застаріла (код 95). Повторна ініціалізація...")
                        self.init_session()
                        return self.get_raw_bonds(retry_on_expired=False)
                    raise Privat24APIError("Сесія Приват24 застаріла після повторної спроби")

                data = raw_data.get("data", raw_data)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "bonds" in data and isinstance(data["bonds"], list):
                    return data["bonds"]

            if isinstance(raw_data, list):
                return raw_data
            return []
        except Exception as e:
            if retry_on_expired and ("401" in str(e) or "403" in str(e)):
                self.init_session()
                return self.get_raw_bonds(retry_on_expired=False)
            raise Privat24APIError(f"Помилка завантаження каталогу облігацій: {e}") from e

    def get_limits(self, isin: str) -> Dict[str, Any]:
        """Отримує залишки на складі та ліміти купівлі для вказаного ISIN."""
        self._ensure_session()
        self._apply_jitter()

        url = f"{self.host}/{self.base_url}bonds"
        params = {
            "action": "limits",
            "xref": self.xref,
            "isin": isin,
            "operation": "s",  # обов'язково для гостьового перегляду без авторизації
        }

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            raw_data = resp.json()
            payload = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else raw_data
            if isinstance(payload, dict):
                return {
                    "isin": isin,
                    "count": int(payload.get("count", 0)),
                    "minAmount": payload.get("minAmount", 1),
                    "maxAmount": payload.get("maxAmount"),
                    "active": bool(payload.get("active", False)),
                }
        except Exception as e:
            logger.warning(f"Не вдалося отримати ліміти для {isin}: {e}")

        # Дефолтний результат у разі помилки або відсутності лімітів
        return {
            "isin": isin,
            "count": 0,
            "minAmount": 1,
            "maxAmount": None,
            "active": False,
        }

    def get_operations(self, isin: str) -> List[CashFlowEvent]:
        """Отримує календарний графік виплат (купони, погашення) для вказаного ISIN."""
        self._ensure_session()
        self._apply_jitter()

        url = f"{self.host}/{self.base_url}bonds"
        payload = {
            "action": "operations",
            "xref": self.xref,
            "isin": isin,
        }

        events: List[CashFlowEvent] = []
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            raw_data = resp.json()
            payload_data = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else raw_data

            if isinstance(payload_data, dict):
                raw_ops = payload_data.get("operations", [])
            elif isinstance(payload_data, list):
                raw_ops = payload_data
            else:
                raw_ops = []

            for op in raw_ops:
                dt_str = op.get("dat") or op.get("date")
                if not dt_str:
                    continue
                pay_date = parse_date(dt_str)
                currency = op.get("currency", "UAH")

                # Обробка формату Приват24: dat, kupon, payment
                if "kupon" in op or "payment" in op:
                    kupon_val = float(op.get("kupon", 0.0) or 0.0)
                    payment_val = float(op.get("payment", 0.0) or 0.0)

                    if kupon_val > 0:
                        events.append(
                            CashFlowEvent(
                                isin=isin,
                                payment_date=pay_date,
                                event_type=CashFlowType.COUPON,
                                amount=kupon_val,
                                currency=currency,
                            )
                        )
                    if payment_val > 0:
                        events.append(
                            CashFlowEvent(
                                isin=isin,
                                payment_date=pay_date,
                                event_type=CashFlowType.REDEMPTION,
                                amount=payment_val,
                                currency=currency,
                            )
                        )
                else:
                    # Загальний формат: type, amount
                    op_type_raw = str(op.get("type", "")).upper()
                    if "KUPON" in op_type_raw or "COUPON" in op_type_raw:
                        ev_type = CashFlowType.COUPON
                    else:
                        ev_type = CashFlowType.REDEMPTION

                    amount = float(op.get("amount", 0.0))
                    events.append(
                        CashFlowEvent(
                            isin=isin,
                            payment_date=pay_date,
                            event_type=ev_type,
                            amount=amount,
                            currency=currency,
                        )
                    )

        except Exception as e:
            logger.warning(f"Не вдалося отримати графік операцій для {isin}: {e}")

        return events

    def fetch_bonds(self) -> List[Bond]:
        """Базовий метод інтерфейсу BaseBondSource: отримує список випусків з базовими атрибутами."""
        raw_list = self.get_raw_bonds()
        bonds: List[Bond] = []

        for item in raw_list:
            isin = item.get("isin")
            if not isin:
                continue

            term_str = item.get("maturity") or item.get("term") or item.get("maturityDate")
            maturity_date = parse_date(term_str)

            name = item.get("name") or "Військові облігації"
            currency = item.get("currency", "UAH")

            # У API Приват24: sellPrice/sellYield - купівля клієнтом у банку;
            # buyPrice/buyYield - зворотний викуп банком у клієнта
            price_buy = float(item["sellPrice"]) if item.get("sellPrice") is not None else (
                float(item["priceBuy"]) if item.get("priceBuy") is not None else None
            )
            rate_buy = float(item["sellYield"]) if item.get("sellYield") is not None else (
                float(item["rateBuy"]) if item.get("rateBuy") is not None else None
            )

            price_sell = float(item["buyPrice"]) if item.get("buyPrice") is not None else (
                float(item["priceSell"]) if item.get("priceSell") is not None else None
            )
            rate_sell = float(item["buyYield"]) if item.get("buyYield") is not None else (
                float(item["rateSell"]) if item.get("rateSell") is not None else None
            )

            nominal = float(item.get("nominal", 1000.0))
            is_active = bool(item.get("active", True))
            is_military = bool(item.get("military", True))

            bond = Bond(
                isin=isin,
                name=name,
                currency=currency,
                maturity_date=maturity_date,
                is_military=is_military,
                price_buy=price_buy,
                rate_buy=rate_buy,
                price_sell=price_sell,
                rate_sell=rate_sell,
                nominal=nominal,
                is_active=is_active,
                updated_at=datetime.now(),
            )
            bonds.append(bond)

        return bonds

    def fetch_limits(self, isin: str) -> Dict[str, Any]:
        """Реалізація методу BaseBondSource."""
        return self.get_limits(isin)

    def fetch_operations(self, isin: str) -> List[CashFlowEvent]:
        """Реалізація методу BaseBondSource."""
        return self.get_operations(isin)
