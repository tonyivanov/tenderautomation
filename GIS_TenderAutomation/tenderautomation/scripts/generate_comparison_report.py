"""Generate comparison report: v1 vs v2 scoring (v2.1)."""
from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.config import settings
from core.db import SessionLocal
from core.orm import TenderORM
from core.repositories import TenderRepository
from core.services.qualification_engine import QualificationEngine
from core.services.scoring_v2 import ScoringV2Pipeline
from sqlalchemy import select


def generate() -> Path:
    engine_v1 = QualificationEngine.from_filters_dir(settings.filters_dir)
    pipeline_v2 = ScoringV2Pipeline(seed=42)
    repo = TenderRepository()

    with SessionLocal() as session:
        rows = session.execute(select(TenderORM)).scalars().all()
        tenders = [repo._orm_to_model(r) for r in rows]

    results = []
    stats = {
        "total": len(tenders),
        "v2_p1": 0, "v2_p2": 0, "v2_p3": 0, "v2_reject": 0,
        "v2_positive": 0, "v2_selected": 0,
        "v1_core_lost": 0, "v1_review_lost": 0,
        "v2_action_object_only": 0,
        "v2_disagreement": 0,
        "v2_supply_p1": 0,
        "v2_legacy_only": 0,
        "v2_no_legacy_candidate": 0,
    }

    for tender in tenders:
        r_v1 = engine_v1.qualify(tender)
        v1_tier = r_v1.tier
        v1_score = r_v1.score
        v1_cat = r_v1.category if not r_v1.hard_stop_match else "hard_stop"

        r_v2 = pipeline_v2.qualify(
            tender_id=tender.id,
            title=tender.title,
            v1_tier=v1_tier,
            v1_score=v1_score,
            v1_category=v1_cat,
        )

        if r_v2.review_queue == "P1":
            stats["v2_p1"] += 1
        elif r_v2.review_queue == "P2":
            stats["v2_p2"] += 1
        elif r_v2.review_queue == "P3":
            stats["v2_p3"] += 1
        else:
            stats["v2_reject"] += 1

        if r_v2.positive_candidate:
            stats["v2_positive"] += 1
        if r_v2.selected_for_human_review:
            stats["v2_selected"] += 1

        if v1_cat == "core" and not r_v2.selected_for_human_review:
            stats["v1_core_lost"] += 1
        if v1_cat == "review" and not r_v2.selected_for_human_review:
            stats["v1_review_lost"] += 1

        if r_v2.action_object.candidate and not r_v2.rules.candidate:
            stats["v2_action_object_only"] += 1
        if r_v2.classifier_disagreement:
            stats["v2_disagreement"] += 1
        if r_v2.procurement_type == "supply_only" and r_v2.review_queue == "P1":
            stats["v2_supply_p1"] += 1
        if r_v2.legacy.candidate and not r_v2.rules.candidate and not r_v2.action_object.candidate:
            stats["v2_legacy_only"] += 1

        results.append(r_v2)

    queue_order = {"P1": 0, "P2": 1, "P3": 2, "reject": 3}
    results.sort(key=lambda r: (queue_order.get(r.review_queue, 4), -r.review_priority_score))

    queue_label = {"P1": "P1", "P2": "P2", "P3": "P3", "reject": "reject"}
    queue_bg = {
        "P1": "background:#ffebee",
        "P2": "background:#fff8e1",
        "P3": "background:#e3f2fd",
        "reject": "background:#f5f5f5;color:#999"
    }

    rows_html = ""
    for i, r in enumerate(results, 1):
        reasons = ", ".join(r.decision_reasons) if r.decision_reasons else "-"
        v2_queue = r.review_queue
        qb = queue_bg.get(v2_queue, "")

        if r.v1_category == "core":
            v1_badge = "core"
        elif r.v1_category == "review" or r.v1_tier == "in_review":
            v1_badge = "review"
        elif r.v1_category == "lowish":
            v1_badge = "lowish"
        elif r.v1_category == "hard_stop":
            v1_badge = "hard_stop"
        else:
            v1_badge = "low"

        indicators = []
        if r.positive_candidate:
            indicators.append("+")
        if r.legacy.candidate:
            indicators.append("L")
        if r.rules.candidate:
            indicators.append("R")
        if r.action_object.candidate:
            indicators.append("A")
        if r.classifier_disagreement:
            indicators.append("!")
        if r.supply_only:
            indicators.append("$")
        if r.p3_control_sample:
            indicators.append("P3")
        ind_str = " ".join(indicators) if indicators else "-"

        rows_html += (
            '<tr style="' + qb + '">'
            '<td>' + str(i) + '</td>'
            '<td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
            '<a href="#" title="' + html.escape(r.original_title) + '">' + html.escape(r.original_title[:100]) + '</a></td>'
            '<td>' + v1_badge + '</td>'
            '<td>' + str(r.v1_score) + '</td>'
            '<td><b>' + queue_label.get(v2_queue, v2_queue) + '</b></td>'
            '<td>' + str(r.review_priority_score) + '</td>'
            '<td>' + ("+" if r.positive_candidate else "-") + '</td>'
            '<td>' + ("+" if r.selected_for_human_review else "-") + '</td>'
            '<td style="font-size:10px">' + ind_str + '</td>'
            '<td style="font-size:10px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + html.escape(reasons) + '</td>'
            '</tr>'
        )

    core_lost_class = "good" if stats["v1_core_lost"] == 0 else "bad"
    review_lost_class = "good" if stats["v1_review_lost"] == 0 else "bad"
    supply_p1_class = "good" if stats["v2_supply_p1"] == 0 else "bad"

    report = """<!DOCTYPE html><html lang=ru><head><meta charset=utf-8><title>Scoring v2.1 - Comparison</title>
<style>body{font-family:system-ui,sans-serif;margin:20px;background:#f5f5f5}h1{color:#333}h2{color:#555;margin-top:20px}
table{width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1);margin-bottom:20px}
th,td{padding:5px 7px;text-align:left;border-bottom:1px solid #eee;font-size:10px}
th{background:#4CAF50;color:#fff;position:sticky;top:0}
a{color:#2196F3;text-decoration:none}a:hover{text-decoration:underline}
.summary{display:flex;gap:10px;margin:10px 0;flex-wrap:wrap;font-size:12px}
.summary div{background:#fff;padding:8px 12px;border-radius:5px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.summary b{color:#333}.good{color:#2e7d32}.warn{color:#f57f17}.bad{color:#c62828}.ok{color:#1565c0}
.check{margin:10px 0;font-size:12px}.check span{margin-right:15px}
</style></head><body>
<h1>Scoring v2.1 - Comparison Report (v1 vs v2)</h1>

<div class=check>
<span>Legacy scorer as safety net</span>
<span>positive_candidate / selected_for_human_review split</span>
<span>P2 not default queue</span>
<span>Disagreement only with 2 explicit decisions</span>
<span>Supply capped at P2 / priority 25</span>
</div>

<h2>Summary</h2>
<div class=summary>
<div>Total: <b>""" + str(stats["total"]) + """</b></div>
<div>P1: <b class="good">""" + str(stats["v2_p1"]) + """</b></div>
<div>P2: <b class="ok">""" + str(stats["v2_p2"]) + """</b></div>
<div>P3: <b>""" + str(stats["v2_p3"]) + """</b></div>
<div>Reject: <b class="bad">""" + str(stats["v2_reject"]) + """</b></div>
<div>Positive: <b class="good">""" + str(stats["v2_positive"]) + """</b></div>
<div>Selected: <b class="good">""" + str(stats["v2_selected"]) + """</b></div>
</div>

<h2>Quality Checks</h2>
<div class=summary>
<div>v1 Core lost: <b class=""" + core_lost_class + """">""" + str(stats["v1_core_lost"]) + """</b></div>
<div>v1 Review lost: <b class=""" + review_lost_class + """">""" + str(stats["v1_review_lost"]) + """</b></div>
<div>Supply in P1: <b class=""" + supply_p1_class + """">""" + str(stats["v2_supply_p1"]) + """</b></div>
<div>Disagreements: <b>""" + str(stats["v2_disagreement"]) + """</b></div>
<div>Action+Object only: <b>""" + str(stats["v2_action_object_only"]) + """</b></div>
<div>Legacy only (no new signals): <b>""" + str(stats["v2_legacy_only"]) + """</b></div>
</div>

<h2>Legend</h2>
<div style="font-size:11px;margin:10px 0">
<b>+</b> = positive_candidate | <b>L</b> = legacy v1 | <b>R</b> = strong rules | <b>A</b> = action+object | <b>!</b> = disagreement | <b>$</b> = supply_only | <b>P3</b> = control sample
</div>

<table><thead><tr>
<th>#</th><th>Title</th><th>v1</th><th>v1 Score</th><th>v2 Queue</th><th>Prio</th><th>+</th><th>Sel</th><th>Signals</th><th>Reasons</th>
</tr></thead><tbody>""" + rows_html + """</tbody></table></body></html>"""

    output_path = Path(settings.data_dir) / "comparison_report_v1_v2.html"
    output_path.write_text(report, encoding="utf-8")
    print("Report: " + str(output_path))
    print("P1:" + str(stats["v2_p1"]) + " P2:" + str(stats["v2_p2"]) + " P3:" + str(stats["v2_p3"]) + " Reject:" + str(stats["v2_reject"]))
    print("Positive:" + str(stats["v2_positive"]) + " Selected:" + str(stats["v2_selected"]))
    print("v1 Core lost:" + str(stats["v1_core_lost"]) + " v1 Review lost:" + str(stats["v1_review_lost"]))
    print("Supply in P1:" + str(stats["v2_supply_p1"]) + " Disagreements:" + str(stats["v2_disagreement"]))
    return output_path


if __name__ == "__main__":
    generate()