"""Quick test of Groq Qwen3-32B classification on 5 tenders from DB."""
import asyncio, sys
sys.path.insert(0, "src")

from core.db import SessionLocal
from core.orm.tender import TenderORM
from sqlalchemy import select
from core.services.scoring_v3.groq_client import classify_batch
from core.services.scoring_v3.config import GROQ_API_KEY

async def main():
    # Fetch 5 random tenders from DB
    with SessionLocal() as session:
        rows = session.execute(
            select(TenderORM.title).order_by(TenderORM.collected_at.desc()).limit(10)
        ).scalars().all()

    titles = list(rows)
    print(f"Testing Groq Qwen3-32B on {len(titles)} titles:\n")
    for i, t in enumerate(titles, 1):
        print(f"  {i}. {t}")

    print("\nCalling Groq API...")
    result = await classify_batch(titles, use_judge=False, api_key=GROQ_API_KEY)

    print(f"\nModel: {result.model_used}")
    print(f"Tokens: {result.input_tokens} in / {result.output_tokens} out")
    print(f"Latency: {result.latency_ms}ms")
    print(f"Cost: ${result.estimated_cost:.6f}")
    print(f"\nResults ({len(result.items)} items):")
    for item in result.items:
        print(f"  [{item.verdict:6s}] fit={item.fit_score:3d} conf={item.confidence:.2f} "
              f"domain={item.primary_domain:20s} type={item.procurement_type}")
        if item.reason:
            print(f"                reason: {item.reason[:120]}")

if __name__ == "__main__":
    asyncio.run(main())