import logging

from proofline.packet import load_packet
from proofline.security.redact import (
    RedactingLogFilter,
    SensitiveValue,
    collect_sensitive_values,
    generate_variants,
    mask,
    redact_json,
    redact_text,
    values_present_in,
)


def test_mask_keeps_last_four_characters() -> None:
    assert mask("666-74-3390") == "***-**-3390"


def test_mask_short_value_is_left_alone() -> None:
    assert mask("4321") == "4321"


def test_generate_variants_includes_dashed_spaced_and_bare_ssn() -> None:
    variants = generate_variants("666-41-2287")

    assert "666-41-2287" in variants
    assert "666412287" in variants
    assert "666 41 2287" in variants


def test_collect_sensitive_values_finds_household_ssns_and_ip_pin() -> None:
    packet = load_packet()

    values = collect_sensitive_values(packet)
    categories = {v.category for v in values}
    household_ssns = {p.ssn for p in packet.household.people}

    assert "ssn" in categories
    assert "ip_pin" in categories
    assert household_ssns <= {v.value for v in values if v.category == "ssn"}


def test_collect_sensitive_values_finds_timeline_efile_pins() -> None:
    packet = load_packet()

    values = collect_sensitive_values(packet)
    pins = {v.value for v in values if v.category == "efile_pin"}

    assert "41207" in pins
    assert "88310" in pins


def test_redact_text_masks_known_value_in_any_variant() -> None:
    values = [SensitiveValue("666-41-2287", "ssn")]

    assert redact_text("SSN: 666-41-2287", values) == "SSN: ***-**-2287"
    assert redact_text("SSN: 666412287", values) == "SSN: ***-**-2287"
    assert redact_text("SSN: 666 41 2287", values) == "SSN: ***-**-2287"


def test_redact_text_backstop_catches_an_unlisted_ssn_shaped_string() -> None:
    redacted = redact_text("New SSN found: 123-45-6789", [])

    assert "123-45-6789" not in redacted
    assert "6789" in redacted


def test_redact_text_backstop_catches_a_pin_in_context() -> None:
    redacted = redact_text("spouse PIN 88310 was entered", [])

    assert "88310" not in redacted
    assert "8310" in redacted


def test_redact_text_on_empty_string_returns_it_unchanged() -> None:
    assert redact_text("", [SensitiveValue("666-41-2287", "ssn")]) == ""


def test_redact_text_leaves_unrelated_numbers_alone() -> None:
    text = "Submission 71530420261940012345 accepted on 2026-07-13"

    redacted = redact_text(text, [])

    assert redacted == text


def test_redact_json_walks_nested_structures() -> None:
    values = [SensitiveValue("666-41-2287", "ssn")]
    data = {"people": [{"name": "Ngozi", "ssn": "666-41-2287"}], "other": 42}

    redacted = redact_json(data, values)

    assert redacted["people"][0]["ssn"] == "***-**-2287"
    assert redacted["other"] == 42


def test_values_present_in_detects_a_matching_variant() -> None:
    values = [SensitiveValue("666-41-2287", "ssn")]

    found = values_present_in("employee ssn 666412287", values)

    assert [v.value for v in found] == ["666-41-2287"]


def test_values_present_in_empty_when_nothing_matches() -> None:
    values = [SensitiveValue("666-41-2287", "ssn")]

    assert values_present_in("nothing sensitive here", values) == []


def test_logging_filter_masks_sensitive_value_in_log_record() -> None:
    packet = load_packet()
    ssn = packet.household.people[0].ssn
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"saw ssn {ssn}",
        args=(),
        exc_info=None,
    )

    RedactingLogFilter().filter(record)

    assert ssn not in record.getMessage()


def test_logging_filter_survives_a_record_whose_message_cannot_be_formatted() -> None:
    """getMessage() itself can raise (e.g. a %-style msg with args that
    don't match it) -- the filter must let the record through unmasked
    rather than crashing the logging call that triggered it."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="value is %d",
        args=("not-a-number",),
        exc_info=None,
    )

    result = RedactingLogFilter().filter(record)

    assert result is True
