"""One connected synthetic journey system; no downloaded business data."""
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .storage import SCHEMA

CAMPAIGNS = [
    ("C01", "google", "branded_search", 30, 0.12, 190),
    ("C02", "google", "nonbranded_search", 30, 0.065, 270),
    ("C03", "google", "shopping", 30, 0.085, 230),
    ("C04", "meta", "prospecting", 7, 0.045, 170),
    ("C05", "meta", "retargeting", 7, 0.105, 160),
    ("C06", "affiliate", "partner", 30, 0.075, 0),
]

def utc(day, hour=12, minute=0, tz="America/New_York"):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)

def generate(config):
    rng = random.Random(config["seed"])
    start = date.fromisoformat(config["report_start"])
    end = date.fromisoformat(config["report_end"])
    warmup = start - timedelta(days=config["warmup_days"])
    zone = config["timezone"]
    price, unit_cost = config["synthetic_list_price_cents"], config["synthetic_unit_cost_cents"]
    data = {name: [] for name in SCHEMA}
    for cid, channel, objective, window, _, _ in CAMPAIGNS:
        data["campaigns"].append((cid, channel, objective, window, "synthetic_observation"))
        for n, message in enumerate(("guided brewing", "at-home routine")):
            data["creatives"].append((f"{cid}-A{n}", cid, message, "demo", "synthetic_observation"))
    campaign_by_id = {row[0]: row for row in CAMPAIGNS}
    promo_start, promo_end = start + timedelta(days=35), start + timedelta(days=48)
    outage_start, outage_end = start + timedelta(days=65), start + timedelta(days=67)
    stock_start, stock_end = start + timedelta(days=85), start + timedelta(days=87)
    data["promotions"].append(("P01", promo_start, promo_end, 8000, utc(warmup, tz=zone), "user_assumption"))
    truth = {"source_class": "evaluation_only", "seed": config["seed"], "incidents": [
        {"type": "tracking_loss", "start": str(outage_start), "end": str(outage_end)},
        {"type": "promotion", "start": str(promo_start), "end": str(promo_end)},
        {"type": "stock_constraint", "start": str(stock_start), "end": str(stock_end)},
    ]}
    sessions_by_journey = defaultdict(list)
    counter = 0
    customers = []

    def add_session(journey, customer, campaign, at):
        sid = f"S{len(data['sessions']) + 1:07d}"
        ad = f"{campaign}-A{rng.randrange(2)}" if campaign else None
        row = (sid, journey, customer, campaign, ad, at, at + timedelta(hours=1), "synthetic_observation")
        data["sessions"].append(row)
        sessions_by_journey[journey].append(row)
        return sid

    for offset in range((end - warmup).days + 1):
        day = warmup + timedelta(days=offset)
        in_stock = not stock_start <= day <= stock_end
        data["costs"].append((day, "ES601", unit_cost, utc(day, 0, tz=zone), "user_assumption"))
        data["inventory"].append((day, "ES601", 0 if not in_stock else rng.randint(70, 230), utc(day, 0, tz=zone), "synthetic_observation"))
        for cid, _, _, _, base_cvr, cpc in [*CAMPAIGNS, (None, None, None, 0, 0.07, 0)]:
            n = config["sessions_per_campaign_day"] + rng.randint(-5, 7) if cid else 10
            for _ in range(max(1, n)):
                counter += 1
                journey = f"J{counter:07d}"
                if customers and rng.random() < 0.2:
                    customer = rng.choice(customers)
                else:
                    customer = f"U{counter:07d}"
                    customers.append(customer)
                at = utc(day, rng.randint(8, 19), rng.randrange(60), zone)
                sid = add_session(journey, customer, cid, at)
                if cid and day >= warmup + timedelta(days=5) and rng.random() < 0.17:
                    alternatives = [c[0] for c in CAMPAIGNS if c[1] != campaign_by_id[cid][1]]
                    add_session(journey, customer, rng.choice(alternatives), at - timedelta(days=rng.randint(1, 4)))
                promo = promo_start <= day <= promo_end
                p = base_cvr * (1.2 if day.weekday() >= 5 else 1.0) * (1.3 if promo else 1.0)
                if not in_stock or rng.random() >= p:
                    continue
                lag = rng.choices([0, 1, 3, 6, 10], [50, 20, 15, 10, 5])[0]
                purchased = at + timedelta(days=lag, minutes=10)
                purchase_day = purchased.astimezone(ZoneInfo(zone)).date()
                # No completed purchase when this product is unavailable.
                if stock_start <= purchase_day <= stock_end:
                    continue
                if lag:
                    sid = add_session(journey, customer, None, purchased - timedelta(minutes=5))
                cancelled = rng.random() < 0.025
                qty = 2 if rng.random() < 0.025 else 1
                discount_unit = 8000 if promo_start <= purchase_day <= promo_end else 0
                # Fictional additional offer in one acquisition group.
                if cid == "C04":
                    discount_unit += 6000
                gross, discount = price * qty, discount_unit * qty
                fee = ((gross - discount) * 29 + 500) // 1000 + 30
                oid = f"O{len(data['orders']) + 1:06d}"
                data["orders"].append((oid, "1", journey, customer, "ES601", purchased,
                    purchased + timedelta(minutes=30), "cancelled" if cancelled else "fulfilled",
                    qty, gross, discount, 0 if cancelled else 1700 * qty, 0 if cancelled else fee, "synthetic_observation"))
                if not cancelled and not (outage_start <= purchase_day <= outage_end and rng.random() < 0.75):
                    data["purchases"].append((f"E{oid}", sid, oid, purchased, purchased + timedelta(hours=2), "synthetic_observation"))
                if cancelled:
                    continue
                return_p = 0.23 if cid == "C04" else 0.07
                if rng.random() < return_p:
                    returned_at = purchased + timedelta(days=rng.randint(8, 35))
                    physical = rng.random() < 0.8
                    refund = price - discount_unit if physical else min(6500, gross - discount)
                    data["refunds"].append((f"R{len(data['refunds']) + 1:05d}", oid, "1", returned_at,
                        returned_at + timedelta(hours=5), refund, 1 if physical else 0,
                        unit_cost * 8 // 10 if physical else 0, 1200 if physical else 0, 0, "synthetic_observation"))
    # Ensure assumptions exist for late purchases as well as the reporting period.
    latest = max([end, *(row[5].astimezone(ZoneInfo(zone)).date() for row in data["orders"])])
    for offset in range(1, (latest - end).days + 1):
        day = end + timedelta(days=offset)
        data["costs"].append((day, "ES601", unit_cost, utc(day, 0, tz=zone), "user_assumption"))

    claims = defaultdict(list)
    for order in data["orders"]:
        if order[7] != "fulfilled":
            continue
        oid, _, journey, _, _, purchased, *_ = order
        for channel in ("google", "meta", "affiliate"):
            eligible = [s for s in sessions_by_journey[journey]
                if s[3] and campaign_by_id[s[3]][1] == channel
                and timedelta(0) <= purchased - s[5] <= timedelta(days=campaign_by_id[s[3]][3])]
            if eligible:
                touch = max(eligible, key=lambda s: (s[5], s[0]))
                claims[(touch[3], purchased.astimezone(ZoneInfo(zone)).date())].append(
                    (purchased + timedelta(hours=12), order[9] - order[10]))
    # All platform snapshots use purchase date and pre-refund net-of-discount revenue.
    # They are replacement observations at three different extraction cutoffs.
    for offset in range((latest - warmup).days + 1):
        day = warmup + timedelta(days=offset)
        for cid, channel, *_ in CAMPAIGNS:
            group = claims[(cid, day)]
            for age in (1, 3, 7):
                snap = utc(day + timedelta(days=age), 6, tz=zone)
                visible = [c for c in group if c[0] <= snap]
                data["platform_snapshots"].append((channel, cid, day, snap, len(visible),
                    sum(c[1] for c in visible), "purchase_date", "net_of_discount_before_refunds", "synthetic_observation"))
    clicks = defaultdict(int)
    for s in data["sessions"]:
        day = s[5].astimezone(ZoneInfo(zone)).date()
        if s[3] and warmup <= day <= end:
            clicks[(day, s[3], s[4])] += 1
    for offset in range((end - warmup).days + 1):
        day = warmup + timedelta(days=offset)
        for cid, channel, _, _, _, cpc in CAMPAIGNS:
            total_spend = 0
            commission = sum(v for _, v in claims[(cid, day)]) * 6 // 100 if channel == "affiliate" else 0
            for ad_n in range(2):
                ad = f"{cid}-A{ad_n}"
                count = clicks[(day, cid, ad)]
                spend = (commission // 2 + (commission % 2 if ad_n == 0 else 0)) if channel == "affiliate" else count * cpc
                total_spend += spend
                data["media"].append((day, cid, ad, None if channel == "affiliate" else count * rng.randint(25, 60),
                    count, spend, utc(day + timedelta(days=1), 6, tz=zone), "synthetic_observation"))
            plan = 5000 if channel == "affiliate" else config["sessions_per_campaign_day"] * cpc
            data["budgets"].append((day, cid, plan, utc(warmup, 0, tz=zone), "user_assumption"))
    return data, truth
