"""Step 10, Part 4: the golden-set run. Everything here is marked `eval`
(excluded from `pytest api -q -m "not eval"`, per CLAUDE.md), and every
test that needs the model skips with an explicit reason when
GROQ_API_KEY isn't set -- never a silent pass, never a hang.

`test_baseline_recall_on_golden_set` is the one exception that doesn't
need the key at all (it's the deterministic checks' own recall, with no
model involved) -- it's still marked `eval` so it stays grouped with the
rest of this file, but it can be run and trusted today, with no key.

See docs/DECISIONS.md for why the model-dependent tests below could not
actually be executed in this session (no GROQ_API_KEY was available), and
what that does and doesn't mean for the ship decision.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from proofline.ai.investigator import investigate_case
from proofline.ai.schema import InvestigatorSuggestion
from proofline.ai.validator import validate_suggestion
from proofline.checks.baseline import build_report
from proofline.db.models import Base, Case
from proofline.db.repository import insert_case
from proofline.packet import load_packet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from eval.golden_cases import GOLDEN_CASES, GoldenCase

pytestmark = pytest.mark.eval

_NO_GROQ_KEY = not os.environ.get("GROQ_API_KEY")
_SKIP_REASON = "GROQ_API_KEY not set"


def test_baseline_recall_on_golden_set() -> None:
    """The bar the investigator has to beat: the existing checks already
    catch every confirmed error (E1-E4) but neither of the two chosen
    "possible" leads (E5, E9) -- nobody has written a check for those
    yet, which is exactly why they're useful golden cases for the AI."""
    report = build_report()
    confirmed_ids = {g.error_id for g in GOLDEN_CASES if g.check_id is not None}
    possible_ids = {g.error_id for g in GOLDEN_CASES if g.check_id is None}

    assert confirmed_ids <= set(report.confirmed_found), (
        report.confirmed_found,
        report.confirmed_missing,
    )
    matched_possible_ids = {error_id for _, error_id in report.possible_matches}
    assert possible_ids.isdisjoint(matched_possible_ids), (
        "a check now covers one of the golden set's 'possible' leads -- "
        "update golden_cases.py's check_id for it"
    )


@pytest.fixture
def _session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_case(session: Session, golden: GoldenCase) -> Case:
    case = Case(
        case_id=f"case-golden-{golden.error_id}",
        root_cause_key=f"golden:{golden.error_id}",
        origin=golden.origin,
        scope=golden.scope,
        claims=list(golden.claims),
        severity=golden.severity,
        finding_type=golden.finding_type,
        status="investigating",
        revision=1,
        evidence_refs=list(golden.case_evidence_refs),
        tax_effect_federal=golden.tax_effect_federal,
        tax_effect_california=golden.tax_effect_california,
        impact_unknown=golden.impact_unknown,
        observed=golden.observed,
        expected=golden.expected,
    )
    insert_case(session, case)
    session.commit()
    return case


def _retrieval_recall(golden: GoldenCase, suggestion: InvestigatorSuggestion) -> float:
    required = {*golden.required_claim_citations, *golden.required_document_citations}
    if not required:
        return 1.0
    cited = {*suggestion.cited_claim_ids, *suggestion.cited_document_ids}
    return len(required & cited) / len(required)


def _retrieval_precision(
    golden: GoldenCase, suggestion: InvestigatorSuggestion
) -> float:
    cited = {*suggestion.cited_claim_ids, *suggestion.cited_document_ids}
    if not cited:
        return 0.0
    distractors = set(golden.distractor_documents)
    bad = cited & distractors
    return 1.0 - (len(bad) / len(cited))


@pytest.mark.skipif(_NO_GROQ_KEY, reason=_SKIP_REASON)
@pytest.mark.parametrize("golden", GOLDEN_CASES, ids=lambda g: g.error_id)
def test_hard_gates_on_golden_set(golden: GoldenCase, _session: Session) -> None:
    """Deterministic, no exceptions: every golden case's real
    investigation must resolve every citation, invent no number, and
    propose a transition the case's state could actually accept. This is
    the one gate that must be 100% -- a single miss here means the
    feature does not ship, full stop."""
    case = _seed_case(_session, golden)
    run = investigate_case(_session, case.case_id)
    result = validate_suggestion(load_packet(), case, run.suggestion)
    assert result.ok, (golden.error_id, result.reasons)


