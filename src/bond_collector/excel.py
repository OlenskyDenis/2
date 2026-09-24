"""Модуль для роботи з книгою Microsoft Excel (bonds.xlsx) (T016–T020)."""
from datetime import date, datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.bond_collector.interfaces import BaseStorage
from src.bond_collector.models import Bond, CashFlowEvent, CashFlowType


class ExcelFileLockedError(Exception):
    """Помилка доступу: файл Excel заблоковано іншим процесом."""
    pass


HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)

SHEET_CURRENT = "Актуальні котирування"
SHEET_HISTORY = "Історія котирувань"
SHEET_CASHFLOWS = "Графік виплат"

HEADERS_CURRENT = [
    "ISIN",
    "Назва",
    "Валюта",
    "Дата погашення",
    "Днів до погашення",
    "Військова облігація",
    "Вітрина сайту",
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

HEADERS_HISTORY = [
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

HEADERS_CASHFLOWS = [
    "ISIN",
    "Валюта",
    "Дата виплати",
    "Тип виплати",
    "Сума виплати на 1 папір",
    "Статус виплати",
]


class ExcelStorage(BaseStorage):
    """Сховище для збереження та неруйнівного оновлення реєстру облігацій в Excel."""

    def exists(self, filepath: Path) -> bool:
        """Перевіряє існування цільового файлу Excel."""
        return Path(filepath).is_file()

    def _create_initial_workbook(self) -> openpyxl.Workbook:
        """Створює нову робочу книгу з трьома аркушами та відформатованими заголовками."""
        wb = openpyxl.Workbook()

        # Перший аркуш
        ws_curr = wb.active
        ws_curr.title = SHEET_CURRENT
        ws_curr.append(HEADERS_CURRENT)

        # Другий аркуш
        ws_hist = wb.create_sheet(title=SHEET_HISTORY)
        ws_hist.append(HEADERS_HISTORY)

        # Третій аркуш
        ws_cash = wb.create_sheet(title=SHEET_CASHFLOWS)
        ws_cash.append(HEADERS_CASHFLOWS)

        for ws in (ws_curr, ws_hist, ws_cash):
            ws.row_dimensions[1].height = 26
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
                cell.alignment = HEADER_ALIGNMENT

        return wb

    def _update_current_quotes(self, ws: Any, bonds: List[Bond]) -> None:
        """Оновлює або додає котирування на аркуші 'Актуальні котирування' (upsert)."""
        existing_rows: Dict[str, int] = {}
        for r in range(2, ws.max_row + 1):
            isin_val = ws.cell(row=r, column=1).value
            if isin_val:
                existing_rows[str(isin_val).strip()] = r

        incoming_isins = set()

        for bond in bonds:
            incoming_isins.add(bond.isin)
            row_idx = existing_rows.get(bond.isin)

            row_data = [
                bond.isin,
                bond.name,
                bond.currency,
                bond.maturity_date.strftime("%Y-%m-%d"),
                bond.days_to_maturity,
                "Так" if bond.is_military else "Ні",
                bond.showcase_status,
                bond.price_buy,
                (bond.rate_buy / 100.0) if bond.rate_buy is not None else None,
                bond.price_sell,
                (bond.rate_sell / 100.0) if bond.rate_sell is not None else None,
                bond.available_qty,
                bond.availability_status,
                bond.min_amount,
                bond.max_amount,
                bond.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]

            if row_idx:
                for c_idx, val in enumerate(row_data, start=1):
                    ws.cell(row=row_idx, column=c_idx, value=val)
            else:
                ws.append(row_data)
                existing_rows[bond.isin] = ws.max_row

        # Зняті випуски не видаляються, а позначаються як "Знято з торгів / Погашено"
        for isin, r_idx in existing_rows.items():
            if isin not in incoming_isins and bonds:
                ws.cell(row=r_idx, column=13, value="Знято з торгів / Погашено")

    def _update_quote_history(self, ws: Any, bonds: List[Bond]) -> None:
        """Додає або оновлює історичний зріз із дедуплікацією за поточний день."""
        # Карта (isin, date_str) -> row_index
        history_map: Dict[Tuple[str, str], int] = {}
        for r in range(2, ws.max_row + 1):
            ts_val = ws.cell(row=r, column=1).value
            isin_val = ws.cell(row=r, column=2).value
            if ts_val and isin_val:
                date_str = str(ts_val)[:10]
                history_map[(str(isin_val).strip(), date_str)] = r

        for bond in bonds:
            today_str = bond.updated_at.strftime("%Y-%m-%d")
            key = (bond.isin, today_str)

            row_data = [
                bond.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                bond.isin,
                bond.currency,
                bond.price_buy,
                (bond.rate_buy / 100.0) if bond.rate_buy is not None else None,
                bond.price_sell,
                (bond.rate_sell / 100.0) if bond.rate_sell is not None else None,
                bond.available_qty,
                bond.availability_status,
            ]

            if key in history_map:
                row_idx = history_map[key]
                # Перевіряємо, чи змінилися ціни або кількість
                prev_buy = ws.cell(row=row_idx, column=4).value
                prev_sell = ws.cell(row=row_idx, column=6).value
                prev_qty = ws.cell(row=row_idx, column=8).value

                curr_buy = row_data[3]
                curr_sell = row_data[5]
                curr_qty = row_data[7]

                # Якщо є зміни, оновлюємо запис за цей день актуальними даними
                if (prev_buy != curr_buy) or (prev_sell != curr_sell) or (prev_qty != curr_qty):
                    for c_idx, val in enumerate(row_data, start=1):
                        ws.cell(row=row_idx, column=c_idx, value=val)
                # Якщо змін немає, рядок не дублюється
            else:
                ws.append(row_data)
                history_map[key] = ws.max_row

    def _update_cashflows(self, ws: Any, bonds: List[Bond]) -> None:
        """Синхронізує графік виплат за складеним ключем (ISIN + Дата + Тип)."""
        existing_ops: Dict[Tuple[str, str, str], int] = {}
        for r in range(2, ws.max_row + 1):
            isin_val = ws.cell(row=r, column=1).value
            dt_val = ws.cell(row=r, column=3).value
            type_val = ws.cell(row=r, column=4).value
            if isin_val and dt_val and type_val:
                key = (str(isin_val).strip(), str(dt_val)[:10], str(type_val).strip())
                existing_ops[key] = r

        for bond in bonds:
            for event in bond.cash_flows:
                date_str = event.payment_date.strftime("%Y-%m-%d")
                ev_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
                key = (bond.isin, date_str, ev_type_str)

                row_data = [
                    event.isin,
                    event.currency,
                    date_str,
                    ev_type_str,
                    event.amount,
                    event.status,
                ]

                if key in existing_ops:
                    row_idx = existing_ops[key]
                    ws.cell(row=row_idx, column=5, value=event.amount)
                    ws.cell(row=row_idx, column=6, value=event.status)
                else:
                    ws.append(row_data)
                    existing_ops[key] = ws.max_row

    def _apply_formatting_and_autofilters(self, wb: openpyxl.Workbook) -> None:
        """Встановлює автофільтри, стилі та числові формати на всіх аркушах."""
        for ws in wb.worksheets:
            max_r = max(1, ws.max_row)
            max_c = max(1, ws.max_column)

            # Активація AutoFilter
            col_letter = get_column_letter(max_c)
            ws.auto_filter.ref = f"A1:{col_letter}{max_r}"

            # Підлаштування ширини колонок
            for col in ws.columns:
                col_letter = get_column_letter(col[0].column)
                max_len = 0
                for cell in col:
                    val_str = str(cell.value or "")
                    if len(val_str) > max_len:
                        max_len = len(val_str)
                ws.column_dimensions[col_letter].width = max(12, min(max_len + 3, 40))

            # Формати числових та відсоткових осередків
            if ws.title == SHEET_CURRENT:
                for r in range(2, max_r + 1):
                    ws.cell(row=r, column=5).number_format = "#,##0"  # Днів
                    ws.cell(row=r, column=7).number_format = "#,##0.00"  # Ціна купівлі
                    ws.cell(row=r, column=8).number_format = "0.00%"  # Дохідність купівлі
                    ws.cell(row=r, column=9).number_format = "#,##0.00"  # Ціна викупу
                    ws.cell(row=r, column=10).number_format = "0.00%"  # Дохідність викупу
                    ws.cell(row=r, column=11).number_format = "#,##0"  # Залишок шт
            elif ws.title == SHEET_HISTORY:
                for r in range(2, max_r + 1):
                    ws.cell(row=r, column=4).number_format = "#,##0.00"
                    ws.cell(row=r, column=5).number_format = "0.00%"
                    ws.cell(row=r, column=6).number_format = "#,##0.00"
                    ws.cell(row=r, column=7).number_format = "0.00%"
                    ws.cell(row=r, column=8).number_format = "#,##0"
            elif ws.title == SHEET_CASHFLOWS:
                for r in range(2, max_r + 1):
                    ws.cell(row=r, column=5).number_format = "#,##0.00"

    def save(self, bonds: List[Bond], filepath: Path) -> None:
        """Транзакційне збереження даних через тимчасовий файл .tmp з атомарною заміною."""
        target_path = Path(filepath).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_name(f".{target_path.name}.tmp")

        if self.exists(target_path):
            wb = openpyxl.load_workbook(target_path)
        else:
            wb = self._create_initial_workbook()

        # Оновлення вмісту аркушів
        self._update_current_quotes(wb[SHEET_CURRENT], bonds)
        self._update_quote_history(wb[SHEET_HISTORY], bonds)
        self._update_cashflows(wb[SHEET_CASHFLOWS], bonds)

        # Застосування стилів та фільтрів
        self._apply_formatting_and_autofilters(wb)

        try:
            # Збереження у тимчасовий файл
            wb.save(tmp_path)

            # Атомарне перейменування
            os.replace(tmp_path, target_path)

        except PermissionError as e:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise ExcelFileLockedError(
                f"Файл '{target_path.name}' заблоковано іншою програмою (ймовірно, відкрито в Microsoft Excel). "
                f"Будь ласка, закрийте файл та повторіть спробу."
            ) from e
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise
