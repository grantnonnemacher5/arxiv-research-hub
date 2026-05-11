"""GPT-4o HTML reports for rolling windows (plan Day 2)."""

from __future__ import annotations

import html
import logging
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone

from openai import OpenAI
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from classifier import BUCKET_DESCRIPTIONS
from config import OPENAI_API_KEY, OPENAI_CHAT_MODEL, REPORTS_DIR
from database import Paper, Report

logger = logging.getLogger(__name__)

ALLOWED_PERIODS = frozenset({"7d", "1m", "3m", "6m", "1y"})


def period_to_date_range(period: str, end: date | None = None) -> tuple[date, date]:
    if period not in ALLOWED_PERIODS:
        raise ValueError(f"Invalid period {period!r}; expected one of {sorted(ALLOWED_PERIODS)}")
    end = end or date.today()
    if period == "7d":
        start = end - timedelta(days=7)
    elif period == "1m":
        start = end - timedelta(days=30)
    elif period == "3m":
        start = end - timedelta(days=90)
    elif period == "6m":
        start = end - timedelta(days=180)
    else:  # 1y
        start = end - timedelta(days=365)
    return start, end


def _effective_date_sql():
    return func.coalesce(Paper.published_date, cast(Paper.created_at, Date))


def fetch_papers_for_period(db: Session, start: date, end: date) -> list[Paper]:
    eff = _effective_date_sql()
    stmt = (
        select(Paper)
        .where(eff >= start, eff <= end, Paper.buckets != "")
        .order_by(Paper.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def _group_by_bucket(papers: Sequence[Paper]) -> dict[str, list[Paper]]:
    groups: dict[str, list[Paper]] = defaultdict(list)
    for p in papers:
        labels = [x.strip() for x in p.buckets.split(",") if x.strip()]
        for lab in labels:
            if lab in BUCKET_DESCRIPTIONS:
                groups[lab].append(p)
    return groups


def _paper_lines_for_prompt(papers: Sequence[Paper], limit: int = 40) -> str:
    lines: list[str] = []
    for p in papers[:limit]:
        d = p.published_date or (p.created_at.date() if p.created_at else None)
        ds = d.isoformat() if d else "unknown date"
        lines.append(f"- Title: {p.title}\n  Authors: {p.authors}\n  Date: {ds}\n  arXiv: {p.arxiv_id}")
    if len(papers) > limit:
        lines.append(f"... and {len(papers) - limit} more papers in this bucket.")
    return "\n".join(lines)


def _summarize_bucket(client: OpenAI, bucket: str, papers: Sequence[Paper]) -> str:
    if not papers:
        return "No papers were classified into this bucket for the selected period."
    user = (
        f"You are writing a section of a research digest for finance / equity research readers.\n"
        f"Bucket theme: {bucket}\n"
        f"Theme notes: {BUCKET_DESCRIPTIONS[bucket]}\n\n"
        f"Here are the papers (titles/metadata only):\n{_paper_lines_for_prompt(papers)}\n\n"
        "Write 2–4 short paragraphs: key themes, what is changing, and why it might matter "
        "for practitioners. Plain English, no hype, no bullet list unless essential. "
        "Do not invent citations beyond the provided metadata."
    )
    resp = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You produce precise, readable research summaries for expert readers.",
            },
            {"role": "user", "content": user},
        ],
        max_tokens=1800,
        temperature=0.35,
    )
    return (resp.choices[0].message.content or "").strip()


def _executive_summary(
    client: OpenAI, period_label: str, papers: Sequence[Paper], bucket_summaries: dict[str, str]
) -> str:
    overview = "\n\n".join(f"{k}:\n{v}" for k, v in bucket_summaries.items())
    user = (
        f"Time window label: {period_label}\n"
        f"Total papers in window: {len(papers)}\n\n"
        f"Draft section summaries:\n{overview}\n\n"
        "Write one tight executive summary paragraph (6–10 sentences) for a research lead."
    )
    resp = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": "You write executive summaries for research leads."},
            {"role": "user", "content": user},
        ],
        max_tokens=600,
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()


def _html_doc(
    period: str,
    start: date,
    end: date,
    generated: datetime,
    executive: str,
    bucket_blocks: list[tuple[str, Sequence[Paper], str]],
    total: int,
) -> str:
    period_label = f"{start.isoformat()} — {end.isoformat()} ({period})"
    esc = html.escape
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>AI Research Report</title>",
        "<style>body{font-family:system-ui,Segoe UI,Roboto,sans-serif;max-width:900px;margin:2rem auto;line-height:1.5;color:#111}h1,h2{border-bottom:1px solid #ddd;padding-bottom:.25rem}article{margin-bottom:2rem}.meta{color:#555;font-size:.95rem}</style>",
        "</head><body>",
        f"<h1>{esc('AI Research Report — ' + period_label)}</h1>",
        f'<p class="meta">Generated: {esc(generated.strftime("%Y-%m-%d %H:%M UTC"))}</p>',
        "<h2>Executive summary</h2>",
        f"<p>{esc(executive).replace(chr(10), '<br>')}</p>",
        "<hr>",
    ]
    for bucket, plist, summary in bucket_blocks:
        parts.append(f"<h2>{esc(bucket)}</h2>")
        parts.append("<h3>Key papers</h3><ul>")
        for p in plist[:50]:
            d = p.published_date or (p.created_at.date() if p.created_at else None)
            ds = esc(d.isoformat()) if d else "unknown date"
            parts.append(
                "<li>"
                f"<strong>{esc(p.title)}</strong><br>"
                f"{esc(p.authors)} — {ds} — {esc(p.arxiv_id)}"
                "</li>"
            )
        if len(plist) > 50:
            parts.append(f"<li>… plus {len(plist) - 50} more in this bucket.</li>")
        parts.append("</ul>")
        parts.append("<h3>Themes and findings</h3>")
        parts.append(f"<article>{esc(summary).replace(chr(10), '<br>')}</article>")
    parts.append("<hr>")
    parts.append(f"<p><strong>Total papers reviewed:</strong> {total}</p>")
    parts.append("<p>Report generated by: AI Research Hub MVP</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def generate_report(period: str, db: Session) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    start, end = period_to_date_range(period)
    papers = fetch_papers_for_period(db, start, end)
    if not papers:
        raise ValueError("No classified papers in this period; ingest and classify first.")

    client = OpenAI(api_key=OPENAI_API_KEY)
    groups = _group_by_bucket(papers)
    fixed = list(BUCKET_DESCRIPTIONS.keys())
    bucket_summaries: dict[str, str] = {}
    bucket_blocks: list[tuple[str, Sequence[Paper], str]] = []
    for b in fixed:
        plist = groups.get(b, [])
        summary = _summarize_bucket(client, b, plist)
        bucket_summaries[b] = summary
        bucket_blocks.append((b, plist, summary))

    exec_par = _executive_summary(client, period, papers, bucket_summaries)
    now = datetime.now(timezone.utc)
    safe_period = re.sub(r"[^a-zA-Z0-9_-]+", "", period)
    filename = f"{safe_period}_{now.strftime('%Y%m%d_%H%M%S')}.html"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = (REPORTS_DIR / filename).resolve()
    html_doc = _html_doc(period, start, end, now, exec_par, bucket_blocks, len(papers))
    out_path.write_text(html_doc, encoding="utf-8")

    rel = filename
    db.add(Report(period=period, file_path=rel, generated_at=now.replace(tzinfo=None)))
    db.commit()
    logger.info("Wrote report %s (%s papers)", out_path, len(papers))
    return rel
