from datetime import datetime, timedelta

from graph.patterns import (
    detect_account_takeover,
    detect_card_testing,
    detect_cnp,
    detect_new_device_cnp,
    detect_out_of_region,
    detect_recurring_legitimate,
    detect_shared_origin,
)


def _t(i, ts, amount, channel="online", **kw):
    row = {
        "txn_id": f"T{i}",
        "ts": ts,
        "amount": amount,
        "channel": channel,
        "product_cd": kw.get("product_cd", "C"),
        "addr1": kw.get("addr1", "100"),
        "device_status": kw.get("device_status", ""),
        "proxy": kw.get("proxy", ""),
        "device_id": kw.get("device_id", ""),
        "r_email": kw.get("r_email", ""),
    }
    return row


def test_card_testing_sequence():
    t0 = datetime(2016, 11, 1, 10, 0)
    txns = [
        _t(1, t0, 2),
        _t(2, t0 + timedelta(minutes=10), 1.5),
        _t(3, t0 + timedelta(minutes=20), 0.99),
        _t(4, t0 + timedelta(minutes=50), 250),
    ]
    hit = detect_card_testing(txns)
    assert hit["matched"]
    assert hit["large_cleared"]
    assert "T1" in hit["txn_ids"]


def test_cnp_burst():
    t0 = datetime(2016, 11, 1, 10, 0)
    hist = [_t(0, t0 - timedelta(days=20), 15, product_cd="C")]
    burst = [
        _t(1, t0, 90, product_cd="H"),
        _t(2, t0 + timedelta(hours=3), 80, product_cd="H"),
    ]
    hit = detect_cnp(hist + burst, around_txn_id="T2")
    assert hit["matched"]


def test_new_device():
    t0 = datetime(2016, 11, 1, 10, 0)
    txns = [
        _t(1, t0 - timedelta(days=10), 20),
        _t(2, t0, 90, device_status="New", proxy="anonymous", device_id="D1"),
        _t(3, t0 + timedelta(hours=2), 80, device_status="New", device_id="D1"),
    ]
    hit = detect_new_device_cnp(txns, around_txn_id="T2")
    assert hit["matched"]
    assert hit["is_new"]


def test_out_of_region_with_home_overlap():
    t0 = datetime(2016, 11, 20, 15, 0)
    txns = [
        _t(1, t0 - timedelta(days=40), 20, channel="in_person", addr1="300"),
        _t(2, t0 - timedelta(days=20), 22, channel="in_person", addr1="300"),
        _t(3, t0, 85, channel="in_person", addr1="999"),
        _t(4, t0 + timedelta(hours=20), 18, channel="in_person", addr1="300"),
    ]
    hit = detect_out_of_region(txns, around_txn_id="T3")
    assert hit["matched"]
    assert hit["home_overlap"]


def test_shared_origin_device():
    txns = [_t(1, datetime(2016, 11, 1), 10, device_id="DEV")]
    hit = detect_shared_origin(
        txns,
        "C1",
        device_cards={"DEV": {"C1", "C2", "C3"}},
        email_cards={},
        region_cards={},
        around_txn_id="T1",
    )
    assert hit["matched"]
    assert hit["shared_element"] == "device"
    assert "C2" in hit["connected_card_ids"]


def test_recurring():
    t0 = datetime(2016, 8, 1)
    txns = [
        _t(1, t0, 12, channel="in_person"),
        _t(2, t0.replace(month=9), 12, channel="in_person"),
        _t(3, t0.replace(month=10), 12, channel="in_person"),
    ]
    hit = detect_recurring_legitimate(txns, around_txn_id="T3")
    assert hit["matched"]


def test_account_takeover_needs_several_signals():
    t0 = datetime(2016, 11, 1, 10, 0)
    txns = [
        _t(1, t0 - timedelta(days=10), 20, channel="in_person"),
        _t(2, t0, 200, channel="online", device_status="New", proxy="hidden", device_id="Dnew"),
        _t(3, t0 + timedelta(hours=5), 15, channel="in_person", device_id="Dold"),
    ]
    hit = detect_account_takeover(txns, around_txn_id="T2")
    assert hit["matched"]
