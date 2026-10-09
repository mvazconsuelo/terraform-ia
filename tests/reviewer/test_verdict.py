"""The verdict: PASS or REQUEST_CHANGES, decided by code from the findings and the checks. The AI never takes part."""
from __future__ import annotations

from tools.review.finding import Finding
from tools.review.run_review import decide, max_severity


def _finding(severity: str, kind: str = "CONFIRMED", rule_id: str = "ROOT-004") -> Finding:
    return Finding(severity=severity, category="GOVERNANCE", title="t", evidence="e", explanation="x", recommendation="r", type=kind, rule_id=rule_id)


def test_verdict_passes_with_no_findings() -> None:
    assert decide([], {"terraform fmt": "success"})["decision"] == "PASS"


def test_verdict_requests_changes_for_a_confirmed_high_finding() -> None:
    # given: a confirmed HIGH finding
    verdict = decide([_finding("HIGH")], {})

    # then: it blocks, and the reason names the rule
    assert verdict["decision"] == "REQUEST_CHANGES" and "ROOT-004" in verdict["reasons"][0]


def test_verdict_requests_changes_for_a_critical_finding() -> None:
    assert decide([_finding("CRITICAL")], {})["decision"] == "REQUEST_CHANGES"


def test_verdict_passes_with_only_medium_and_lower_findings() -> None:
    assert decide([_finding("MEDIUM"), _finding("LOW"), _finding("INFO")], {})["decision"] == "PASS"


def test_verdict_does_not_block_on_an_inferred_finding() -> None:
    # given: a HIGH finding that the reviewer only infers
    assert decide([_finding("HIGH", kind="INFERRED")], {})["decision"] == "PASS"


def test_verdict_requests_changes_when_a_check_failed() -> None:
    # given: all findings clean, but the tests job failed
    verdict = decide([], {"terraform fmt": "success", "tests": "failure"})

    # then: the failed check blocks, and it is named
    assert verdict["decision"] == "REQUEST_CHANGES" and "tests" in verdict["reasons"][0]


def test_verdict_does_not_block_on_a_warning() -> None:
    # given: Checkov reports problems but runs without blocking
    assert decide([], {"Checkov (3 findings)": "warning"})["decision"] == "PASS"


def test_verdict_does_not_block_on_a_skipped_check() -> None:
    assert decide([], {"terraform validate": "skipped"})["decision"] == "PASS"


def test_risk_is_the_highest_severity_found() -> None:
    assert max_severity([_finding("LOW"), _finding("HIGH"), _finding("MEDIUM")]) == "HIGH"
    assert max_severity([]) == "INFO"
