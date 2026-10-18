import pytest
from proofline.db.connection import check_connection, get_database_url
from sqlalchemy import create_engine


def test_check_connection_succeeds_against_a_reachable_database() -> None:
    engine = create_engine("sqlite:///:memory:")

    check_connection(engine)  # must not raise


def test_check_connection_raises_against_an_unreachable_database() -> None:
    engine = create_engine("sqlite:////nonexistent/path/does-not-exist.db")

    with pytest.raises(Exception):  # noqa: B017 -- any driver error counts
        check_connection(engine)


def test_get_database_url_raises_a_clear_error_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(KeyError):
        get_database_url()


def test_get_database_url_defaults_to_sslmode_require(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")

    url = get_database_url()

    assert url.query["sslmode"] == "require"
    assert url.drivername == "postgresql+psycopg"
