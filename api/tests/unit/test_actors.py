from proofline.packet import ClientUser, Firm, Household, Person, StaffMember
from proofline.security.actors import AI_ASSISTANT_ID, load_actors

from tests.unit.factories import minimal_packet


def _packet_with_firm_and_people() -> object:
    return minimal_packet(
        household=Household(
            filing_status="married_filing_jointly",
            tax_year=2025,
            people=[
                Person(id="ngozi", role="taxpayer", name="Ngozi Okafor", ssn="1"),
                Person(id="erik", role="spouse", name="Erik Lindqvist", ssn="2"),
            ],
        ),
        firm=Firm(
            staff=[
                StaffMember(
                    id="st-01",
                    name="Priya Raman",
                    role="preparer",
                    sensitive_data_clearance=True,
                ),
                StaffMember(
                    id="st-04",
                    name="Marcus Bell",
                    role="preparer",
                    sensitive_data_clearance=False,
                ),
            ],
            client_users=[
                ClientUser(id="cu-01", name="Ngozi Okafor", role="client"),
                ClientUser(id="cu-02", name="Erik Lindqvist", role="client"),
            ],
        ),
    )


def test_staff_clearance_comes_from_sensitive_data_clearance() -> None:
    actors = load_actors(_packet_with_firm_and_people())

    assert actors["st-01"].clearance is True
    assert actors["st-04"].clearance is False


def test_client_users_are_never_cleared() -> None:
    actors = load_actors(_packet_with_firm_and_people())

    assert actors["cu-01"].role == "client"
    assert actors["cu-01"].clearance is False


def test_client_user_matched_to_household_person_by_name() -> None:
    actors = load_actors(_packet_with_firm_and_people())

    assert actors["cu-01"].household_person_id == "ngozi"
    assert actors["cu-02"].household_person_id == "erik"


def test_client_user_matched_by_case_insensitive_fallback() -> None:
    packet = minimal_packet(
        household=Household(
            filing_status="married_filing_jointly",
            tax_year=2025,
            people=[Person(id="ngozi", role="taxpayer", name="NGOZI OKAFOR", ssn="1")],
        ),
        firm=Firm(
            client_users=[ClientUser(id="cu-01", name="Ngozi Okafor", role="client")]
        ),
    )

    actors = load_actors(packet)

    assert actors["cu-01"].household_person_id == "ngozi"


def test_client_user_with_no_matching_household_person_gets_none() -> None:
    packet = minimal_packet(
        firm=Firm(client_users=[ClientUser(id="cu-09", name="Nobody", role="client")])
    )

    actors = load_actors(packet)

    assert actors["cu-09"].household_person_id is None


def test_ai_assistant_actor_exists_and_is_never_cleared() -> None:
    actors = load_actors(_packet_with_firm_and_people())

    ai_assistant = actors[AI_ASSISTANT_ID]
    assert ai_assistant.role == "ai_assistant"
    assert ai_assistant.clearance is False


def test_unknown_actor_id_is_not_in_the_map() -> None:
    actors = load_actors(_packet_with_firm_and_people())

    assert "no-such-actor" not in actors
