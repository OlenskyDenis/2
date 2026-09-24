"""Модульні заглушки та інтерфейси розширення під майбутні цикли (FR-008, T025)."""
from typing import Any, Callable, Dict, List, Optional

from src.bond_collector.interfaces import BaseBondSource
from src.bond_collector.models import Bond, CashFlowEvent


class MultiBrokerAdapter(BaseBondSource):
    """Адаптер для агрегації кількох брокерських або банківських джерел даних."""

    def __init__(self):
        self._sources: Dict[str, BaseBondSource] = {}

    def register_source(self, name: str, source: BaseBondSource) -> None:
        """Реєструє нове джерело котирувань."""
        self._sources[name] = source

    def list_sources(self) -> List[str]:
        """Повертає перелік зареєстрованих джерел."""
        return list(self._sources.keys())

    def fetch_bonds(self) -> List[Bond]:
        """Агрегує облігації з усіх зареєстрованих джерел."""
        all_bonds: List[Bond] = []
        for source in self._sources.values():
            all_bonds.extend(source.fetch_bonds())
        return all_bonds

    def fetch_limits(self, isin: str) -> Dict[str, Any]:
        """Запитує ліміти у першого джерела, де знайдено папір."""
        for source in self._sources.values():
            try:
                res = source.fetch_limits(isin)
                if res.get("count", 0) > 0:
                    return res
            except Exception:
                continue
        return {"isin": isin, "count": 0, "active": False}

    def fetch_operations(self, isin: str) -> List[CashFlowEvent]:
        """Запитує операції у доступних джерел."""
        for source in self._sources.values():
            try:
                ops = source.fetch_operations(isin)
                if ops:
                    return ops
            except Exception:
                continue
        return []


class SchedulerStub:
    """Заглушка модуля фонового оновлення та автоматичного опитування за розкладом."""

    def schedule(self, interval_minutes: int, callback: Callable[[], None]) -> str:
        """Реєструє завдання оновлення (заплановано на наступні цикли)."""
        return f"Планувальник з інтервалом {interval_minutes} хв. буде реалізовано в наступному циклі."


class YieldCalculatorStub:
    """Заглушка аналітичного розрахункового рушія дохідності (YTM, податки, чистий заробіток)."""

    def calculate_effective_yield(self, isin: str, price: float, tax_rate: float = 0.0) -> str:
        """Розраховує ефективну ставку дохідності (заплановано на наступні цикли)."""
        return f"Аналітичний розрахунковий модуль для {isin} буде реалізовано в наступному циклі."
