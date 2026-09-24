"""Модульні тести сервісу збору даних CollectorService (T012)."""
from datetime import date, datetime
import pytest

from src.bond_collector.interfaces import BaseBondSource
from src.bond_collector.models import Bond, CashFlowEvent, CashFlowType
from src.bond_collector.service import CollectorService


class MockSource(BaseBondSource):
    """Мокове джерело даних для тестування CollectorService."""

    def __init__(self):
        self.bonds = [
            Bond(
                isin="UA4000227185",
                name="Військові облігації",
                currency="UAH",
                maturity_date=date(2027, 5, 26),
                is_military=True,
                price_buy=1056.23,
                rate_buy=14.85,
            ),
            Bond(
                isin="UA4000227193",
                name="Військові облігації 2",
                currency="UAH",
                maturity_date=date(2028, 6, 15),
                is_military=True,
                price_buy=980.00,
                rate_buy=16.00,
            ),
        ]

    def fetch_bonds(self):
        return self.bonds

    def fetch_limits(self, isin: str):
        if isin == "UA4000227185":
            return {"isin": isin, "count": 85217, "minAmount": 1, "maxAmount": 85217, "active": True}
        # Симулюємо помилку або відсутність для другого паперу
        raise RuntimeError("Network error on limits")

    def fetch_operations(self, isin: str):
        if isin == "UA4000227185":
            return [
                CashFlowEvent(
                    isin=isin,
                    payment_date=date(2025, 5, 21),
                    event_type=CashFlowType.COUPON,
                    amount=75.50,
                    currency="UAH",
                )
            ]
        return []


@pytest.mark.unit
class TestCollectorService:
    """Тестування координації збору, оновлення залишків та часткової відмовостійкості."""

    def test_collect_all_with_graceful_degradation(self):
        source = MockSource()
        service = CollectorService(source=source)

        progress_records = []

        def on_progress(current, total, isin):
            progress_records.append((current, total, isin))

        collected = service.collect_all(progress_callback=on_progress)

        assert len(collected) == 2
        # Перша облігація має залишки та виплати
        first = collected[0]
        assert first.isin == "UA4000227185"
        assert first.available_qty == 85217
        assert first.availability_status == "В наявності"
        assert len(first.cash_flows) == 1

        # Друга облігація має залишок 0 через Graceful degradation
        second = collected[1]
        assert second.isin == "UA4000227193"
        assert second.available_qty == 0
        assert second.availability_status == "Розпродано"

        # Перевірка колбеку прогресу
        assert len(progress_records) == 2
        assert progress_records[0] == (1, 2, "UA4000227185")
        assert progress_records[1] == (2, 2, "UA4000227193")
