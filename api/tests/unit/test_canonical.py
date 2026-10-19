from decimal import Decimal

from proofline.db.canonical import (
    canonical_hash,
    prepare_payload_for_storage,
    to_canonical_json,
)
from proofline.db.models import Base, Event
from proofline.db.repository import insert_event
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_prepare_payload_for_storage_converts_decimal_to_string() -> None:
    payload = {"amount": Decimal("15535.56"), "nested": {"value": Decimal("1.00")}}

    prepared = prepare_payload_for_storage(payload)

    assert prepared == {"amount": "15535.56", "nested": {"value": "1.00"}}


def test_prepare_payload_for_storage_converts_decimal_inside_list() -> None:
    payload = {"amounts": [Decimal("1.50"), Decimal("2.50")]}

    prepared = prepare_payload_for_storage(payload)

    assert prepared == {"amounts": ["1.50", "2.50"]}


def test_to_canonical_json_sorts_keys() -> None:
    first = to_canonical_json({"b": 1, "a": 2})
    second = to_canonical_json({"a": 2, "b": 1})

    assert first == second == '{"a":2,"b":1}'


def test_canonical_hash_is_stable_regardless_of_key_order() -> None:
    assert canonical_hash({"b": 1, "a": 2}) == canonical_hash({"a": 2, "b": 1})


def test_canonical_hash_differs_for_different_payloads() -> None:
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_insert_event_with_decimal_in_payload_does_not_crash() -> None:
    """Regression: before `prepare_payload_for_storage` was wired into
    `insert_event`, a `Decimal` in a payload crashed the save because
    Python's default JSON encoder can't serialize it."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        event = insert_event(session, "test_event", {"tax_effect": Decimal("15535.56")})
        session.commit()

        read_back = session.get(Event, event.id)
        assert read_back is not None
        assert read_back.payload == {"tax_effect": "15535.56"}
