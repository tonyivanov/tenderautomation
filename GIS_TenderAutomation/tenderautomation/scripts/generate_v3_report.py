"""Generate comprehensive v3 classification report + comparison v3 vs v2 vs v1."""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.config import settings
from core.db import SessionLocal
from core.orm import TenderORM
from core.repositories import TenderRepository
from core.services.qualification_engine import QualificationEngine
from core.services.scoring_v2 import ScoringV2Pipeline
from core.services.scoring_v3 import ScoringV3Pipeline
from core.services.scoring_v3 import models as v3m
from sqlalchemy import select


def generate() -> Path:
    engine_v1 = QualificationEngine.from_filters_dir(settings.filters_dir)
    pipeline_v2 = ScoringV2Pipeline(seed=42)
    pipeline_v3 = ScoringV3Pipeline(seed=42)
    repo = TenderRepository()

    with SessionLocal() as session:
        rows = session.execute(select(TenderORM)).scalars().all()
        tenders = [repo._orm_to_model(r) for r in rows]

    # ── v1 + v2 classification ──────────────────────────────────────────
    v1_results: list[dict] = []
    v2_map: dict[str, object] = {}

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
        v2_map[tender.id] = r_v2

        v1_results.append({
            "id": tender.id,
            "title": tender.title,
            "v1_tier": v1_tier,
            "v1_score": v1_score,
            "v1_category": v1_cat,
            "platform": tender.platform or "unknown",
            "url": tender.url or "#",
            "deadline": tender.deadline,
        })

    # ── v3 classification ────────────────────────────────────────────────
    tender_dicts = [
        {
            "id": t["id"],
            "title": t["title"],
            "v1_tier": t["v1_tier"],
            "v1_score": t["v1_score"],
            "v1_category": t["v1_category"],
        }
        for t in v1_results
    ]

    v3_run = pipeline_v3.run(tender_dicts, run_legacy=False)
    v3_map: dict[str, v3m.V3Result] = {}
    for r in v3_run.results:
        v3_map[r.tender_id] = r

    # ── Build combined dataset ───────────────────────────────────────────
    combined: list[dict] = []
    stats = {
        "total": len(tenders),
        "p1": 0, "p2": 0, "p3": 0, "reject": 0,
        "v3_core": 0, "v3_review": 0, "v3_reject": 0,
        "v2_p1": 0, "v2_p2": 0, "v2_p3": 0, "v2_reject": 0,
        "v1_core": 0, "v1_review": 0, "v1_lowish": 0, "v1_hard_stop": 0, "v1_low": 0,
        "disagreements": 0,
        "judge_calls": 0,
        "cache_hits": 0,
        "total_cost": 0.0,
        "v3_core_v1_lost": 0,  # v1 core/hard_stop not in v3 P1/P2
        "v3_miss_hard_stop": 0,  # v1 hard_stop sent to P1
    }

    for t in v1_results:
        tid = t["id"]
        r_v3 = v3_map.get(tid)
        r_v2 = v2_map.get(tid)

        v2_queue = "reject"
        v2_positive = False
        v2_selected = False
        v2_prio = 0
        if r_v2:
            v2_queue = getattr(r_v2, "review_queue", "reject")
            v2_positive = getattr(r_v2, "positive_candidate", False)
            v2_selected = getattr(r_v2, "selected_for_human_review", False)
            v2_prio = getattr(r_v2, "review_priority_score", 0)

        v3_queue = r_v3.queue if r_v3 else "error"
        v3_verdict = r_v3.final_verdict if r_v3 else "error"
        v3_fit = r_v3.final_fit_score if r_v3 else 0
        v3_conf = r_v3.final_confidence if r_v3 else 0
        v3_prio = r_v3.priority if r_v3 else 0
        v3_disagreed = r_v3.classifier_disagreement if r_v3 else False
        v3_judge = r_v3.judge_pass is not None if r_v3 else False
        v3_cached = r_v3.cache_hit if r_v3 else False
        v3_fp_verdict = r_v3.first_pass.verdict if r_v3 else "error"
        v3_fp_confidence = r_v3.first_pass.confidence if r_v3 else 0
        v3_fp_fit = r_v3.first_pass.fit_score if r_v3 else 0
        v3_proc_type = r_v3.first_pass.procurement_type if r_v3 else "unknown"
        v3_domain = r_v3.first_pass.primary_domain if r_v3 else "unknown"
        v3_risk_flags = r_v3.first_pass.risk_flags if r_v3 else []
        v3_pos_ev = r_v3.first_pass.positive_evidence if r_v3 else []
        v3_neg_ev = r_v3.first_pass.negative_evidence if r_v3 else []
        v3_reason = r_v3.first_pass.reason if r_v3 else ""
        v3_judge_verdict = r_v3.judge_pass.verdict if r_v3 and r_v3.judge_pass else ""
        v3_judge_conf = r_v3.judge_pass.confidence if r_v3 and r_v3.judge_pass else 0
        v3_judge_fit = r_v3.judge_pass.fit_score if r_v3 and r_v3.judge_pass else 0
        v3_cost = r_v3.estimated_cost if r_v3 else 0
        v3_input_tokens = r_v3.input_tokens if r_v3 else 0
        v3_output_tokens = r_v3.output_tokens if r_v3 else 0

        # Stats
        stats["total_cost"] += v3_cost

        if v3_queue == "P1":
            stats["p1"] += 1
        elif v3_queue == "P2":
            stats["p2"] += 1
        elif v3_queue == "P3":
            stats["p3"] += 1
        else:
            stats["reject"] += 1

        if v3_verdict == "core":
            stats["v3_core"] += 1
        elif v3_verdict == "review":
            stats["v3_review"] += 1
        else:
            stats["v3_reject"] += 1

        if v2_queue == "P1":
            stats["v2_p1"] += 1
        elif v2_queue == "P2":
            stats["v2_p2"] += 1
        elif v2_queue == "P3":
            stats["v2_p3"] += 1
        else:
            stats["v2_reject"] += 1

        v1_cat = t["v1_category"]
        if v1_cat == "core":
            stats["v1_core"] += 1
        elif v1_cat == "review":
            stats["v1_review"] += 1
        elif v1_cat == "lowish":
            stats["v1_lowish"] += 1
        elif v1_cat == "hard_stop":
            stats["v1_hard_stop"] += 1
        else:
            stats["v1_low"] += 1

        if v3_disagreed:
            stats["disagreements"] += 1
        if v3_judge:
            stats["judge_calls"] += 1
        if v3_cached:
            stats["cache_hits"] += 1

        # v1 core lost: v1 core not in v3 P1/P2
        if v1_cat == "core" and v3_queue not in ("P1", "P2"):
            stats["v3_core_v1_lost"] += 1

        # v1 hard_stop in P1
        if v1_cat == "hard_stop" and v3_queue == "P1":
            stats["v3_miss_hard_stop"] += 1

        deadline = t.get("deadline")
        deadline_str = deadline.strftime("%Y-%m-%d") if deadline else "—"
        if deadline_str != "—":
            try:
                dl_date = datetime.strptime(deadline_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dl_date < datetime.now(timezone.utc):
                    deadline_str = "EXPIRED " + deadline_str
            except ValueError:
                pass

        combined.append({
            "title": t["title"],
            "platform": t["platform"],
            "url": t["url"],
            "deadline": deadline_str,
            "v1_cat": v1_cat,
            "v1_score": t["v1_score"],
            "v2_queue": v2_queue,
            "v2_positive": v2_positive,
            "v2_selected": v2_selected,
            "v2_prio": v2_prio,
            "v3_queue": v3_queue,
            "v3_verdict": v3_verdict,
            "v3_fit": v3_fit,
            "v3_conf": v3_conf,
            "v3_prio": v3_prio,
            "v3_disagreed": v3_disagreed,
            "v3_judge": v3_judge,
            "v3_cached": v3_cached,
            "v3_proc_type": v3_proc_type,
            "v3_domain": v3_domain,
            "v3_risk_flags": v3_risk_flags,
            "v3_pos_ev": v3_pos_ev,
            "v3_neg_ev": v3_neg_ev,
            "v3_reason": v3_reason,
            "v3_first_verdict": v3_fp_verdict,
            "v3_first_conf": v3_fp_confidence,
            "v3_first_fit": v3_fp_fit,
            "v3_judge_verdict": v3_judge_verdict,
            "v3_judge_conf": v3_judge_conf,
            "v3_judge_fit": v3_judge_fit,
            "v3_cost": v3_cost,
        })

    # Sort: v3 P1 → P2 → P3 → reject, then by priority desc
    queue_order = {"P1": 0, "P2": 1, "P3": 2, "reject": 3, "error": 4}
    combined.sort(key=lambda r: (queue_order.get(r["v3_queue"], 5), -r["v3_prio"]))

    # ── Build HTML ───────────────────────────────────────────────────────
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(combined)

    queue_bg = {
        "P1": "background:#ffebee",
        "P2": "background:#fff8e1",
        "P3": "background:#e3f2fd",
        "reject": "background:#f5f5f5;color:#999",
        "error": "background:#ffcdd2",
    }
    v1_badge_bg = {
        "core": "background:#c8e6c9;color:#2e7d32",
        "review": "background:#fff9c4;color:#f57f17",
        "lowish": "background:#bbdefb;color:#1565c0",
        "hard_stop": "background:#ffcdd2;color:#c62828",
        "low": "background:#e0e0e0;color:#757575",
    }
    v3_verdict_bg = {
        "core": "background:#c8e6c9",
        "review": "background:#fff9c4",
        "reject": "background:#ffcdd2",
        "error": "background:#f5f5f5;color:#999",
    }

    rows_html = ""
    for i, r in enumerate(combined, 1):
        qb = queue_bg.get(r["v3_queue"], "")
        v1b = v1_badge_bg.get(r["v1_cat"], "")
        v3vb = v3_verdict_bg.get(r["v3_verdict"], "")

        # Short evidence
        pos_ev_short = ", ".join(r["v3_pos_ev"][:2]) if r["v3_pos_ev"] else "—"
        neg_ev_short = ", ".join(r["v3_neg_ev"][:2]) if r["v3_neg_ev"] else "—"
        risk_str = ", ".join(r["v3_risk_flags"]) if r.get("v3_risk_flags") else "—"

        indicators = []
        if r["v3_judge"]:
            indicators.append("⚖")
        if r["v3_disagreed"]:
            indicators.append("⚠")
        if r["v3_cached"]:
            indicators.append("💾")
        ind_str = " ".join(indicators) if indicators else "—"

        # Full tooltip with all LLM evidence
        tooltip_parts = []
        if r["v3_pos_ev"]:
            tooltip_parts.append("POSITIVE: " + "; ".join(r["v3_pos_ev"]))
        if r["v3_neg_ev"]:
            tooltip_parts.append("NEGATIVE: " + "; ".join(r["v3_neg_ev"]))
        if r["v3_reason"]:
            tooltip_parts.append("REASON: " + r["v3_reason"])
        tooltip = "\n".join(tooltip_parts)

        rows_html += (
            f'<tr style="{qb}">'
            f'<td>{i}</td>'
            f'<td style="max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{html.escape(r["title"])}">'
            f'<a href="{html.escape(r["url"])}" target=_blank>{html.escape(r["title"][:120])}</a></td>'
            f'<td><span style="font-size:10px;padding:1px 4px;border-radius:3px;{v1b}">{r["v1_cat"]}</span></td>'
            f'<td>{r["v1_score"]}</td>'
            f'<td>{r["v2_queue"]}</td>'
            f'<td><b>{r["v3_queue"]}</b></td>'
            f'<td><span style="font-size:10px;padding:1px 4px;border-radius:3px;{v3vb}">{r["v3_verdict"]}</span></td>'
            f'<td>{r["v3_fit"]}</td>'
            f'<td>{r["v3_conf"]:.2f}</td>'
            f'<td>{r["v3_prio"]}</td>'
            f'<td>{r["v3_domain"]}</td>'
            f'<td style="font-size:10px">{r["v3_proc_type"]}</td>'
            f'<td style="font-size:10px">{risk_str}</td>'
            f'<td>{ind_str}</td>'
            f'<td><span style="font-size:10px;padding:1px 4px;border-radius:3px;{v3_verdict_bg.get(r["v3_first_verdict"], "")}">{r["v3_first_verdict"]}</span></td>'
            f'<td>{r["v3_first_fit"]}</td>'
            f'<td>{r["v3_first_conf"]:.2f}</td>'
            f'<td><span style="font-size:10px;padding:1px 4px;border-radius:3px;{v3_verdict_bg.get(r["v3_judge_verdict"], "")}">{r["v3_judge_verdict"] or "—"}</span></td>'
            f'<td>{r["v3_judge_fit"]}</td>'
            f'<td>{r["v3_judge_conf"]:.2f}</td>'
            f'<td style="font-size:9px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{html.escape(tooltip)}">{html.escape(pos_ev_short)}</td>'
            f'<td style="font-size:9px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{html.escape(tooltip)}">{html.escape(neg_ev_short)}</td>'
            f'</tr>'
        )

    # Quality check classes
    lost_class = "good" if stats["v3_core_v1_lost"] == 0 else "bad"
    hs_class = "good" if stats["v3_miss_hard_stop"] == 0 else "bad"
    cost_class = "good" if stats["total_cost"] < 1.0 else ("warn" if stats["total_cost"] < 3.0 else "bad")

    report = f"""<!DOCTYPE html><html lang=ru><head><meta charset=utf-8><title>Scoring v3 — GIS LLM Classification</title>
<style>body{{font-family:system-ui,sans-serif;margin:20px;background:#f5f5f5}}h1{{color:#333}}h2{{color:#555;margin-top:24px}}
table{{width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1);margin-bottom:20px}}
th,td{{padding:4px 6px;text-align:left;border-bottom:1px solid #eee;font-size:10px}}
th{{background:#4CAF50;color:#fff;position:sticky;top:0;z-index:1}}
a{{color:#2196F3;text-decoration:none}}a:hover{{text-decoration:underline}}
.summary{{display:flex;gap:10px;margin:10px 0;flex-wrap:wrap;font-size:12px}}
.summary div{{background:#fff;padding:8px 14px;border-radius:5px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.summary b{{color:#333}}
.good{{color:#2e7d32}}.warn{{color:#f57f17}}.bad{{color:#c62828}}.ok{{color:#1565c0}}
.check{{margin:10px 0;font-size:12px}}.check span{{margin-right:15px}}
.pipeline-info{{font-size:11px;color:#666;margin:4px 0}}
</style></head><body>
<h1>Scoring v3 — LLM Classification Report (v3 vs v2 vs v1)</h1>

<div class=pipeline-info>
Two-pass: {v3_run.stats.first_pass_core}/{v3_run.stats.first_pass_review}/{v3_run.stats.first_pass_reject} →
Judge on {v3_run.stats.sent_to_judge} →
Final: {v3_run.stats.final_core}/{v3_run.stats.final_review}/{v3_run.stats.final_reject} |
Batches: {v3_run.primary_batches} primary + {v3_run.judge_batches} judge |
Cache: {v3_run.cache_hits} hits / {v3_run.cache_misses} misses |
Time: {v3_run.elapsed_seconds}s
</div>

<h2>Queue Distribution</h2>
<div class=summary>
<div>Total: <b>{total}</b></div>
<div>P1: <b class="good">{stats["p1"]}</b></div>
<div>P2: <b class="ok">{stats["p2"]}</b></div>
<div>P3: <b>{stats["p3"]}</b></div>
<div>Reject: <b class="bad">{stats["reject"]}</b></div>
</div>

<div class=summary>
<div>v3 Core: <b class="good">{stats["v3_core"]}</b></div>
<div>v3 Review: <b class="warn">{stats["v3_review"]}</b></div>
<div>v3 Reject: <b class="bad">{stats["v3_reject"]}</b></div>
</div>

<h2>Comparison</h2>
<div class=summary>
<div>v2 P1: <b>{stats["v2_p1"]}</b></div>
<div>v2 P2: <b>{stats["v2_p2"]}</b></div>
<div>v2 P3: <b>{stats["v2_p3"]}</b></div>
<div>v2 Reject: <b>{stats["v2_reject"]}</b></div>
<div>v1 Core: <b>{stats["v1_core"]}</b></div>
<div>v1 Review: <b>{stats["v1_review"]}</b></div>
<div>v1 HardStop: <b>{stats["v1_hard_stop"]}</b></div>
</div>

<h2>Quality Checks</h2>
<div class=summary>
<div>v1 Core lost: <b class="{lost_class}">{stats["v3_core_v1_lost"]}</b></div>
<div>v1 HardStop→P1: <b class="{hs_class}">{stats["v3_miss_hard_stop"]}</b></div>
<div>Disagreements: <b>{stats["disagreements"]}</b></div>
<div>Judge calls: <b>{stats["judge_calls"]}</b></div>
<div>Cache hits: <b>{stats["cache_hits"]}</b></div>
<div>Est. cost: <b class="{cost_class}">${stats["total_cost"]:.4f}</b></div>
</div>

<h2>Legend</h2>
<div style="font-size:11px;margin:10px 0">
<b>⚖</b> = Judge pass | <b>⚠</b> = Disagreement | <b>💾</b> = Cache hit<br>
v3 Verdict: <span style="background:#c8e6c9;padding:1px 6px;border-radius:3px">core</span>
<span style="background:#fff9c4;padding:1px 6px;border-radius:3px">review</span>
<span style="background:#ffcdd2;padding:1px 6px;border-radius:3px">reject</span>
</div>

<table><thead><tr>
<th>#</th><th>Title</th><th>v1</th><th>v1 Sc</th><th>v2 Q</th><th>v3 Q</th><th>Verdict</th><th>Fit</th><th>Conf</th><th>Prio</th><th>Domain</th><th>Type</th><th>Risk</th><th>I</th><th>1st</th><th>1Fit</th><th>1Conf</th><th>Judge</th><th>JFit</th><th>JConf</th><th>+Ev</th><th>-Ev</th>
</tr></thead><tbody>{rows_html}</tbody></table>

<div style="font-size:10px;color:#999;margin-top:10px">{now_utc} | v3 pipeline</div>
</body></html>"""

    now_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    output_path = Path(settings.data_dir) / f"v3_classification_report_{now_stamp}.html"
    output_path.write_text(report, encoding="utf-8")
    print(f"Report: {output_path}")
    print(f"Total: {total} | P1: {stats['p1']} P2: {stats['p2']} P3: {stats['p3']} Reject: {stats['reject']}")
    print(f"v3: core={stats['v3_core']} review={stats['v3_review']} reject={stats['v3_reject']}")
    print(f"v2: P1={stats['v2_p1']} P2={stats['v2_p2']} P3={stats['v2_p3']} Reject={stats['v2_reject']}")
    print(f"v1 Core lost: {stats['v3_core_v1_lost']} | HardStop→P1: {stats['v3_miss_hard_stop']}")
    print(f"Disagreements: {stats['disagreements']} | Judge calls: {stats['judge_calls']}")
    print(f"Est. cost: ${stats['total_cost']:.4f}")
    return output_path


if __name__ == "__main__":
    generate()