"""Vimshottari dasha: hand-verifiable invariants and known cases.

These use synthetic Moon longitudes chosen so the expected lord and balance can
be computed by hand — no ephemeris needed, so the test is fast and exact.
"""

from datetime import datetime, timezone

import pytest

from app.modules.astrology_engine.vimshottari import (
    DASHA_SEQUENCE,
    _NAK_SPAN,
    compute_vimshottari_dasha,
)

_BIRTH = datetime(1990, 1, 15, 7, 45, tzinfo=timezone.utc)


def test_sequence_sums_to_120_years():
    assert sum(years for _, years in DASHA_SEQUENCE) == 120


def test_start_of_ashwini_is_full_ketu():
    # Moon at 0° = very start of Ashwini (Ketu's nakshatra): nothing traversed,
    # so the full 7-year Ketu mahadasha remains.
    d = compute_vimshottari_dasha(0.0, _BIRTH)
    assert d["starting_lord"] == "ketu"
    assert d["balance_at_birth"]["years"] == pytest.approx(7.0)


def test_halfway_into_ashwini_is_half_ketu():
    # Halfway through Ashwini → half of Ketu's 7 years remain.
    d = compute_vimshottari_dasha(_NAK_SPAN / 2, _BIRTH)
    assert d["starting_lord"] == "ketu"
    assert d["balance_at_birth"]["years"] == pytest.approx(3.5)


def test_middle_of_fourth_nakshatra_is_moon():
    # Rohini (nakshatra index 3) is ruled by the Moon. Sit the Moon squarely in
    # the middle of it → exactly half of the Moon's 10-year period remains.
    # (Aim mid-nakshatra, not on a cusp, to avoid float boundary ambiguity.)
    d = compute_vimshottari_dasha(_NAK_SPAN * 3 + _NAK_SPAN / 2, _BIRTH)
    assert d["starting_lord"] == "chandra"
    assert d["balance_at_birth"]["years"] == pytest.approx(5.0)


def test_mahadasha_order_and_dates_are_contiguous():
    d = compute_vimshottari_dasha(0.0, _BIRTH)
    mahas = d["mahadashas"]
    assert len(mahas) == 9
    # First lord is Ketu, sequence wraps in canonical order.
    assert [m["lord"] for m in mahas][:3] == ["ketu", "shukran", "surya"]
    # Each mahadasha ends exactly where the next begins.
    for a, b in zip(mahas, mahas[1:]):
        assert a["end"] == b["start"]
    # Only the first straddles birth.
    assert mahas[0]["partial_at_birth"] is True
    assert all(not m["partial_at_birth"] for m in mahas[1:])


def test_current_period_lookup():
    # 3 years after birth, still inside the 7-year Ketu mahadasha at 0° start.
    as_of = datetime(1993, 1, 15, tzinfo=timezone.utc)
    d = compute_vimshottari_dasha(0.0, _BIRTH, as_of=as_of)
    assert d["current"] is not None
    assert d["current"]["mahadasha"]["lord"] == "ketu"
    # The antardasha at `as_of` should be a real sub-period with dates around it.
    antar = d["current"]["antardasha"]
    assert antar is not None
    assert antar["start"] <= as_of.isoformat() < antar["end"]


def test_antardashas_span_their_mahadasha():
    d = compute_vimshottari_dasha(0.0, _BIRTH, antardasha=True)
    maha = d["mahadashas"][0]
    subs = maha["antardashas"]
    assert len(subs) == 9
    # Sub-periods start with the mahadasha lord and cover the whole span.
    assert subs[0]["lord"] == "ketu"
    assert subs[0]["start"] == maha["start"]
    assert subs[-1]["end"] == maha["end"]
