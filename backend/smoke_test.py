"""End-to-end smoke test: exercises every branch + the async flow."""
from fastapi.testclient import TestClient
from main import app


def run():
    with TestClient(app) as c:
        def post_sync(grade, category="earbuds", price=1800, ff="FBA"):
            return c.post("/returns", data={
                "sku": f"SKU-{grade}-{category}", "category": category,
                "original_price": price, "user_id": "meena", "fulfillment": ff,
                "return_reason": "did not like sound", "mock_grade": grade,
                "sync": "true",
            }).json()

        print("== sync pipeline branches ==")
        r = post_sync("A"); print("  A earbuds  ->", r["viable"], r["disposition"], "listing:", r["listing_id"])
        r = post_sync("A", category="phone_case", price=150); print("  A cheap    ->", r["viable"], r["disposition"])
        r = post_sync("B"); print("  B earbuds  ->", r["disposition"], "|", r["reason"])
        r = post_sync("D"); print("  D earbuds  ->", r["disposition"], "listing:", r["listing_id"])
        r = post_sync("A", ff="FBM"); print("  FBM dest   ->", r["destination"])

        print("\n== ASYNC flow (accept fast, poll for result) ==")
        acc = c.post("/returns", data={
            "sku": "ASYNC-1", "category": "shoes", "original_price": 2200,
            "user_id": "meena", "fulfillment": "FBA", "mock_grade": "A",
        }).json()
        print("  accepted:", acc["status"], "| poll_url:", acc["poll_url"])
        s = c.get(acc["poll_url"]).json()
        print("  polled   :", s["status"], "done:", s["done"], "disposition:", s["disposition"], "listing:", s["listing_id"])

        print("\n== marketplace + buy ==")
        ls = c.get("/listings").json(); print("  active listings:", len(ls))
        lid = ls[0]["id"]; card = c.get(f"/listings/{lid}").json()
        print("  health card:", card["grade"], card["health_score"], "price:", card["price"], "warranty:", card["warranty_days"])
        b = c.post(f"/listings/{lid}/buy", data={"buyer_id": "rahul"}).json(); print("  buy:", b["bought"], "credits:", b["credits_awarded"])

        print("\n== credits ==")
        print("  meena:", c.get("/credits/meena").json()["total"], "| rahul:", c.get("/credits/rahul").json()["total"])

        print("\n== prevention ==")
        print("  ", c.get("/prevention", params={"category": "shoes"}).json()["nudge"])


run()
