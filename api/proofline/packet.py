"""The only code that opens api/data/packet.json.

Loaded once per process (`load_packet()` is cached) and kept in memory as
typed Pydantic models. Sections that nothing outside this module inspects
yet (prior_years, tax_agency_records, engine_reference, fx_rates,
post_filing_rates, planning_reference_2026) stay loosely typed — a
container plus a plain dict payload is enough for JSON-pointer resolution,
and there is no need to model fields nobody reads.
"""

from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

_PACKET_PATH = Path(__file__).resolve().parent.parent / "data" / "packet.json"


class PacketMeta(BaseModel):
    name: str
    version: str
    generated: str
    client_id: str


class Address(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str | None = None
    address: str
    type: str


class Residency(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    state: str
    from_: str = Field(alias="from")
    to: str | None = None
    status: str


class Person(BaseModel):
    id: str
    role: str
    name: str
    ssn: str
    dob: str | None = None
    occupation: str | None = None
    ip_pin: str | None = None
    phone: str | None = None
    email: str | None = None
    relationship: str | None = None
    months_lived_with_you: int | None = None
    full_time_student: bool | None = None
    note: str | None = None
    own_income: Any = None


class BankAccount(BaseModel):
    routing: str
    account: str
    type: str
    bank: str


class Household(BaseModel):
    filing_status: str
    tax_year: int
    entered_by: str | None = None
    people: list[Person]
    addresses: list[Address] = []
    residency: list[Residency] = []
    bank_account_for_refund_or_payment: BankAccount | None = None
    prior_year_agi_for_esignature: Decimal | None = None
    related_returns: list[Any] = []

    def person(self, person_id: str) -> Person:
        for person in self.people:
            if person.id == person_id:
                return person
        raise KeyError(f"no household person {person_id!r}")


class Extraction(BaseModel):
    status: str
    values: int
    reason: str | None = None


class Page(BaseModel):
    page: int
    printed_content: str


class Document(BaseModel):
    id: str
    title: str
    document_type: str
    issuer: str | None = None
    belongs_to: str | None = None
    tax_year: int | None = None
    received_at: str | None = None
    uploaded_by: str | None = None
    file_name: str | None = None
    page_count: int
    pages: list[Page] = []
    extraction: Extraction
    marked_corrected: bool | None = None


class Position(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class ExtractedValue(BaseModel):
    id: str
    document_id: str
    page: int
    field: str
    label: str | None = None
    value: Any = None
    value_type: str
    text_as_read: str | None = None
    position: Position | None = None
    confidence: float


class QuestionnaireItem(BaseModel):
    id: str
    question: str
    answer: Any = None
    answered_by: str | None = None
    answered_at: str | None = None


class Message(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sent_at: str
    from_: str = Field(alias="from")
    to: str
    text: str


class CallNote(BaseModel):
    id: str
    date: str
    participants: list[str] = []
    notes: list[str] = []


class Client(BaseModel):
    questionnaire: list[QuestionnaireItem] = []
    messages: list[Message] = []
    call_notes: list[CallNote] = []


class TimelineEvent(BaseModel):
    id: str
    at: str
    event: str
    actor: str | None = None
    detail: str | None = None
    refs: list[str] = []


class Line(BaseModel):
    key: str
    jurisdiction: str
    form: str
    line: str
    label: str
    value: Any
    rule: str
    inputs: list[str] = []
    sources: list[str] = []
    note: str | None = None


class Asset(BaseModel):
    asset_id: str
    description: str | None = None
    activity: str | None = None
    cost: Decimal | None = None
    land_value_not_depreciated: Decimal | None = None
    placed_in_service: str | None = None
    method: str | None = None
    life_years: Decimal | None = None
    federal: dict[str, Any] = {}
    california: dict[str, Any] = {}
    amt: dict[str, Any] | None = None
    disposed: bool | str | None = None
    sources: list[str] = []


class Diagnostic(BaseModel):
    code: str
    severity: str
    message: str
    refs: list[str] = []


class ChangeFromPrevious(BaseModel):
    key: str
    change: str
    old: Any = None
    new: Any = None


class TaxEffectRate(BaseModel):
    federal_per_dollar: Decimal
    california_per_dollar: Decimal


class FederalSummary(BaseModel):
    agi: Decimal | None = None
    taxable_income: Decimal | None = None
    total_tax: Decimal | None = None
    payments: Decimal | None = None
    balance_due: Decimal | None = None
    penalty: Decimal | None = None


class CaliforniaSummary(BaseModel):
    total_agi: Decimal | None = None
    ca_agi: Decimal | None = None
    total_tax: Decimal | None = None
    payments: Decimal | None = None
    balance_due: Decimal | None = None
    penalty: Decimal | None = None


class Summary(BaseModel):
    federal: FederalSummary
    california: CaliforniaSummary


class ReturnVersion(BaseModel):
    version: str
    computed_at: str
    trigger: str | None = None
    documents_used: list[str] = []
    documents_superseded: list[str] = []
    summary: Summary
    tax_effect_rates: dict[str, TaxEffectRate] = {}
    carryovers_out: dict[str, Any] = {}
    assets: list[Asset] = []
    diagnostics: list[Diagnostic] = []
    changes_from_previous: list[ChangeFromPrevious] = []
    lines: list[Line] = []

    _lines_by_key: dict[str, Line] = PrivateAttr(default_factory=dict)
    _assets_by_id: dict[str, Asset] = PrivateAttr(default_factory=dict)
    # Populated lazily by proofline.provenance.tracing, which recurses through
    # every line's sources once per return version rather than once per line
    # traced -- the one-per-object attribute means it lives and dies with
    # this return version, so there's no cross-packet staleness to manage.
    _documents_used_by_any_line_cache: frozenset[str] | None = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        self._lines_by_key = {line.key: line for line in self.lines}
        self._assets_by_id = {asset.asset_id: asset for asset in self.assets}

    def line(self, key: str) -> Line:
        try:
            return self._lines_by_key[key]
        except KeyError:
            raise KeyError(
                f"no line {key!r} in return version {self.version!r}"
            ) from None

    def asset(self, asset_id: str) -> Asset:
        try:
            return self._assets_by_id[asset_id]
        except KeyError:
            raise KeyError(
                f"no asset {asset_id!r} in return version {self.version!r}"
            ) from None

    def get_documents_used_by_any_line_cache(self) -> frozenset[str] | None:
        return self._documents_used_by_any_line_cache

    def set_documents_used_by_any_line_cache(self, value: frozenset[str]) -> None:
        self._documents_used_by_any_line_cache = value


class ChangedLine(BaseModel):
    key: str
    change: str
    old: Any = None
    new: Any = None


class Alternative(BaseModel):
    id: str
    description: str | None = None
    base_version: str
    choices: dict[str, Any] = {}
    federal: dict[str, Any] = {}
    california: dict[str, Any] = {}
    changed_lines: list[ChangedLine] = []


class Extension(BaseModel):
    computed_at: str | None = None
    based_on_version: str | None = None
    federal: dict[str, Any] = {}
    california: dict[str, Any] = {}


class WhatIf(BaseModel):
    alternatives: list[Alternative] = []
    extension: Extension | None = None

    def alternative(self, alternative_id: str) -> Alternative:
        for alt in self.alternatives:
            if alt.id == alternative_id:
                return alt
        raise KeyError(f"no what-if alternative {alternative_id!r}")


class PriorYears(BaseModel):
    model_config = ConfigDict(extra="allow")

    return_2024: dict[str, Any] = {}
    prior_preparer_workpaper: dict[str, Any] = {}
    asset_records: list[dict[str, Any]] = []
    basis_records: dict[str, Any] = {}
    carryovers_into_2025: dict[str, Any] = {}


class TaxAgencyRecords(BaseModel):
    model_config = ConfigDict(extra="allow")

    irs_account_transcript_2025: list[dict[str, Any]] = []
    ftb_account: dict[str, Any] = {}
    notices: list[dict[str, Any]] = []
    efile: list[dict[str, Any]] = []


class EngineReference(BaseModel):
    parameters: dict[str, Any] = {}
    rules: dict[str, Any] = {}


class FxRates(BaseModel):
    model_config = ConfigDict(extra="allow")

    SEK_per_USD: dict[str, Any] = {}


class Packet(BaseModel):
    packet: PacketMeta
    readme: dict[str, Any] = {}
    household: Household
    documents: list[Document]
    extracted_values: list[ExtractedValue]
    client: Client = Client()
    firm: dict[str, Any] = {}
    prior_years: PriorYears = PriorYears()
    tax_agency_records: TaxAgencyRecords = TaxAgencyRecords()
    timeline: list[TimelineEvent] = []
    engine_reference: EngineReference = EngineReference()
    return_versions: list[ReturnVersion]
    what_if: WhatIf = WhatIf()
    planning_reference_2026: dict[str, Any] = {}
    post_filing_rates: dict[str, Any] = {}
    fx_rates: FxRates = FxRates()

    _documents_by_id: dict[str, Document] = PrivateAttr(default_factory=dict)
    _extracted_values_by_id: dict[str, ExtractedValue] = PrivateAttr(
        default_factory=dict
    )

    def model_post_init(self, context: Any, /) -> None:
        self._documents_by_id = {doc.id: doc for doc in self.documents}
        self._extracted_values_by_id = {
            value.id: value for value in self.extracted_values
        }

    def document(self, document_id: str) -> Document:
        try:
            return self._documents_by_id[document_id]
        except KeyError:
            raise KeyError(f"no document {document_id!r}") from None

    def extracted_value(self, extracted_value_id: str) -> ExtractedValue:
        try:
            return self._extracted_values_by_id[extracted_value_id]
        except KeyError:
            raise KeyError(f"no extracted value {extracted_value_id!r}") from None

    def return_version(self, version: str = "v3") -> ReturnVersion:
        for rv in self.return_versions:
            if rv.version == version:
                return rv
        raise KeyError(f"no return version {version!r}")

    def questionnaire_item(self, item_id: str) -> QuestionnaireItem:
        for item in self.client.questionnaire:
            if item.id == item_id:
                return item
        raise KeyError(f"no questionnaire item {item_id!r}")

    def message(self, message_id: str) -> Message:
        for message in self.client.messages:
            if message.id == message_id:
                return message
        raise KeyError(f"no message {message_id!r}")

    def call_note(self, call_note_id: str) -> CallNote:
        for note in self.client.call_notes:
            if note.id == call_note_id:
                return note
        raise KeyError(f"no call note {call_note_id!r}")

    def timeline_event(self, timeline_id: str) -> TimelineEvent:
        for event in self.timeline:
            if event.id == timeline_id:
                return event
        raise KeyError(f"no timeline event {timeline_id!r}")


@lru_cache(maxsize=1)
def load_packet() -> Packet:
    with _PACKET_PATH.open() as f:
        raw = json.load(f)
    return Packet.model_validate(raw)
