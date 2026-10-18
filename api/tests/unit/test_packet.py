from proofline.packet import load_packet

from tests.unit.factories import minimal_packet


def test_load_packet_is_cached_singleton() -> None:
    first = load_packet()
    second = load_packet()
    assert first is second


def test_load_packet_known_values() -> None:
    packet = load_packet()
    assert packet.household.filing_status == "married_filing_jointly"
    assert len(packet.household.people) == 4
    assert len(packet.documents) == 74
    assert len(packet.extracted_values) == 3012
    assert {rv.version for rv in packet.return_versions} == {"v1", "v2", "v3"}


def test_minimal_packet_factory_builds() -> None:
    packet = minimal_packet()
    assert packet.household.people[0].role == "taxpayer"
    assert packet.documents == []
    assert packet.return_version("v3").lines == []