@pytest.mark.skipif(_NO_GROQ_KEY, reason=_SKIP_REASON)
def test_investigator_beats_baseline_on_the_two_possible_leads(
    _session: Session,
) -> None:
    """The real comparison for E5/E9: the baseline's recall on these two
    is 0 (no check exists). The investigator ships only if it does
    meaningfully better -- citing the right evidence, not just anything."""
    possible_cases = [g for g in GOLDEN_CASES if g.check_id is None]
    recalls = []
    for golden in possible_cases:
        case = _seed_case(_session, golden)
        run = investigate_case(_session, case.case_id)
        recalls.append(_retrieval_recall(golden, run.suggestion))
    baseline_recall = 0.0
    investigator_recall = sum(recalls) / len(recalls)
    assert investigator_recall > baseline_recall, (
        f"investigator recall {investigator_recall} did not beat the baseline's "
        f"{baseline_recall} on the possible leads with no existing check"
    )


@pytest.mark.skipif(_NO_GROQ_KEY, reason=_SKIP_REASON)
def test_judge_calibration_before_trusting_it() -> None:
    """Part 4 point 5: don't trust the judge for anything until it agrees
    with ten hand labels. Faithfulness here is used as "contains no claim
    the evidence doesn't support" -- the judge's `success` should match
    the hand label on at least 8 of 10 (CLAUDE.md "say so" if it
    doesn't -- see docs/DECISIONS.md for what this session found, if it
    ran this)."""
    from deepeval.metrics import FaithfulnessMetric
    from deepeval.test_case import LLMTestCase

    from eval.groq_judge import GroqJudgeModel
    from eval.judge_calibration import CALIBRATION_CASES

    judge = GroqJudgeModel()
    metric = FaithfulnessMetric(model=judge, threshold=0.5, include_reason=False)

    agreements = 0
    for case in CALIBRATION_CASES:
        test_case = LLMTestCase(
            input="Summarize what the evidence shows.",
            actual_output=case.summary,
            retrieval_context=list(case.retrieval_context),
        )
        metric.measure(test_case)
        judge_says_unsupported = not metric.success
        if judge_says_unsupported == case.has_unsupported_claim:
            agreements += 1

    agreement_rate = agreements / len(CALIBRATION_CASES)
    assert agreement_rate >= 0.8, (
        f"the faithfulness judge only agreed with hand labels on "
        f"{agreements}/{len(CALIBRATION_CASES)} calibration cases -- "
        "do not trust it for the golden-set run until this is fixed "
        "(pick a different judge model/prompt; see docs/DECISIONS.md)"
    )


@pytest.mark.skipif(_NO_GROQ_KEY, reason=_SKIP_REASON)
@pytest.mark.parametrize("golden", GOLDEN_CASES, ids=lambda g: g.error_id)
def test_judge_metrics_on_golden_set(golden: GoldenCase, _session: Session) -> None:
    """Faithfulness and a "new-hire usefulness" rubric on the real
    investigation output -- supplementary color for the ship decision,
    not itself a hard gate (only the deterministic gates above and the
    baseline comparison are)."""
    from deepeval.metrics import FaithfulnessMetric, GEval
    from deepeval.test_case import LLMTestCase, SingleTurnParams

    from eval.groq_judge import GroqJudgeModel

    case = _seed_case(_session, golden)
    run = investigate_case(_session, case.case_id)
    judge = GroqJudgeModel()

    test_case = LLMTestCase(
        input=f"Investigate case {case.case_id}: {golden.observed}",
        actual_output=run.suggestion.summary,
        retrieval_context=[golden.observed, golden.expected],
    )

    faithfulness = FaithfulnessMetric(model=judge, threshold=0.5)
    faithfulness.measure(test_case)

    usefulness = GEval(
        name="New-hire usefulness",
        criteria=(
            "Would this summary actually help a new hire who has never seen this "
            "case understand what's wrong and what evidence supports it, without "
            "overstating anything?"
        ),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.RETRIEVAL_CONTEXT,
        ],
        model=judge,
        threshold=0.5,
    )
    usefulness.measure(test_case)

    assert faithfulness.score is not None
    assert usefulness.score is not None
