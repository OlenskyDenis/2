"""Базові інтерфейси та абстракції джерел даних та сховища (Library-First)."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from src.bond_collector.models import Bond, CashFlowEvent


class BaseBondSource(ABC):
    """Абстрактне джерело котирувань та ринкових даних облігацій."""

    @abstractmethod
    def fetch_bonds(self) -> List[Bond]:
        """Отримує список усіх доступних облігацій з базовими котируваннями."""
        raise NotImplementedError

    @abstractmethod
    def fetch_limits(self, isin: str) -> Dict[str, Any]:
        """Отримує залишки у продажу та ліміти сум для вказаного ISIN."""
        raise NotImplementedError

    @abstractmethod
    def fetch_operations(self, isin: str) -> List[CashFlowEvent]:
        """Отримує календарний графік виплат (купони, погашення) для вказаного ISIN."""
        raise NotImplementedError


class BaseStorage(ABC):
    """Абстрактне сховище (персистентний шар) для збереження даних облігацій."""

    @abstractmethod
    def save(self, bonds: List[Bond], filepath: Path) -> None:
        """Зберігає або синхронізує колекцію облігацій у вказаний файл."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, filepath: Path) -> bool:
        """Перевіряє наявність файлу сховища."""
        raise NotImplementedError
