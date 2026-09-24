"""Тести модульних точок розширення та заглушок під майбутні цикли (T024)."""
import pytest

from src.bond_collector.interfaces import BaseBondSource
from src.bond_collector.models import Bond
from src.bond_collector.stubs import (
    MultiBrokerAdapter,
    SchedulerStub,
    YieldCalculatorStub,
)


@pytest.mark.unit
class TestStubsAndExtensibility:
    """Перевірка точок розширення для майбутніх циклів (FR-008)."""

    def test_multi_broker_adapter_registration(self):
        class DummySource(BaseBondSource):
            def fetch_bonds(self):
                return []

            def fetch_limits(self, isin: str):
                return {}

            def fetch_operations(self, isin: str):
                return []

        adapter = MultiBrokerAdapter()
        adapter.register_source("mono", DummySource())
        assert "mono" in adapter.list_sources()

    def test_scheduler_stub_status(self):
        scheduler = SchedulerStub()
        info = scheduler.schedule(interval_minutes=60, callback=lambda: None)
        assert "наступному циклі" in info

    def test_yield_calculator_stub_status(self):
        calc = YieldCalculatorStub()
        res = calc.calculate_effective_yield("UA4000227185", price=1050.0)
        assert "наступному циклі" in res
