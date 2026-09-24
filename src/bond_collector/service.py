"""Сервіс координації збору даних та агрегації котирувань облігацій (T012)."""
from datetime import datetime
import logging
from typing import Callable, List, Optional

from src.bond_collector.interfaces import BaseBondSource
from src.bond_collector.models import Bond

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


class CollectorService:
    """Сервіс для пакетного збору ринкових даних, залишків та календарів виплат."""

    def __init__(self, source: BaseBondSource):
        self.source = source

    def collect_all(self, progress_callback: Optional[ProgressCallback] = None) -> List[Bond]:
        """Виконує повний цикл збору даних для всіх доступних облігацій джерела.

        Підтримує принцип часткової відмовостійкості (Graceful degradation):
        тимчасовий збій для окремого паперу фіксується як попередження, не перериваючи
        обробку решти випусків.
        """
        bonds = self.source.fetch_bonds()
        total = len(bonds)
        if total == 0:
            logger.info("Джерело повернуло порожній список облігацій (торги закрито).")
            return []

        for idx, bond in enumerate(bonds):
            try:
                # Отримання залишків та лімітів
                try:
                    limits = self.source.fetch_limits(bond.isin)
                    bond.available_qty = int(limits.get("count", 0))
                    bond.min_amount = limits.get("minAmount", 1)
                    bond.max_amount = limits.get("maxAmount")
                    bond.is_active = bool(limits.get("active", False))
                except Exception as lim_err:
                    logger.warning(f"Помилка отримання лімітів для {bond.isin}: {lim_err}")
                    bond.available_qty = 0
                    bond.is_active = False

                # Отримання графіку купонних виплат та погашення
                try:
                    operations = self.source.fetch_operations(bond.isin)
                    bond.cash_flows = operations
                except Exception as ops_err:
                    logger.warning(f"Помилка отримання графіка виплат для {bond.isin}: {ops_err}")
                    bond.cash_flows = []

                bond.updated_at = datetime.now()

            except Exception as e:
                logger.error(f"Неочікувана помилка при обробці облігації {bond.isin}: {e}")

            if progress_callback:
                progress_callback(idx + 1, total, bond.isin)

        return bonds
