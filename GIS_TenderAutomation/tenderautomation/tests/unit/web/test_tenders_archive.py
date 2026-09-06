from datetime import datetime, timedelta, timezone

import pytest

from core.models import TenderStatus
from web.app import templates
from web.routers.tenders_router import (
    TABS,
    _counts_for_rows,
    _decorate_tenders,
    _filter_search,
    _filter_tab,
    _sort_tenders,
)


NOW = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)


def _cache(*items):
    by_id = {item["tender_id"]: item for item in items}
    return {"by_id": by_id, "by_title": {}, "items": list(items)}


def _v3(tender_id: str, queue: str):
    return {
        "tender_id": tender_id,
        "queue": queue,
        "verdict": "core",
        "fit_score": 90,
        "domain": "cloud",
    }


def test_p1_excludes_expired_but_keeps_unknown(tender_factory) -> None:
    expired = tender_factory(
        id="expired", external_id="expired", deadline=NOW - timedelta(days=1)
    )
    unknown = tender_factory(id="unknown", external_id="unknown", deadline=None)
    rows = _decorate_tenders(
        [expired, unknown], _cache(_v3("expired", "P1"), _v3("unknown", "P1")), NOW
    )
    assert [row["id"] for row in _filter_tab(rows, "P1")] == ["unknown"]
    assert _counts_for_rows(rows)["P1"] == 1


def test_archive_contains_every_status_and_all_preserves_everything(tender_factory) -> None:
    tenders = [
        tender_factory(
            id=f"expired-{status.value}",
            external_id=status.value,
            deadline=NOW - timedelta(days=1),
            status=status,
        )
        for status in (TenderStatus.TAKEN, TenderStatus.DEFERRED, TenderStatus.REJECTED)
    ]
    rows = _decorate_tenders(tenders, _cache(), NOW)
    assert len(_filter_tab(rows, "archive")) == 3
    assert len(_filter_tab(rows, "all")) == 3
    assert [row["status"] for row in rows] == [tender.status for tender in tenders]


def test_archive_sorts_recently_expired_first_then_id(tender_factory) -> None:
    tenders = [
        tender_factory(id="b", external_id="b", deadline=NOW - timedelta(days=2)),
        tender_factory(id="c", external_id="c", deadline=NOW - timedelta(days=1)),
        tender_factory(id="a", external_id="a", deadline=NOW - timedelta(days=1)),
    ]
    rows = _filter_tab(_decorate_tenders(tenders, _cache(), NOW), "archive")
    assert [row["id"] for row in _sort_tenders(rows, "archive")] == ["a", "c", "b"]


def test_search_is_applied_before_counts(tender_factory) -> None:
    rows = _decorate_tenders(
        [
            tender_factory(id="cloud", title="Cloud platform", buyer="One"),
            tender_factory(id="erp", title="ERP", buyer="Two"),
        ],
        _cache(_v3("cloud", "P1"), _v3("erp", "P1")),
        NOW,
    )
    filtered = _filter_search(rows, "cloud")
    assert len(filtered) == 1
    assert _counts_for_rows(filtered)["P1"] == 1


@pytest.mark.parametrize("queue", ["P1", "P2"])
def test_rejected_tenders_leave_review_queues_but_remain_in_history(
    tender_factory,
    queue: str,
) -> None:
    statuses = (
        TenderStatus.PENDING,
        TenderStatus.TAKEN,
        TenderStatus.DEFERRED,
        TenderStatus.REJECTED,
    )
    tenders = [
        tender_factory(
            id=f"{queue}-{status.value}",
            external_id=f"{queue}-{status.value}",
            status=status,
        )
        for status in statuses
    ]
    rows = _decorate_tenders(
        tenders,
        _cache(*(_v3(tender.id, queue) for tender in tenders)),
        NOW,
    )

    expected_ids = {
        f"{queue}-pending",
        f"{queue}-taken",
        f"{queue}-deferred",
    }
    assert {row["id"] for row in _filter_tab(rows, queue)} == expected_ids
    assert {row["id"] for row in _filter_tab(rows, "active")} == expected_ids
    assert _counts_for_rows(rows)[queue] == 3
    assert _counts_for_rows(rows)["active"] == 3
    assert [row["id"] for row in _filter_tab(rows, "rejected")] == [
        f"{queue}-rejected"
    ]
    assert len(_filter_tab(rows, "all")) == 4


def test_archive_tab_and_stable_selectors_render() -> None:
    assert ("archive", "🗄 Архив") in TABS
    html = templates.env.get_template("tenders/list.html").render(
        tabs=TABS,
        filters={"tab": "archive", "platform": None, "search": ""},
        counts={"archive": 2},
        tenders=[],
        total_count=2,
        last_collection={"at": "", "new_count": 0},
        page=1,
        has_next=False,
    )
    assert 'data-testid="tenders-tab-archive"' in html
    assert 'data-testid="tenders-tab-P1"' in html
    assert "Архив" in html


def _render_tender_list(tab: str, tender) -> str:
    row = _decorate_tenders(
        [tender],
        _cache(_v3(tender.id, "P1")),
        NOW,
    )[0]
    return templates.env.get_template("tenders/list.html").render(
        tabs=TABS,
        filters={"tab": tab, "platform": None, "search": ""},
        counts={tab: 1},
        tenders=[row],
        total_count=1,
        last_collection={"at": "", "new_count": 0},
        page=1,
        has_next=False,
    )


@pytest.mark.parametrize("tab", ["active", "P1", "P2"])
@pytest.mark.parametrize(
    ("status", "label"),
    [
        (TenderStatus.TAKEN, "Взято"),
        (TenderStatus.REJECTED, "Отклонено"),
        (TenderStatus.DEFERRED, "Отложено"),
    ],
)
def test_decision_status_renders_on_active_and_priority_tabs(
    tender_factory,
    tab: str,
    status: TenderStatus,
    label: str,
) -> None:
    tender = tender_factory(status=status)

    html = _render_tender_list(tab, tender)

    assert "<th>Статус</th>" in html
    assert f'data-testid="tender-decision-status-{tender.id}"' in html
    assert label in html


def test_pending_status_has_no_decision_badge(tender_factory) -> None:
    tender = tender_factory(status=TenderStatus.PENDING)

    html = _render_tender_list("active", tender)

    assert "<th>Статус</th>" in html
    assert f'data-testid="tender-decision-status-{tender.id}"' not in html


def test_decision_status_is_not_rendered_on_other_tabs(tender_factory) -> None:
    tender = tender_factory(status=TenderStatus.TAKEN)

    html = _render_tender_list("archive", tender)

    assert "<th>Статус</th>" not in html
    assert f'data-testid="tender-decision-status-{tender.id}"' not in html
