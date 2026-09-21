"""Deterministic fraud-pattern detectors. No LLM. Operate on retrieved txn dicts."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

SMALL_AUTH_USD = 5.0
TESTING_FOLLOW_USD = 20.0
TESTING_WINDOW = timedelta(hours=1)
TESTING_FOLLOW_WINDOW = timedelta(hours=2)
CNP_BURST_WINDOW = timedelta(hours=48)
TRIP_DAYS = 3


def _ts(row: dict[str, Any]) -> datetime | None:
    value = row.get("ts")
    if isinstance(value, datetime):
        return value
    return None


def _amt(row: dict[str, Any]) -> float:
    try:
        return abs(float(row.get("amount") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _sorted(txns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(txns, key=lambda t: (_ts(t) or datetime.min, str(t.get("txn_id", ""))))


def empty_match(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "matched": False,
        "txn_ids": [],
        "details": "",
        "strength": 0.0,
        "entity_ids": [],
    }
    if extra:
        out.update(extra)
    return out


def detect_card_testing(txns: list[dict[str, Any]], around_txn_id: str | None = None) -> dict[str, Any]:
    """3+ small online auths on one card within ~1h, followed by a larger purchase."""
    online = [t for t in _sorted(txns) if t.get("channel") == "online" and _ts(t) is not None]
    if len(online) < 4:
        return empty_match()

    best: dict[str, Any] | None = None
    for i, start in enumerate(online):
        window_end = _ts(start) + TESTING_WINDOW
        cluster = [start]
        for nxt in online[i + 1 :]:
            if _ts(nxt) <= window_end and _amt(nxt) < SMALL_AUTH_USD:
                cluster.append(nxt)
            elif _ts(nxt) > window_end:
                break
        smalls = [t for t in cluster if _amt(t) < SMALL_AUTH_USD]
        if len(smalls) < 3:
            continue
        last_small_ts = _ts(smalls[-1])
        follow = None
        for nxt in online:
            if _ts(nxt) <= last_small_ts:
                continue
            if _ts(nxt) > last_small_ts + TESTING_FOLLOW_WINDOW:
                break
            if _amt(nxt) >= TESTING_FOLLOW_USD and _amt(nxt) > max(_amt(s) for s in smalls) * 3:
                follow = nxt
                break
        if follow is None:
            continue
        ids = [str(t["txn_id"]) for t in smalls] + [str(follow["txn_id"])]
        if around_txn_id and around_txn_id not in ids and around_txn_id not in {str(t["txn_id"]) for t in online}:
            continue
        strength = min(0.95, 0.55 + 0.08 * (len(smalls) - 3) + (0.15 if _amt(follow) > 100 else 0.0))
        cand = {
            "matched": True,
            "txn_ids": ids,
            "details": (
                f"{len(smalls)} online authorizations under ${SMALL_AUTH_USD:.0f} within one hour, "
                f"followed by a ${_amt(follow):.2f} purchase"
            ),
            "strength": strength,
            "entity_ids": ids,
            "large_cleared": _amt(follow) > 100,
            "large_amount": _amt(follow),
        }
        if best is None or cand["strength"] > best["strength"]:
            best = cand
    return best or empty_match({"large_cleared": False})


def detect_cnp(txns: list[dict[str, Any]], around_txn_id: str | None = None) -> dict[str, Any]:
    """Unusual online use / burst vs card history."""
    ordered = [t for t in _sorted(txns) if _ts(t) is not None]
    if not ordered:
        return empty_match()
    flagged = None
    if around_txn_id:
        flagged = next((t for t in ordered if str(t.get("txn_id")) == str(around_txn_id)), None)
    if flagged is None:
        flagged = ordered[-1]
    if flagged.get("channel") != "online":
        return empty_match()

    prior = [t for t in ordered if _ts(t) < _ts(flagged)]
    online_prior = [t for t in prior if t.get("channel") == "online"]
    burst = [
        t
        for t in ordered
        if t.get("channel") == "online"
        and abs((_ts(t) - _ts(flagged)).total_seconds()) <= CNP_BURST_WINDOW.total_seconds()
    ]
    burst_ids = [str(t["txn_id"]) for t in burst]
    unusual_amount = False
    new_product = False
    if online_prior:
        med = sorted(_amt(t) for t in online_prior)[len(online_prior) // 2]
        if med > 0 and _amt(flagged) > max(3 * med, med + 50):
            unusual_amount = True
        products = {t.get("product_cd") for t in online_prior if t.get("product_cd")}
        if flagged.get("product_cd") and products and flagged.get("product_cd") not in products:
            new_product = True
    elif _amt(flagged) >= 200:
        unusual_amount = True

    burst_hit = len(burst) >= 2
    matched = burst_hit or unusual_amount or new_product
    if not matched:
        return empty_match()
    strength = 0.25 + 0.12 * min(len(burst), 4) + (0.15 if unusual_amount else 0) + (0.1 if new_product else 0)
    details = []
    if burst_hit:
        details.append(f"{len(burst)} online transactions within 48 hours")
    if unusual_amount:
        details.append(f"amount ${_amt(flagged):.2f} diverges from prior online history")
    if new_product:
        details.append(f"product code {flagged.get('product_cd')} is new for this card")
    return {
        "matched": True,
        "txn_ids": burst_ids or [str(flagged["txn_id"])],
        "details": "; ".join(details),
        "strength": min(0.85, strength),
        "entity_ids": burst_ids or [str(flagged["txn_id"])],
        "single_unusual": (not burst_hit) and (unusual_amount or new_product),
    }


def detect_new_device_cnp(txns: list[dict[str, Any]], around_txn_id: str | None = None) -> dict[str, Any]:
    cnp = detect_cnp(txns, around_txn_id)
    ordered = [t for t in _sorted(txns) if _ts(t) is not None]
    flagged = None
    if around_txn_id:
        flagged = next((t for t in ordered if str(t.get("txn_id")) == str(around_txn_id)), None)
    if flagged is None and ordered:
        flagged = ordered[-1]
    if flagged is None:
        return empty_match()
    status = str(flagged.get("device_status") or "").strip()
    proxy = str(flagged.get("proxy") or "").strip().lower()
    is_new = status.lower() == "new"
    proxy_hit = proxy in {"anonymous", "hidden", "true", "1", "yes"}
    if not is_new and not (cnp["matched"] and proxy_hit):
        return empty_match()
    if not is_new and not cnp["matched"]:
        return empty_match()
    device_id = flagged.get("device_id") or ""
    ids = list(dict.fromkeys((cnp.get("txn_ids") or [str(flagged["txn_id"])]) + ([device_id] if device_id else [])))
    strength = (cnp.get("strength") or 0.2) + (0.18 if is_new else 0) + (0.1 if proxy_hit else 0)
    bits = []
    if is_new:
        bits.append("device marked New for this account")
    if proxy_hit:
        bits.append(f"proxy={proxy}")
    if cnp.get("details"):
        bits.append(cnp["details"])
    return {
        "matched": True,
        "txn_ids": cnp.get("txn_ids") or [str(flagged["txn_id"])],
        "details": "; ".join(bits),
        "strength": min(0.9, strength),
        "entity_ids": ids,
        "device_id": device_id,
        "is_new": is_new,
        "proxy": proxy if proxy_hit else "",
    }


def detect_out_of_region(txns: list[dict[str, Any]], around_txn_id: str | None = None) -> dict[str, Any]:
    """Card-present (or billed) activity in a region with no history, while home activity continues."""
    ordered = [t for t in _sorted(txns) if _ts(t) is not None and t.get("addr1")]
    if len(ordered) < 3:
        return empty_match()
    flagged = None
    if around_txn_id:
        flagged = next((t for t in ordered if str(t.get("txn_id")) == str(around_txn_id)), None)
    if flagged is None:
        flagged = ordered[-1]
    prior = [t for t in ordered if _ts(t) < _ts(flagged)]
    if len(prior) < 2:
        return empty_match()
    counts = Counter(str(t.get("addr1")) for t in prior)
    home, home_n = counts.most_common(1)[0]
    if home_n / max(len(prior), 1) < 0.4:
        return empty_match()
    current = str(flagged.get("addr1"))
    if not current or current == home:
        return empty_match()
    foreign = [
        t
        for t in ordered
        if str(t.get("addr1")) == current
        and abs((_ts(t) - _ts(flagged)).total_seconds()) <= timedelta(days=7).total_seconds()
    ]
    span_days = 0.0
    if len(foreign) >= 2:
        span_days = (_ts(foreign[-1]) - _ts(foreign[0])).total_seconds() / 86400.0
    home_overlap = [
        t
        for t in ordered
        if str(t.get("addr1")) == home
        and abs((_ts(t) - _ts(flagged)).days) <= 2
    ]
    # Several days in one new region with no home overlap → trip, not clone.
    if span_days >= TRIP_DAYS and not home_overlap:
        return empty_match({"details": "multi-day new-region activity consistent with travel"})
    if not home_overlap and len(foreign) <= 1 and flagged.get("channel") != "in_person":
        return empty_match()
    matched = current != home and (bool(home_overlap) or (flagged.get("channel") == "in_person" and home_n >= 3))
    if not matched:
        return empty_match()
    ids = [str(t["txn_id"]) for t in foreign]
    return {
        "matched": True,
        "txn_ids": ids,
        "details": (
            f"Activity in billing region {current} with no prior history; "
            f"home region {home} {'continues' if home_overlap else 'is established historically'}"
        ),
        "strength": 0.55 if home_overlap else 0.35,
        "entity_ids": ids + [current, home],
        "home_region": home,
        "foreign_region": current,
        "home_overlap": bool(home_overlap),
    }


def detect_account_takeover(txns: list[dict[str, Any]], around_txn_id: str | None = None) -> dict[str, Any]:
    ordered = [t for t in _sorted(txns) if _ts(t) is not None]
    if len(ordered) < 2:
        return empty_match()
    flagged = None
    if around_txn_id:
        flagged = next((t for t in ordered if str(t.get("txn_id")) == str(around_txn_id)), None)
    if flagged is None:
        flagged = ordered[-1]
    window = [
        t
        for t in ordered
        if abs((_ts(t) - _ts(flagged)).total_seconds()) <= timedelta(days=2).total_seconds()
    ]
    channels = {t.get("channel") for t in window if t.get("channel") in {"online", "in_person"}}
    mixed = len(channels) >= 2
    new_dev = str(flagged.get("device_status") or "").lower() == "new"
    proxy = str(flagged.get("proxy") or "").strip().lower() in {"anonymous", "hidden"}
    prior = [t for t in ordered if _ts(t) < _ts(flagged)]
    unusual = False
    if prior:
        med = sorted(_amt(t) for t in prior)[len(prior) // 2]
        unusual = med > 0 and _amt(flagged) > 4 * med
    devices = {t.get("device_id") for t in window if t.get("device_id")}
    device_shift = len(devices) >= 2
    score = (0.2 if mixed else 0) + (0.2 if new_dev else 0) + (0.15 if proxy else 0) + (0.15 if unusual else 0) + (0.1 if device_shift else 0)
    if score < 0.35:
        return empty_match()
    bits = []
    if mixed:
        bits.append("mixed-channel activity in a 48h window")
    if new_dev:
        bits.append("new device")
    if proxy:
        bits.append("proxy connection")
    if unusual:
        bits.append("amount inconsistent with history")
    if device_shift:
        bits.append("multiple device profiles")
    ids = [str(t["txn_id"]) for t in window]
    return {
        "matched": True,
        "txn_ids": ids,
        "details": "; ".join(bits),
        "strength": min(0.88, score + 0.2),
        "entity_ids": ids,
        "credentials_compromised_hint": mixed and new_dev,
    }


def detect_shared_origin(
    txns: list[dict[str, Any]],
    card_id: str,
    device_cards: dict[str, set[str]],
    email_cards: dict[str, set[str]],
    region_cards: dict[str, set[str]],
    around_txn_id: str | None = None,
) -> dict[str, Any]:
    """Cards sharing a device, recipient email, or (rare) billing region."""
    flagged = None
    if around_txn_id:
        flagged = next((t for t in txns if str(t.get("txn_id")) == str(around_txn_id)), None)
    if flagged is None and txns:
        flagged = _sorted(txns)[-1]
    if flagged is None:
        return empty_match({"shared_element": "", "connected_card_ids": []})

    candidates: list[tuple[str, str, set[str]]] = []
    device_id = flagged.get("device_id") or ""
    if device_id and device_id in device_cards:
        others = set(device_cards[device_id]) - {card_id}
        if others:
            candidates.append(("device", device_id, others))
    r_email = flagged.get("r_email") or ""
    if r_email and r_email in email_cards:
        others = set(email_cards[r_email]) - {card_id}
        if others:
            candidates.append(("recipient_email", r_email, others))
    region = str(flagged.get("addr1") or "")
    if region and region in region_cards:
        others = set(region_cards[region]) - {card_id}
        # Popular regions connect thousands of cards — only treat as shared origin if small cluster.
        if 1 <= len(others) <= 12:
            candidates.append(("billing_region", region, others))

    if not candidates:
        return empty_match({"shared_element": "", "connected_card_ids": []})
    kind, element, others = max(candidates, key=lambda x: len(x[2]))
    connected = sorted(others)
    return {
        "matched": True,
        "txn_ids": [str(flagged["txn_id"])],
        "details": f"shared {kind} {element} links {len(connected)} other card(s)",
        "strength": min(0.8, 0.35 + 0.08 * min(len(connected), 6)),
        "entity_ids": [element, card_id] + connected[:12],
        "shared_element": kind,
        "shared_value": element,
        "connected_card_ids": connected,
    }


def detect_recurring_legitimate(txns: list[dict[str, Any]], around_txn_id: str | None = None) -> dict[str, Any]:
    """Same amount repeating on a roughly monthly cadence — disputed-but-legitimate signal (R7)."""
    ordered = [t for t in _sorted(txns) if _ts(t) is not None and _amt(t) > 0]
    if not ordered:
        return empty_match()
    flagged = None
    if around_txn_id:
        flagged = next((t for t in ordered if str(t.get("txn_id")) == str(around_txn_id)), None)
    if flagged is None:
        return empty_match()
    target = round(_amt(flagged), 2)
    same = [t for t in ordered if abs(_amt(t) - target) < 0.05]
    if len(same) < 3:
        return empty_match()
    gaps = []
    same_sorted = _sorted(same)
    for a, b in zip(same_sorted, same_sorted[1:]):
        gaps.append((_ts(b) - _ts(a)).days)
    monthly = [g for g in gaps if 25 <= g <= 35]
    if len(monthly) < 2:
        return empty_match()
    return {
        "matched": True,
        "txn_ids": [str(t["txn_id"]) for t in same_sorted],
        "details": f"amount ${target:.2f} repeats on a ~monthly cadence ({len(same)} occurrences)",
        "strength": 0.7,
        "entity_ids": [str(t["txn_id"]) for t in same_sorted],
    }
