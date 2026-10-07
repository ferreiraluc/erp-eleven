"""Synthetic regression: an explicit sale date can cross its workbook month."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Usuario, Vendedor
from app.models.usuario import UsuarioRole
from app.models.sales_bi import SalesBIWorkbook
from app.services.assistant_sales_bi import SpreadsheetSalesArgs, query_spreadsheet_sales
from app.services.sales_bi_entries import build_entries
from app.api.endpoints import sales_bi_entries
from test_access import setup, login


def boundary_book(*, year=2026, month=9, day="2026-10-01", key="boundary", kind="archive"):
    rows = [{"sheet": "semana5", "row": index + 12, "source_cell": f"semana5!C{index + 12}",
             "week_index": 5, "week_label": "Synthetic boundary week", "seller": name, "currency": "BRL",
             "gross": amount, "net": amount, "payment_method": "PIX", "customer": "Synthetic customer",
             "date": day, "time": "09:30:00" if day else None, "day_group": None}
            for index, (name, amount) in enumerate((("Junior", "10"), ("Lucas", "900")))]
    return SalesBIWorkbook(id=key, filename="Synthetic.xlsx", kind=kind, year=year, month=month,
        remote_version="1", active=True, synced_at=datetime(2026, 10, 1, 21, tzinfo=timezone.utc),
        snapshot={"total_usd": "1000", "source_cell": "total mes!C8", "warnings": [], "weeks": [],
                  "sellers": {"Junior": {"total_usd": "100", "currencies": {"BRL": "10"}},
                              "Lucas": {"total_usd": "900", "currencies": {"BRL": "900"}}},
                  "entries": {"rows": rows, "diagnostics": []}})


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("source_year,source_month,day", [(2026, 9, "2026-10-01"), (2025, 12, "2026-01-01")])
def test_bot_explicit_day_keeps_dated_rows_from_a_week_crossing_the_workbook_month(private, source_year, source_month, day):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[model.__table__ for model in (Usuario, Vendedor, SalesBIWorkbook)])
    factory = sessionmaker(bind=engine)
    try:
        with factory() as db:
            user = Usuario(nome="Synthetic Junior", email="fixture@example.com", senha_hash="unused",
                           role=UsuarioRole.GERENTE, ativo=True, sales_scope="own" if private else "all", sales_seller="Junior")
            db.add(user)
            source = boundary_book(year=source_year, month=source_month, day=day)
            db.add(source)
            db.commit()
            # The observation is real and a date-only row lookup already finds it.
            observed = build_entries([source], seller="Junior", day=day)
            assert observed["summary"]["count"] == 1
            assert observed["summary"]["currencies"][0]["net"] == 10

            result = query_spreadsheet_sales(db, SpreadsheetSalesArgs(
                visao="por_hora", dia=day, vendedor="Lucas" if private else "Junior"), user.id)
            assert result["totais_observados"]["count"] == 1
            assert result["resultados"] == [{"hour": 9, "count": 1, "currencies": [
                {"currency": "BRL", "count": 1, "gross": 10.0, "net": 10.0, "net_available": 1}]}]
            assert result["fechamento_corrigido"]["total_usd"] is None
            assert result["conferencia_mensal"]["resultados"] == []
            assert result["cobertura"]["source_count"] == 1
            assert result["origem"]["fontes_no_periodo"] == 1
            assert result["fechamento_corrigido"]["source_months"] == 0
            assert result["origem"]["fontes_com_pendencia"] == 0
            assert result["origem"]["snapshot_mais_recente_em"].startswith("2026-10-01T21:00:00")
            assert not db.dirty and not db.new
    finally:
        engine.dispose()


@pytest.mark.parametrize("account,expected_count,expected_gross", [("Junior", 1, 10), ("Wissam", 2, 910)])
def test_authenticated_api_day_overrides_workbook_prefilter_but_keeps_personal_scope(setup, account, expected_count, expected_gross):
    client, factory, _ = setup
    client.app.include_router(sales_bi_entries.router, prefix="/api/sales-bi")
    with factory() as db:
        # Month and year both differ; no SQL prefilter may remove the source.
        source = boundary_book(year=2025, month=12, day="2026-01-01")
        source.snapshot["entries"]["rows"][1]["currency"] = "USD"
        source.snapshot["entries"]["rows"][1]["date"] = "2026-01-02"
        db.add(source)
        db.commit()
    assert client.get("/api/sales-bi/entries?day=2026-01-01").status_code == 401
    headers = login(client, account)
    query = "?year=2026&month=1&day=2026-01-01&limit=1"
    if account == "Junior":
        query += "&seller=Lucas"  # forged filter cannot change the authenticated seller
    result = client.get("/api/sales-bi/entries" + query, headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["total"] == body["summary"]["count"] == 1
    assert body["summary"]["currencies"] == [{"currency": "BRL", "count": 1, "gross": 10, "net": 10, "net_available": 1}]
    assert body["summary"]["official_total_usd"] is None and body["reconciliation"] == []
    assert body["items"][0]["year"] == 2025 and body["items"][0]["month"] == 12
    assert body["daily"][0]["date"] == "2026-01-01" and body["hourly"][0]["count"] == 1
    if account == "Junior":
        assert "Lucas" not in result.text and "900" not in result.text
        assert body["sellers"] == ["Junior"] and body["currencies"] == ["BRL"]
        assert body["dates"] == ["2026-01-01"]
    else:
        assert body["sellers"] == ["Junior", "Lucas"]
    # Removing day still selects the requested workbook period, as before.
    monthly = client.get("/api/sales-bi/entries?year=2025&month=12", headers=headers).json()
    assert monthly["total"] == expected_count
    assert sum(row["gross"] for row in monthly["summary"]["currencies"]) == expected_gross
    assert monthly["summary"]["official_total_usd"] == (100 if account == "Junior" else 1000)


def test_day_search_excludes_undated_rows_deduplicates_snapshot_sources_and_keeps_monthly_reconciliation():
    prior = boundary_book()
    current_copy = boundary_book(key="current-copy", kind="current")
    current_copy.snapshot["entries"]["rows"][0]["gross"] = "99999"
    selected_month = boundary_book(year=2026, month=10, day=None, key="october")
    selected_month.snapshot["sellers"]["Junior"]["currencies"]["BRL"] = "7"
    stale_source = boundary_book(year=2026, month=8, key="older")
    stale_source.snapshot.pop("entries")
    sources = [prior, current_copy, selected_month, stale_source]
    before = deepcopy([row.snapshot for row in sources])

    monthly = build_entries(sources, year=2026, month=10, seller="Junior")
    daily = build_entries(sources, year=2026, month=10, seller="Junior", day="2026-10-01", offset=0, limit=1, private=True)
    assert daily["total"] == daily["summary"]["count"] == 1
    assert daily["items"][0]["source_id"] == "boundary"
    assert daily["summary"]["currencies"][0]["gross"] == 10
    assert daily["summary"]["official_total_usd"] == monthly["summary"]["official_total_usd"] == 100
    assert daily["reconciliation"] == monthly["reconciliation"] == [{"year": 2026, "month": 10, "currency": "BRL", "published": 7.0, "observed_net": 10.0, "difference": 3.0}]
    assert daily["coverage"] == {"source_count": 3, "needs_sync": True, "sources_without_entries": 1, "skipped_rows": None, "undated_excluded": 1}
    assert monthly["coverage"]["source_count"] == 1 and monthly["summary"]["undated_count"] == 1
    assert [row.snapshot for row in sources] == before


def test_equal_dated_sales_in_different_selected_workbooks_remain_distinct_before_pagination():
    first = boundary_book()
    second = boundary_book(year=2026, month=10, key="other-month")
    # These equal real observations are not a live/archive copy of one monthly source.
    result = build_entries([first, second], year=2026, month=10, seller="Junior", day="2026-10-01", offset=1, limit=1)
    assert result["total"] == result["summary"]["count"] == 2
    assert result["summary"]["currencies"][0]["gross"] == 20
    assert len(result["items"]) == 1
    assert result["daily"][0]["count"] == result["hourly"][0]["count"] == 2
    first_page = build_entries([first, second], year=2026, month=10, seller="Junior", day="2026-10-01", limit=1)
    assert first_page["items"][0]["id"] != result["items"][0]["id"]


def test_bot_day_origin_reports_examined_fresh_and_stale_sources_but_closing_stays_monthly(setup):
    _, factory, ids = setup
    with factory() as db:
        old_month = boundary_book()
        old_month.synced_at = datetime(2026, 9, 30, 20, tzinfo=timezone.utc)
        old_month.error = "SYNTHETIC_STALE_DETAIL"
        this_month = boundary_book(month=10, day=None, key="closing-month")
        this_month.synced_at = datetime(2026, 10, 2, 21, tzinfo=timezone.utc)
        ignored_copy = boundary_book(kind="current", key="ignored-copy")
        ignored_copy.synced_at = datetime(2026, 10, 3, 22, tzinfo=timezone.utc)
        db.add_all([old_month, this_month, ignored_copy])
        db.commit()

        daily = query_spreadsheet_sales(db, SpreadsheetSalesArgs(dia="2026-10-01"), ids["Junior"][0])
        origin = daily["origem"]
        assert origin["fontes_no_periodo"] == daily["cobertura"]["source_count"] == 2
        assert origin["fontes_com_pendencia"] == 1
        assert origin["snapshot_mais_antigo_em"].startswith("2026-09-30T20:00:00")
        assert origin["snapshot_mais_recente_em"].startswith("2026-10-02T21:00:00")
        assert "data explícita" in origin["criterio_fontes"]
        assert daily["fechamento_corrigido"]["source_months"] == 1
        assert daily["fechamento_corrigido"]["total_usd"] == 100
        assert daily["resultados"][0]["snapshot_com_pendencia"] is True
        assert daily["cobertura_datas_no_periodo"]["undated_count"] == 1
        assert "SYNTHETIC_STALE_DETAIL" not in str(daily)

        monthly = query_spreadsheet_sales(db, SpreadsheetSalesArgs(ano=2026, mes=10), ids["Junior"][0])
        assert monthly["origem"]["fontes_no_periodo"] == 1
        assert monthly["origem"]["fontes_com_pendencia"] == 0
        assert monthly["origem"]["snapshot_mais_antigo_em"] == monthly["origem"]["snapshot_mais_recente_em"]
