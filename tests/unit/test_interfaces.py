"""Тести базових інтерфейсів та протоколів (T006)."""
from pathlib import Path
from typing import List
import pytest

from src.bond_collector.interfaces import BaseBondSource, BaseStorage
from src.bond_collector.models import Bond


@pytest.mark.unit
class TestInterfaces:
    """Перевірка абстрактних методів інтерфейсів джерел та сховища."""

    def test_base_bond_source_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseBondSource()

    def test_base_storage_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseStorage()

    def test_concrete_source_implementation(self):
        class DummySource(BaseBondSource):
            def fetch_bonds(self) -> List[Bond]:
                return []

            def fetch_limits(self, isin: str) -> dict:
                return {"isin": isin, "count": 100}

            def fetch_operations(self, isin: str) -> list:
                return []

        source = DummySource()
        assert source.fetch_bonds() == []
        assert source.fetch_limits("UA4000227185")["count"] == 100

    def test_concrete_storage_implementation(self, tmp_path: Path):
        class DummyStorage(BaseStorage):
            def save(self, bonds: List[Bond], filepath: Path) -> None:
                filepath.write_text("dummy", encoding="utf-8")

            def exists(self, filepath: Path) -> bool:
                return filepath.exists()

        storage = DummyStorage()
        target_file = tmp_path / "test.xlsx"
        assert not storage.exists(target_file)
        storage.save([], target_file)
        assert storage.exists(target_file)
