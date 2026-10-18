from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from proofline.db.models import Base
from proofline.db.repository import get_event, insert_event


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_insert_and_get_event(session: Session) -> None:
    written = insert_event(session, "test_event", {"foo": "bar"})

    read_back = get_event(session, written.id)

    assert read_back is not None
    assert read_back.id == written.id
    assert read_back.event_type == "test_event"
    assert read_back.payload == {"foo": "bar"}
    assert read_back.schema_version == 1


def test_get_event_missing_returns_none(session: Session) -> None:
    import uuid

    assert get_event(session, uuid.uuid4()) is None
