"""Інтеграційні тести транзакційності та блокування файлу Excel (T015)."""
import os
from pathlib import Path
import pytest

from src.bond_collector.excel import ExcelFileLockedError, ExcelStorage
from src.bond_collector.models import Bond


@pytest.mark.integration
class TestFileLockingAndAtomicity:
    """Тестування захисту від пошкодження файлу та блокування процесом Excel."""

    def test_tmp_file_cleaned_up_on_successful_save(self, tmp_path: Path):
        file_path = tmp_path / "bonds.xlsx"
        tmp_file = file_path.with_name(f".{file_path.name}.tmp")
        storage = ExcelStorage()

        storage.save([], file_path)
        assert file_path.exists()
        assert not tmp_file.exists()

    def test_permission_error_leaves_original_file_intact(self, tmp_path: Path, monkeypatch):
        file_path = tmp_path / "bonds.xlsx"
        storage = ExcelStorage()

        # Початковий валідний файл
        storage.save([], file_path)
        original_size = file_path.stat().st_size
        assert original_size > 0

        # Симулюємо блокування файлу при спробі заміни через os.replace
        def mock_replace(src, dst):
            raise PermissionError("[WinError 32] Процес не може отримати доступ до файлу")

        monkeypatch.setattr(os, "replace", mock_replace)

        with pytest.raises(ExcelFileLockedError, match="заблоковано"):
            storage.save([], file_path)

        # Оригінальний файл не пошкоджено
        assert file_path.exists()
        assert file_path.stat().st_size == original_size

        # Тимчасовий файл видалено
        tmp_file = file_path.with_name(f".{file_path.name}.tmp")
        assert not tmp_file.exists()
