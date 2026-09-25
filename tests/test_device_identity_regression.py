"""Generic regression tests for canonical device IDs and entity identity resolution."""
from __future__ import annotations

import pytest

from graph.ids import device_profile_id, stringify
from graph.local_store import LocalGraphStore
from graph.patterns import COMMON_EMAIL_DOMAINS, detect_shared_origin
from graph.toolkit import GraphToolkit


def test_device_profile_id_canonical_generic():
    # Empty components
    assert device_profile_id("", "", "", "") == ""
    assert device_profile_id("   ", "  \t ", "\n", "") == ""

    # All components present with padding
    id1 = device_profile_id("  Samsung SM-G935F  ", " Android 7.0 ", " chrome 62.0 ", " 1920x1080 ")
    assert id1 == "Samsung SM-G935F | Android 7.0 | chrome 62.0 | 1920x1080"
    assert not id1.endswith(" ")
    assert not id1.startswith(" ")

    # Missing middle or end components
    id2 = device_profile_id("Windows", "", "edge 16.0", "")
    assert id2 == "Windows |  | edge 16.0 |"
    assert not id2.endswith(" ")
    assert not id2.startswith(" ")

    id3 = device_profile_id("", "", "chrome 66.0", "")
    assert id3 == "|  | chrome 66.0 |"
    assert not id3.endswith(" ")

    id4 = device_profile_id("", "", "firefox 47.0", "")
    assert id4 == "|  | firefox 47.0 |"
    assert not id4.endswith(" ")

    id5 = device_profile_id("SM-G610F Build/NRD90M", "", "chrome 66.0 for android", "")
    assert id5 == "SM-G610F Build/NRD90M |  | chrome 66.0 for android |"
    assert not id5.endswith(" ")


def test_device_lookup_consistency():
    store = LocalGraphStore()
    dev_id = device_profile_id("  TestDev  ", " OS X ", " Safari ", " 1440x900 ")
    store.add_transaction({
        "txn_id": "T1001",
        "card_id": "C001-K1",
        "customer_id": "C001",
        "amount": 50.0,
        "channel": "online",
        "device_id": dev_id,
        "device_info": "TestDev",
        "os": "OS X",
        "browser": "Safari",
        "screen": "1440x900",
    })
    store.finalize_indexes()
    toolkit = GraphToolkit(store)

    neigh = toolkit.device_neighbors(dev_id)
    assert neigh["device_id"] == dev_id
    assert "C001-K1" in neigh["cards"]
    assert "T1001" in neigh["txns"]


def test_shared_origin_ignores_common_domains():
    txns = [{"txn_id": "T1", "amount": 100, "channel": "online", "r_email": "gmail.com"}]
    device_cards = {}
    email_cards = {"gmail.com": {f"C{i}-K1" for i in range(1000)}}
    region_cards = {}
    hit = detect_shared_origin(txns, "C0-K1", device_cards, email_cards, region_cards, around_txn_id="T1")
    assert not hit["matched"]
    assert hit["connected_card_ids"] == []


def test_shared_origin_detects_small_custom_cluster():
    txns = [{"txn_id": "T1", "amount": 100, "channel": "online", "r_email": "custom-fraud-hub.biz"}]
    device_cards = {}
    email_cards = {"custom-fraud-hub.biz": {"C0-K1", "C1-K1", "C2-K1"}}
    region_cards = {}
    hit = detect_shared_origin(txns, "C0-K1", device_cards, email_cards, region_cards, around_txn_id="T1")
    assert hit["matched"]
    assert hit["shared_element"] == "recipient_email"
    assert "C1-K1" in hit["connected_card_ids"]
    assert "C2-K1" in hit["connected_card_ids"]
