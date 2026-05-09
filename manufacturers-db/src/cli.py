"""Command-line entry point.

Usage:
    mdb init-db
    mdb ingest gleif --country KZ --limit 10000
    mdb normalize gleif
    mdb ingest sec --limit 100
    mdb normalize sec
    mdb trade --years 2022 2023 2024
    mdb export manufacturers_basic
    mdb export-list
"""

from pathlib import Path

import typer

from src.connectors.gleif import GLEIFConnector
from src.connectors.sec_edgar import SECEdgarConnector
from src.connectors.un_comtrade import UNComtradeConnector
from src.export.csv import list_views, run_export
from src.logging_config import configure_logging, get_logger
from src.normalize.gleif import GLEIFNormalizer
from src.normalize.sec_edgar import SECEdgarNormalizer

configure_logging()
log = get_logger(__name__)

app = typer.Typer(help="Manufacturers DB pipeline.", no_args_is_help=True)

CONNECTORS = {
    "gleif": GLEIFConnector,
    "sec": SECEdgarConnector,
}
NORMALIZERS = {
    "gleif": GLEIFNormalizer,
    "sec": SECEdgarNormalizer,
}


@app.command("init-db")
def init_db() -> None:
    """Create schema by running sql/schema.sql against the configured database."""
    from sqlalchemy import text as sql_text

    from src.db import get_connection

    schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    with get_connection() as conn:
        for stmt in _split_sql(sql):
            if stmt.strip():
                conn.execute(sql_text(stmt))
    typer.echo(f"Schema applied from {schema_path}")


@app.command("ingest")
def ingest(
    source: str = typer.Argument(..., help=f"One of: {', '.join(CONNECTORS)}"),
    country: str | None = typer.Option(None, help="ISO 3166-1 alpha-2 (GLEIF only)"),
    limit: int | None = typer.Option(None, help="Stop after N records"),
) -> None:
    """Fetch raw records from a source and store in entity_sources."""
    cls = CONNECTORS.get(source)
    if not cls:
        raise typer.BadParameter(f"Unknown source. Choices: {list(CONNECTORS)}")
    kwargs: dict = {}
    if country:
        kwargs["country"] = country
    if limit:
        kwargs["limit"] = limit
    n = cls().ingest(**kwargs)
    typer.echo(f"Ingested {n} records from {source}")


@app.command("normalize")
def normalize(
    source: str = typer.Argument(..., help=f"One of: {', '.join(NORMALIZERS)}"),
) -> None:
    """Map raw rows for a source into the canonical schema."""
    cls = NORMALIZERS.get(source)
    if not cls:
        raise typer.BadParameter(f"Unknown source. Choices: {list(NORMALIZERS)}")
    n = cls().normalize_all()
    typer.echo(f"Normalized {n} records from {source}")


@app.command("trade")
def trade(
    years: list[int] = typer.Option(..., "--years", help="Years to fetch"),
    reporter: str = typer.Option("all", help="M49 reporter code or 'all'"),
    flow: str = typer.Option("M", help="M=imports, X=exports"),
) -> None:
    """Fetch UN Comtrade aggregate trade flows."""
    n = UNComtradeConnector().fetch_and_store(
        years=years, reporter=reporter, flow=flow
    )
    typer.echo(f"Stored {n} trade rows")


@app.command("export")
def export(
    view: str = typer.Argument(..., help="Name of the SQL view in sql/exports/"),
    output: Path | None = typer.Option(None, help="Output CSV path"),
) -> None:
    """Run an export view and write the result to CSV."""
    path = run_export(view, output)
    typer.echo(f"Wrote {path}")


@app.command("export-list")
def export_list() -> None:
    """List available export views."""
    for v in list_views():
        typer.echo(v)


def _split_sql(sql: str) -> list[str]:
    """Naive SQL splitter — splits on ';' at end of line."""
    out: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        buf.append(line)
        if line.rstrip().endswith(";"):
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out


if __name__ == "__main__":
    app()
