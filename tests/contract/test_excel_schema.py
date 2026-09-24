"""Контрактні тести структури книги Excel (bonds.xlsx) (T013)."""
from pathlib import Path
import openpyxl
import pytest

from src.bond_collector.excel import ExcelStorage
from src.bond_collector.models import Bond


@pytest.mark.contract
class TestExcelSchemaContract:
    """Перевірка наявності 3 аркушів, точних назв та порядку колонок, а також автофільтрів."""

    def test_excel_workbook_structure_and_headers(self, tmp_path: Path):
        file_path = tmp_path / "test_bonds.xlsx"
        storage = ExcelStorage()
        storage.save([], file_path)

        wb = openpyxl.load_workbook(file_path)
        sheet_names = wb.sheetnames

        # Перевірка наявності трьох обов'язкових аркушів
        assert "Актуальні котирування" in sheet_names
        assert "Історія котирувань" in sheet_names
        assert "Графік виплат" in sheet_names

        # Перевірка 15 колонок для «Актуальні котирування»
        ws_current = wb["Актуальні котирування"]
        current_headers = [cell.value for cell in ws_current[1]]
        expected_current = [
            "ISIN",
            "Назва",
            "Валюта",
            "Дата погашення",
            "Днів до погашення",
            "Військова облігація",
            "Ціна купівлі (з НКД)",
            "Дохідність купівлі (% річних)",
            "Ціна зворотного викупу банком",
            "Дохідність викупу (% річних)",
            "Залишок у наявності (шт.)",
            "Статус продажу",
            "Мін. сума угоди",
            "Макс. сума угоди",
            "Час останнього зрізу",
        ]
        assert current_headers == expected_current

        # Перевірка наявності активованого автофільтра
        assert ws_current.auto_filter.ref is not None

        # Перевірка 9 колонок для «Історія котирувань»
        ws_history = wb["Історія котирувань"]
        history_headers = [cell.value for cell in ws_history[1]]
        expected_history = [
            "Час зрізу",
            "ISIN",
            "Валюта",
            "Ціна купівлі",
            "Дохідність купівлі (%)",
            "Ціна зворотного викупу",
            "Дохідність викупу (%)",
            "Залишок у наявності (шт.)",
            "Статус продажу",
        ]
        assert history_headers == expected_history
        assert ws_history.auto_filter.ref is not None

        # Перевірка 6 колонок для «Графік виплат»
        ws_cashflow = wb["Графік виплат"]
        cashflow_headers = [cell.value for cell in ws_cashflow[1]]
        expected_cashflow = [
            "ISIN",
            "Валюта",
            "Дата виплати",
            "Тип виплати",
            "Сума виплати на 1 папір",
            "Статус виплати",
        ]
        assert cashflow_headers == expected_cashflow
        assert ws_cashflow.auto_filter.ref is not None
