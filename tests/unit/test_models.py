"""Тести доменних моделей даних Bond, PriceSnapshot та CashFlowEvent (T004)."""
from datetime import date, datetime
import pytest

from src.bond_collector.models import (
    Bond,
    PriceSnapshot,
    CashFlowEvent,
    CashFlowType,
)


@pytest.mark.unit
class TestCashFlowEvent:
    """Тестування сутності грошового потоку (купон / погашення)."""

    def test_cashflow_creation_and_computed_status(self):
        past_date = date(2023, 5, 24)
        future_date = date(2030, 1, 1)

        past_event = CashFlowEvent(
            isin="UA4000227185",
            payment_date=past_date,
            event_type=CashFlowType.COUPON,
            amount=75.50,
            currency="UAH",
        )
        assert past_event.status == "Виплачено"
        assert past_event.event_type.value == "Купон"

        future_event = CashFlowEvent(
            isin="UA4000227185",
            payment_date=future_date,
            event_type=CashFlowType.REDEMPTION,
            amount=1000.0,
            currency="UAH",
        )
        assert future_event.status == "Заплановано"
        assert future_event.event_type.value == "Погашення"

    def test_invalid_amount_raises_value_error(self):
        with pytest.raises(ValueError, match="Сума виплати не може бути від'ємною"):
            CashFlowEvent(
                isin="UA4000227185",
                payment_date=date(2026, 1, 1),
                event_type=CashFlowType.COUPON,
                amount=-10.0,
                currency="UAH",
            )


@pytest.mark.unit
class TestBondModel:
    """Тестування сутності облігації Bond та розрахункових властивостей."""

    def test_bond_creation_and_availability_status_in_stock(self):
        bond = Bond(
            isin="UA4000227185",
            name="Військові облігації",
            currency="UAH",
            maturity_date=date(2027, 5, 26),
            is_military=True,
            price_buy=1056.23,
            rate_buy=14.85,
            price_sell=995.10,
            rate_sell=17.50,
            nominal=1000.0,
            available_qty=85217,
            min_amount=1,
            max_amount=85217,
            is_active=True,
            updated_at=datetime(2026, 9, 24, 12, 0, 0),
        )
        assert bond.isin == "UA4000227185"
        assert bond.available_qty == 85217
        assert bond.availability_status == "В наявності"

    def test_bond_availability_status_sold_out(self):
        bond = Bond(
            isin="UA4000227185",
            name="Військові облігації",
            currency="UAH",
            maturity_date=date(2027, 5, 26),
            is_military=True,
            price_buy=1056.23,
            rate_buy=14.85,
            nominal=1000.0,
            available_qty=0,
            is_active=False,
            updated_at=datetime(2026, 9, 24, 12, 0, 0),
        )
        assert bond.available_qty == 0
        assert bond.availability_status == "Розпродано"

    def test_invalid_isin_raises_value_error(self):
        with pytest.raises(ValueError, match="Невалідний формат ISIN"):
            Bond(
                isin="INVALID_ISIN",
                name="Тестова облігація",
                currency="UAH",
                maturity_date=date(2027, 5, 26),
                is_military=True,
                available_qty=100,
                updated_at=datetime.now(),
            )

    def test_invalid_negative_available_qty_raises_value_error(self):
        with pytest.raises(ValueError, match="Кількість у наявності не може бути від'ємною"):
            Bond(
                isin="UA4000227185",
                name="Тестова облігація",
                currency="UAH",
                maturity_date=date(2027, 5, 26),
                is_military=True,
                available_qty=-5,
                updated_at=datetime.now(),
            )


@pytest.mark.unit
class TestPriceSnapshot:
    """Тестування сутності знімку цін PriceSnapshot."""

    def test_price_snapshot_creation_from_bond(self):
        now = datetime(2026, 9, 24, 12, 0, 0)
        bond = Bond(
            isin="UA4000227185",
            name="Військові облігації",
            currency="UAH",
            maturity_date=date(2027, 5, 26),
            is_military=True,
            price_buy=1056.23,
            rate_buy=14.85,
            price_sell=995.10,
            rate_sell=17.50,
            nominal=1000.0,
            available_qty=5000,
            is_active=True,
            updated_at=now,
        )
        snapshot = PriceSnapshot.from_bond(bond)
        assert snapshot.isin == "UA4000227185"
        assert snapshot.snapshot_time == now
        assert snapshot.price_buy == 1056.23
        assert snapshot.available_qty == 5000
        assert snapshot.availability_status == "В наявності"
