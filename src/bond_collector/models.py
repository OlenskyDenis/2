"""Доменні моделі даних для облігацій, знімків цін та грошових потоків."""
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
import re
from typing import List, Optional

ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


class CashFlowType(str, Enum):
    """Тип грошового потоку за облігацією."""
    COUPON = "Купон"
    REDEMPTION = "Погашення"


@dataclass
class CashFlowEvent:
    """Сутність календарної події грошового потоку (купонна виплата або виплата номіналу)."""
    isin: str
    payment_date: date
    event_type: CashFlowType
    amount: float
    currency: str

    def __post_init__(self):
        if not ISIN_REGEX.match(self.isin):
            raise ValueError(f"Невалідний формат ISIN: '{self.isin}'")
        if self.amount < 0:
            raise ValueError("Сума виплати не може бути від'ємною")
        if isinstance(self.event_type, str) and not isinstance(self.event_type, CashFlowType):
            self.event_type = CashFlowType(self.event_type)

    @property
    def status(self) -> str:
        """Статус виплати: 'Виплачено' (минула) або 'Заплановано' (майбутня)."""
        return "Виплачено" if self.payment_date <= date.today() else "Заплановано"


@dataclass
class Bond:
    """Доменна сутність облігації (ОВДП)."""
    isin: str
    name: str
    currency: str
    maturity_date: date
    is_military: bool
    nominal: float = 1000.0
    price_buy: Optional[float] = None
    rate_buy: Optional[float] = None
    price_sell: Optional[float] = None
    rate_sell: Optional[float] = None
    available_qty: int = 0
    min_amount: Optional[int] = 1
    max_amount: Optional[int] = None
    is_active: bool = True
    updated_at: datetime = field(default_factory=datetime.now)
    cash_flows: List[CashFlowEvent] = field(default_factory=list)

    def __post_init__(self):
        if not ISIN_REGEX.match(self.isin):
            raise ValueError(f"Невалідний формат ISIN: '{self.isin}'")
        if self.available_qty < 0:
            raise ValueError("Кількість у наявності не може бути від'ємною")
        if self.nominal <= 0:
            raise ValueError("Номінал повинен бути більше нуля")

    @property
    def days_to_maturity(self) -> int:
        """Кількість календарних днів до дати погашення."""
        delta = (self.maturity_date - date.today()).days
        return max(0, delta)

    @property
    def availability_status(self) -> str:
        """Людинозчитуваний статус доступності паперу для купівлі."""
        if self.available_qty > 0 and self.is_active:
            return "В наявності"
        return "Розпродано"


@dataclass
class PriceSnapshot:
    """Незмінний історичний зріз котирувань та залишків облігації на певний момент часу."""
    snapshot_time: datetime
    isin: str
    currency: str
    price_buy: Optional[float]
    rate_buy: Optional[float]
    price_sell: Optional[float]
    rate_sell: Optional[float]
    available_qty: int
    availability_status: str

    @classmethod
    def from_bond(cls, bond: Bond) -> "PriceSnapshot":
        """Створює історичний зріз на основі поточного стану сутності Bond."""
        return cls(
            snapshot_time=bond.updated_at,
            isin=bond.isin,
            currency=bond.currency,
            price_buy=bond.price_buy,
            rate_buy=bond.rate_buy,
            price_sell=bond.price_sell,
            rate_sell=bond.rate_sell,
            available_qty=bond.available_qty,
            availability_status=bond.availability_status,
        )
