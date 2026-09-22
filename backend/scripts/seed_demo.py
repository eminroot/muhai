"""Create (or refresh) the demo account.

    python -m scripts.seed_demo
    python -m scripts.seed_demo --email demo@muhai.app --password demo1234

One account, pre-filled with the dataset in ``services/demo_seed.py``, for
showing the product without typing a year of bookkeeping first. Real sign-ups
get an empty workspace; this is the only place demo data comes from.

Idempotent. Run it again and the account keeps its id and password while its
data is rebuilt, so a demo you have already opened in a browser stays signed
in and simply refreshes.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import sys
from pathlib import Path

# Runnable as `python scripts/seed_demo.py` as well as `-m scripts.seed_demo`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.models.company import Company  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import demo_seed  # noqa: E402

DEFAULT_EMAIL = "demo@muhai.app"
DEFAULT_PASSWORD = "demo1234"

COMPANY = {
    "name": "Nasimi Ticaret Ltd. Şti.",
    "tax_id": "4830027561",
    "tax_office": "Kadıköy",
    "sector": "wholesale",
    "city": "İstanbul",
    "legal_form": "ltd",
}


async def seed(email: str, password: str, today: dt.date | None) -> None:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))

        if user is None:
            company = Company(email=email, **COMPANY)
            db.add(company)
            await db.flush()

            user = User(
                email=email,
                hashed_password=hash_password(password),
                business_name=COMPANY["name"],
                display_name="Demo Kullanıcı",
                role="owner",
                company_id=company.id,
            )
            db.add(user)
            await db.flush()

            company.owner_user_id = user.id
            db.add(company)
            await db.flush()
            created = True
        else:
            # Keep the existing password: an account someone is already signed
            # in to should not be locked out by a reseed.
            company = await db.get(Company, user.company_id) if user.company_id else None
            if company is None:
                company = Company(email=email, owner_user_id=user.id, **COMPANY)
                db.add(company)
                await db.flush()
                user.company_id = company.id
                db.add(user)
                await db.flush()
            created = False

        counts = await demo_seed.seed_company(db, company, today=today)
        await db.commit()

    total = sum(counts.values())
    print(f"{'Created' if created else 'Refreshed'} demo account")
    print(f"  email    {email}")
    print(f"  password {password if created else '(unchanged)'}")
    print(f"  company  {company.name}")
    print(f"  cash     {company.cash_balance:,.2f} TRY")
    for name, count in counts.items():
        print(f"  {name:<14} {count:>4} rows")
    print(f"  {'total':<14} {total:>4} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD,
                        help="only used when the account is created")
    parser.add_argument("--today", default=None,
                        help="ISO date to generate the history against (default: today)")
    args = parser.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else None
    asyncio.run(seed(args.email, args.password, today))


if __name__ == "__main__":
    main()
