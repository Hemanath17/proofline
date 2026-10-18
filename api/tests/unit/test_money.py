from decimal import Decimal

import pytest
from proofline.checks.money import parse_bool, parse_money


def test_none_is_none() -> None:
    assert parse_money(None) is None


def test_int_and_float() -> None:
    assert parse_money(100) == Decimal(100)
    assert parse_money(71965.0) == Decimal("71965.0")


def test_printed_string_with_comma_and_cents() -> None:
    assert parse_money("71,965.00") == Decimal("71965.00")


def test_printed_string_with_dollar_sign() -> None:
    assert parse_money("$1,234.50") == Decimal("1234.50")


def test_printed_string_omitting_cents() -> None:
    assert parse_money("8,400") == Decimal(8400)


def test_parenthesized_is_negative() -> None:
    assert parse_money("(500.00)") == Decimal("-500.00")


def test_leading_minus_is_negative() -> None:
    assert parse_money("-500.00") == Decimal("-500.00")


def test_blank_string_is_none() -> None:
    assert parse_money("") is None
    assert parse_money("   ") is None


def test_decimal_passes_through() -> None:
    assert parse_money(Decimal("12.34")) == Decimal("12.34")


def test_garbage_string_raises() -> None:
    with pytest.raises(ValueError):
        parse_money("not a number")


def test_bool_raises_value_error_not_invalid_operation() -> None:
    """bool is a subclass of int, so True/False must be rejected explicitly
    before the int/float branch -- otherwise Decimal(str(True)) raises
    decimal.InvalidOperation, which callers expecting ValueError don't
    catch."""
    with pytest.raises(ValueError):
        parse_money(True)
    with pytest.raises(ValueError):
        parse_money(False)


def test_parse_bool_from_real_bool() -> None:
    assert parse_bool(True) is True
    assert parse_bool(False) is False


def test_parse_bool_from_zero_one() -> None:
    assert parse_bool(1) is True
    assert parse_bool(0) is False
    assert parse_bool(1.0) is True
    assert parse_bool(0.0) is False


def test_parse_bool_from_text() -> None:
    assert parse_bool("true") is True
    assert parse_bool("True") is True
    assert parse_bool("Yes") is True
    assert parse_bool("Y") is True
    assert parse_bool("false") is False
    assert parse_bool("No") is False
    assert parse_bool("n") is False
    assert parse_bool("0") is False
    assert parse_bool("1") is True


def test_parse_bool_unknown_is_none_not_an_exception() -> None:
    assert parse_bool(None) is None
    assert parse_bool("maybe") is None
    assert parse_bool(2) is None
    assert parse_bool([]) is None
