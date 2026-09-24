"""Інтеграційні тести CLI-інтерфейсу (T021)."""
from datetime import date, datetime
import json
from pathlib import Path
import pytest

from src.bond_collector.excel import ExcelFileLockedError
from src.bond_collector.models import Bond
from src.cli.main import main


@pytest.mark.integration
class TestCLIFlow:
    """Тестування виклику CLI, потоків stdout/stderr, прапорців та кодів виходу."""

    def test_cli_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "bonds.xlsx" in captured.out or "шлях" in captured.out

    def test_cli_invalid_argument(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--unrecognized-option-xyz"])
        assert exc.value.code == 2

    def test_cli_execution_with_custom_output_and_json(self, tmp_path: Path, monkeypatch, capsys):
        output_file = tmp_path / "custom.xlsx"

        # Мокуємо збір даних, щоб тест був швидким та ізольованим від мережі
        from src.bond_collector.service import CollectorService
        sample_bond = Bond(
            isin="UA4000227185",
            name="Військові облігації",
            currency="UAH",
            maturity_date=date(2027, 5, 26),
            is_military=True,
            price_buy=1050.0,
            available_qty=100,
        )
        monkeypatch.setattr(CollectorService, "collect_all", lambda self, progress_callback=None: [sample_bond])

        ret = main(["--output", str(output_file), "--json"])
        assert ret == 0
        assert output_file.exists()

        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())
        assert data["status"] == "success"
        assert data["bonds_count"] == 1
        assert data["file"] == str(output_file.resolve())

    def test_cli_handles_locked_file_to_stderr(self, tmp_path: Path, monkeypatch, capsys):
        output_file = tmp_path / "locked.xlsx"

        from src.bond_collector.service import CollectorService
        monkeypatch.setattr(CollectorService, "collect_all", lambda self, progress_callback=None: [])

        # Симулюємо помилку блокування файлу
        from src.bond_collector.excel import ExcelStorage

        def mock_save(self, bonds, filepath):
            raise ExcelFileLockedError("Файл заблоковано іншою програмою")

        monkeypatch.setattr(ExcelStorage, "save", mock_save)

        ret = main(["--output", str(output_file)])
        assert ret == 1

        captured = capsys.readouterr()
        assert "[ПОМИЛКА]" in captured.err
        assert "заблоковано" in captured.err
