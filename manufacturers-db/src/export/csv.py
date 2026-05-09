"""Run a SQL view from sql/exports/ and stream the result to a CSV file."""

import csv
from pathlib import Path

from sqlalchemy import text

from src.db import get_connection
from src.logging_config import get_logger
from src.settings import settings

log = get_logger(__name__)

EXPORTS_DIR = Path(__file__).resolve().parents[2] / "sql" / "exports"


def list_views() -> list[str]:
    return sorted(p.stem for p in EXPORTS_DIR.glob("*.sql"))


def run_export(view_name: str, output_path: Path | None = None) -> Path:
    sql_path = EXPORTS_DIR / f"{view_name}.sql"
    if not sql_path.exists():
        raise FileNotFoundError(
            f"No export view '{view_name}'. Available: {list_views()}"
        )

    sql = sql_path.read_text(encoding="utf-8")

    out = output_path or (settings.export_dir / f"{view_name}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    log.info("export.start", view=view_name, output=str(out))

    rows_written = 0
    with get_connection() as conn, out.open("w", newline="", encoding="utf-8") as fh:
        # server-side cursor for memory-friendly streaming
        result = conn.execution_options(stream_results=True).execute(text(sql))
        writer = csv.writer(fh)
        writer.writerow(result.keys())
        for row in result:
            writer.writerow(["" if v is None else v for v in row])
            rows_written += 1
            if rows_written % 10000 == 0:
                log.info("export.progress", view=view_name, rows=rows_written)

    log.info("export.done", view=view_name, rows=rows_written, path=str(out))
    return out
