"""
seed.py
-------
Populates CategoryData (demand/cost/price the rule engine reads) and a couple
of sample return reasons so the /prevention endpoint has something to learn
from. Safe to call repeatedly — it no-ops if data already exists.
"""
from sqlmodel import Session, select

from models import CategoryData, Fulfillment, Grade, ReturnRequest
from database import engine

_CATEGORIES = [
    # category,      demand, refurb_cost, avg_resale_price (₹)
    ("earbuds",      0.80,   30.0,        1800.0),
    ("shoes",        0.70,   40.0,        2200.0),
    ("phone_case",   0.40,   10.0,        150.0),
    ("blender",      0.65,   120.0,       1500.0),
    ("backpack",     0.55,   25.0,        900.0),
    ("smartwatch",   0.75,   90.0,        2500.0),
    ("mouse",        0.60,   30.0,        600.0),
]

# (category, return_reason, count) -> seeds the prevention signal
_SAMPLE_RETURNS = [
    ("shoes", "runs small", 6),
    ("shoes", "color mismatch", 1),
    ("earbuds", "did not like sound", 2),
]


def seed() -> None:
    with Session(engine) as session:
        if not session.exec(select(CategoryData)).first():
            for c, demand, refurb, price in _CATEGORIES:
                session.add(CategoryData(category=c, avg_demand=demand,
                                         refurb_cost=refurb, avg_resale_price=price))

        if not session.exec(select(ReturnRequest)).first():
            for category, reason, n in _SAMPLE_RETURNS:
                for _ in range(n):
                    session.add(ReturnRequest(
                        sku=f"SEED-{category}", category=category,
                        original_price=0.0, user_id="seed",
                        fulfillment=Fulfillment.FBA, return_reason=reason,
                        provisional_grade=Grade.A,
                    ))
        session.commit()


if __name__ == "__main__":
    from database import init_db
    init_db()
    seed()
    print("DB initialised + seeded.")
