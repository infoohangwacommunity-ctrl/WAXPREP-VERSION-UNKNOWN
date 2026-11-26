"""Human- and machine-readable rendering of an acceptance decision."""

from __future__ import annotations

from typing import Any

from waxprep.ci.acceptance import AcceptanceDecision


def decision_to_dict(decision: AcceptanceDecision) -> dict[str, Any]:
    """Serialise a decision for machine consumption."""
    return {
        "accepted": decision.accepted,
        "commit": decision.commit,
        "failures": list(decision.failures),
        "warnings": list(decision.warnings),
        "observed": [{"job": job, "status": status} for job, status in decision.observed],
        "advisory": [{"job": job, "state": state} for job, state in decision.advisory],
    }


def render_markdown(decision: AcceptanceDecision) -> str:
    """Render a decision as a Markdown report for the job summary."""
    verdict = "ACCEPTED" if decision.accepted else "REJECTED"
    # Report boilerplate, not a vocabulary used to classify student messages.
    lines = [  # nosemgrep: semgrep.whd-008-vocabulary-assignment
        "## CI Acceptance Report",
        "",
        f"- **Commit:** `{decision.commit}`",
        f"- **Decision:** {verdict}",
        "",
        "| Job | Recorded status |",
        "| --- | --- |",
    ]
    if decision.observed:
        lines.extend(f"| {job} | {status} |" for job, status in decision.observed)
    else:
        lines.append("| (no evidence recorded) | - |")

    lines.extend([
        "",
        "### Advisory checks (non-blocking)",
        "",
        "| Job | Execution |",
        "| --- | --- |",
    ])
    if decision.advisory:
        lines.extend(f"| {job} | {state} |" for job, state in decision.advisory)
    else:
        lines.append("| (none recorded) | - |")

    lines.extend(["", "### Failures (blocking)", ""])
    for failure in decision.failures or ("None",):
        lines.append(f"- {failure}")

    lines.extend(["\n### Warnings (advisory, non-blocking)", ""])
    for warning in decision.warnings or ("None",):
        lines.append(f"- {warning}")

    lines.extend([
        "",
        "Acceptance is based only on recorded execution evidence for this commit.",
        "It is not a statement that an agent claimed the work was complete.",
        "",
    ])
    return "\n".join(lines)
