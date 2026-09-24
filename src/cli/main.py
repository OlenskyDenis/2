"""Точка входу інтерфейсу командного рядка (CLI) для збору ОВДП (T022)."""
import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
import time
from typing import List, Optional

from src.bond_collector.client import Privat24Client
from src.bond_collector.excel import ExcelFileLockedError, ExcelStorage
from src.bond_collector.service import CollectorService

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Створює та налаштовує парсер аргументів командного рядка українською мовою."""
    parser = argparse.ArgumentParser(
        prog="python -m src.cli.main",
        description="Автоматизований збір ринкових котирувань, залишків та виплат ОВДП Приват24 в Excel.",
    )
    parser.add_argument(
        "excel_path",
        nargs="?",
        default=None,
        help="Шлях до цільового файлу Excel (за замовчуванням: ./bonds.xlsx)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Альтернативний прапорець для вказання шляху до файлу Excel",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Виводити машиннозчитуваний JSON-звіт у stdout замість текстового прогресу",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Виводити детальні діагностичні повідомлення у потік stderr",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Головна функція виконання CLI."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s", stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s", stream=sys.stderr)

    # Визначення цільового файлу
    raw_path = args.output or args.excel_path or "bonds.xlsx"
    target_file = Path(raw_path).resolve()

    start_time = time.time()

    def log_info(msg: str, end: str = "\n", flush: bool = False) -> None:
        if not args.json:
            sys.stdout.write(msg + end)
            if flush:
                sys.stdout.flush()

    try:
        log_info("Ініціалізація підключення до Приват24...", flush=True)
        client = Privat24Client()
        client.init_session()

        log_info("Отримання списку облігацій та опитування залишків...", flush=True)
        service = CollectorService(source=client)

        def on_progress(current: int, total: int, isin: str) -> None:
            if not args.json:
                sys.stdout.write(f"\r  - Обробка випусків: [{current}/{total}] {isin}...")
                sys.stdout.flush()

        bonds = service.collect_all(progress_callback=on_progress)
        if not args.json:
            sys.stdout.write("\n")

        log_info(f"Збереження даних у реєстр Excel: {target_file.name}...", flush=True)
        storage = ExcelStorage()
        storage.save(bonds, target_file)

        duration = time.time() - start_time
        available_count = sum(1 for b in bonds if b.available_qty > 0 and b.is_active)
        total_cashflows = sum(len(b.cash_flows) for b in bonds)

        if args.json:
            report = {
                "status": "success",
                "file": str(target_file),
                "bonds_count": len(bonds),
                "available_bonds_count": available_count,
                "cashflows_count": total_cashflows,
                "duration_seconds": round(duration, 2),
                "timestamp": datetime.now().isoformat(),
            }
            sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        else:
            log_info(
                f"Успішно завершено за {duration:.2f} сек. "
                f"Опрацьовано {len(bonds)} випусків ({available_count} в наявності), "
                f"{total_cashflows} виплат збережено у {target_file.name}."
            )

        return 0

    except ExcelFileLockedError as e:
        sys.stderr.write(f"\n[ПОМИЛКА] {e}\n")
        return 1

    except Exception as e:
        sys.stderr.write(f"\n[ПОМИЛКА] Збій під час виконання збору даних: {e}\n")
        if args.verbose:
            import traceback
            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
