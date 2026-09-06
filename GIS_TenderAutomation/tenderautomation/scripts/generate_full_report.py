"""Generate full qualification report HTML for all tenders."""
from __future__ import annotations

import html
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.config import settings
from core.db import SessionLocal
from core.orm import TenderORM
from core.repositories import TenderRepository
from core.services.qualification_engine import QualificationEngine
from sqlalchemy import select


def generate() -> Path:
    engine = QualificationEngine.from_filters_dir(settings.filters_dir)
    repo = TenderRepository()
    with SessionLocal() as session:
        rows = session.execute(select(TenderORM)).scalars().all()
        tenders = [repo._orm_to_model(r) for r in rows]

    results = []
    stats = {"core": 0, "review": 0, "lowish": 0, "hard_stop": 0, "low": 0}

    for tender in tenders:
        result = engine.qualify(tender)
        if result.hard_stop_match:
            cat = "hard_stop"
        elif result.category == "core":
            cat = "core" if result.tier == "qualified" else "review"
        elif result.category == "review":
            cat = "review"
        elif result.category == "lowish":
            cat = "lowish"
        else:
            cat = "low"

        stats[cat] = stats.get(cat, 0) + 1

        positive_phrases = [m.phrase for m in result.positive_matches[:3]]
        positive_str = ", ".join(positive_phrases) if positive_phrases else "—"
        explanation = result.explanation
        score = result.score
        deadline = tender.deadline.strftime("%Y-%m-%d") if tender.deadline else "—"
        platform = tender.platform or "unknown"
        url = tender.url or "#"
        title = tender.title

        if deadline != "—":
            try:
                dl_date = datetime.strptime(deadline, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dl_date < datetime.now(timezone.utc):
                    deadline_display = "EXPIRED " + deadline
                else:
                    deadline_display = deadline
            except ValueError:
                deadline_display = deadline
        else:
            deadline_display = "—"

        results.append({
            "platform": platform,
            "url": url,
            "title": title,
            "score": score,
            "cat": cat,
            "positive": positive_str,
            "deadline": deadline_display,
            "explanation": explanation,
        })

    cat_order = {"core": 0, "review": 1, "lowish": 2, "hard_stop": 3, "low": 4}
    results.sort(key=lambda r: (cat_order.get(r["cat"], 5), -r["score"]))

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(tenders)

    cat_emoji = {"core": "green", "review": "yellow", "lowish": "blue", "hard_stop": "red", "low": "grey"}
    cat_labels = {"core": "Core (>=20)", "review": "Review (>=12)", "lowish": "Low-ish (6-11)", "hard_stop": "Hard-stop", "low": "Low (0-5)"}

    stats_html = " | ".join(
        f'{cat_labels[c]}: {stats.get(c, 0)}'
        for c in ["core", "review", "lowish", "hard_stop", "low"]
    )

    rows_html = ""
    row_class = {"core": "core", "review": "review", "lowish": "lowish", "hard_stop": "hard_stop", "low": "low"}
    score_class = {"core": "scg", "review": "scy", "lowish": "scb", "hard_stop": "scr", "low": ""}
    platform_style = {"bidzaar": "background:#fff3e0", "b2bcenter": "background:#e3f2fd"}

    for i, r in enumerate(results, 1):
        ps = platform_style.get(r["platform"], "background:#f5f5f5")
        rows_html += (
            f'<tr class="{row_class[r["cat"]]}">'
            f'<td>{i}</td>'
            f'<td><span style="font-size:11px;padding:2px 5px;border-radius:3px;{ps}">{html.escape(r["platform"])}</span></td>'
            f'<td><a href="{html.escape(r["url"])}" target=_blank>{html.escape(r["title"])}</a></td>'
            f'<td class="{score_class[r["cat"]]}">{r["score"]}</td>'
            f'<td class="ex" title="{html.escape(r["positive"])}">{html.escape(r["positive"])}</td>'
            f'<td style="white-space:nowrap">{html.escape(r["deadline"])}</td>'
            f'<td class="ex" title="{html.escape(r["explanation"])}">{html.escape(r["explanation"])}</td>'
            f'</tr>'
        )

    report = f"""<!DOCTYPE html><html lang=ru><head><meta charset=utf-8><title>Qualification v8 — GIS</title>
<style>body{{font-family:system-ui,sans-serif;margin:20px;background:#f5f5f5}}h1{{color:#333}}.s{{color:#666;margin:8px 0}}
table{{width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
th,td{{padding:7px 10px;text-align:left;border-bottom:1px solid #eee;font-size:12px}}
th{{background:#4CAF50;color:#fff;position:sticky;top:0}}
tr.core{{background:#e8f5e9}}tr.review{{background:#fff8e1}}tr.lowish{{background:#e3f2fd}}tr.hard_stop{{background:#ffe0e0}}tr.low{{background:#fafafa;color:#999}}
.scg{{color:#2e7d32;font-weight:bold}}.scy{{color:#f57f17;font-weight:bold}}.scb{{color:#1565c0}}.scr{{color:#c62828}}
a{{color:#2196F3;text-decoration:none}}a:hover{{text-decoration:underline}}
.ex{{font-size:10px;color:#888;max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.lg{{display:flex;gap:10px;margin:10px 0;flex-wrap:wrap}}.lg span{{padding:3px 8px;border-radius:3px;font-size:11px}}
</style></head><body>
<h1>Qualification Report v7 — GIS TenderAutomation (office hard-stop, L3 virt, pentest safety net, infra software, works direction, 6 lifts)</h1>
<div class=s>Total: <b>{total}</b> | {stats_html} | {now_utc}</div>
<div class=lg><span style="background:#e8f5e9">Core GIS (IT audits, DevOps, Ceph, Linux, managed infra, IB analysis)</span><span style="background:#fff8e1">In Review (pentests, IB audits, virtualization, modernization, vendor hw)</span><span style="background:#e3f2fd">Low-ish (6-11)</span><span style="background:#ffe0e0">Hard-stop (sites, 1C, office, construction, engineering infra)</span><span style="background:#fafafa;color:#999">Low (0-5, supply capped at 2)</span></div>
<table><thead><tr><th>#</th><th>Pltf</th><th>Title</th><th>Score</th><th>Positive Phrases</th><th>Deadline</th><th>Explanation</th></tr></thead><tbody>{rows_html}</tbody></table></body></html>"""

    output_path = Path(settings.data_dir) / "full_qualification_report.html"
    output_path.write_text(report, encoding="utf-8")
    print(f"Report written: {output_path}")
    print(f"Total: {total} | Core: {stats.get('core',0)} | Review: {stats.get('review',0)} | Low-ish: {stats.get('lowish',0)} | Hard-stop: {stats.get('hard_stop',0)} | Low: {stats.get('low',0)}")
    return output_path


if __name__ == "__main__":
    generate()