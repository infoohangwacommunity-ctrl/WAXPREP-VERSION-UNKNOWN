"""Policy tests for Stage 09."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from waxprep.supplychain.policy import (
    DependencyPolicy,
    LicenseDecision,
    LicensePolicy,
    PolicyError,
    SourcePolicy,
    VulnerabilityException,
    dependency_review_licenses,
    load_policy,
)

EXCEPTION = (
    "[[exceptions]]\n"
    'advisory = "GHSA-53pm-wgxf-c6qf"\n'
    'package = "wcmatch"\n'
    'versions = ["8.5.2"]\n'
    'reason = "pinned by semgrep"\n'
    'risk = "development only"\n'
    'owner = "WaxPrep Engineering Team"\n'
    "introduced = 2026-07-22\n"
    "review_by = 2026-12-22\n"
    'remediation_evidence = "rechecked 2026-11-25"\n'
)


def write_policies(
    root: Path,
    *,
    exceptions: str = EXCEPTION,
    licenses: str | None = None,
    sources: str | None = None,
    inventory: str | None = None,
) -> Path:
    base = root / "security" / "dependency-policy"
    base.mkdir(parents=True)
    (base / "vulnerability-exceptions.toml").write_text(exceptions, encoding="utf-8")
    (base / "license-policy.toml").write_text(
        licenses
        if licenses is not None
        else 'approved = ["MIT"]\nreview = ["MPL-2.0"]\nprohibited = ["GPL-3.0-only"]\n',
        encoding="utf-8",
    )
    (base / "source-policy.toml").write_text(
        sources
        if sources is not None
        else 'allowed_registries = ["https://pypi.org/simple"]\n'
        "allow_vcs = false\n"
        "allow_url = false\n"
        "[reviewed_majors]\nalpha = [1]\n",
        encoding="utf-8",
    )
    (base / "dependency-inventory.toml").write_text(
        inventory
        if inventory is not None
        else '[purpose]\nalpha = "test dependency"\n[owner]\nalpha = "team"\n',
        encoding="utf-8",
    )
    return root


def test_loads_repository_policy() -> None:
    policy = load_policy(Path("."))
    assert isinstance(policy, DependencyPolicy)
    assert len(policy.exceptions) == 1
    assert policy.inventory.purpose_for("fastapi")
    assert policy.sources.major_reviewed("fastapi", "0.162.2")


def test_missing_policy_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="missing file"):
        load_policy(tmp_path)


def test_invalid_toml_is_an_error(tmp_path: Path) -> None:
    write_policies(tmp_path, exceptions="exceptions = [")
    with pytest.raises(PolicyError, match="invalid TOML"):
        load_policy(tmp_path)


def test_exceptions_must_be_an_array(tmp_path: Path) -> None:
    write_policies(tmp_path, exceptions="exceptions = 1\n")
    with pytest.raises(PolicyError, match="array of tables"):
        load_policy(tmp_path)


def test_exception_entries_must_be_tables(tmp_path: Path) -> None:
    write_policies(tmp_path, exceptions='exceptions = ["nope"]\n')
    with pytest.raises(PolicyError, match="expected a table"):
        load_policy(tmp_path)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('versions = ["8.5.2"]\n', "versions = []\n", "at least one version"),
        ('reason = "pinned by semgrep"\n', "", "reason"),
        ("introduced = 2026-07-22\n", 'introduced = "yesterday"\n', "ISO date"),
        ("review_by = 2026-12-22\n", "review_by = 2026-01-01\n", "must not precede"),
    ],
)
def test_exception_validation(tmp_path: Path, old: str, new: str, message: str) -> None:
    write_policies(tmp_path, exceptions=EXCEPTION.replace(old, new))
    with pytest.raises(PolicyError, match=message):
        load_policy(tmp_path)


def test_exception_date_must_be_a_date(tmp_path: Path) -> None:
    write_policies(
        tmp_path,
        exceptions=EXCEPTION.replace("introduced = 2026-07-22", "introduced = 2026"),
    )
    with pytest.raises(PolicyError, match="ISO date"):
        load_policy(tmp_path)


def test_policy_entries_must_be_non_empty(tmp_path: Path) -> None:
    write_policies(tmp_path, licenses='approved = [""]\nreview = []\nprohibited = []\n')
    with pytest.raises(PolicyError, match="non-empty"):
        load_policy(tmp_path)


def test_unreadable_policy_path_is_an_error(tmp_path: Path) -> None:
    from waxprep.supplychain.tomlio import TomlError, load_table

    with pytest.raises(TomlError, match="cannot read"):
        load_table(tmp_path)


def test_license_policy_requires_approved(tmp_path: Path) -> None:
    write_policies(tmp_path, licenses="approved = []\nreview = []\nprohibited = []\n")
    with pytest.raises(PolicyError, match="at least one SPDX identifier"):
        load_policy(tmp_path)


def test_license_lists_must_be_disjoint(tmp_path: Path) -> None:
    write_policies(
        tmp_path,
        licenses='approved = ["MIT"]\nreview = ["MIT"]\nprohibited = []\n',
    )
    with pytest.raises(PolicyError, match="not disjoint"):
        load_policy(tmp_path)


def test_license_entries_must_be_strings(tmp_path: Path) -> None:
    write_policies(tmp_path, licenses="approved = [1]\nreview = []\nprohibited = []\n")
    with pytest.raises(PolicyError, match="array of strings"):
        load_policy(tmp_path)


def test_source_policy_requires_a_registry(tmp_path: Path) -> None:
    write_policies(
        tmp_path,
        sources="allowed_registries = []\nallow_vcs = false\nallow_url = false\n",
    )
    with pytest.raises(PolicyError, match="allowed registry"):
        load_policy(tmp_path)


def test_source_policy_requires_booleans(tmp_path: Path) -> None:
    write_policies(
        tmp_path,
        sources='allowed_registries = ["https://pypi.org/simple"]\nallow_vcs = "no"\nallow_url = false\n',
    )
    with pytest.raises(PolicyError, match="allow_vcs"):
        load_policy(tmp_path)


def test_reviewed_majors_must_be_integers(tmp_path: Path) -> None:
    write_policies(
        tmp_path,
        sources='allowed_registries = ["https://pypi.org/simple"]\n'
        "allow_vcs = false\nallow_url = false\n"
        '[reviewed_majors]\nalpha = ["one"]\n',
    )
    with pytest.raises(PolicyError, match="integer major versions"):
        load_policy(tmp_path)


def test_inventory_requires_purpose(tmp_path: Path) -> None:
    write_policies(tmp_path, inventory="[purpose]\n[owner]\n")
    with pytest.raises(PolicyError, match="document at least one dependency"):
        load_policy(tmp_path)


def test_inventory_requires_owner(tmp_path: Path) -> None:
    write_policies(tmp_path, inventory='[purpose]\nalpha = "x"\n[owner]\n')
    with pytest.raises(PolicyError, match="no owner recorded"):
        load_policy(tmp_path)


def test_inventory_values_must_be_strings(tmp_path: Path) -> None:
    write_policies(tmp_path, inventory='[purpose]\nalpha = 1\n[owner]\nalpha = "team"\n')
    with pytest.raises(PolicyError, match="expected a non-empty string"):
        load_policy(tmp_path)


def make_exception(**overrides: object) -> VulnerabilityException:
    values: dict[str, object] = {
        "advisory": "GHSA-1",
        "package": "wcmatch",
        "versions": ("8.5.2",),
        "reason": "r",
        "risk": "r",
        "owner": "o",
        "introduced": date(2026, 1, 1),
        "review_by": date(2026, 12, 22),
        "remediation_evidence": "e",
    }
    values.update(overrides)
    return VulnerabilityException(**values)  # type: ignore[arg-type]


def test_exception_is_scoped_to_advisory_package_and_version() -> None:
    exception = make_exception()
    assert exception.covers("GHSA-1", "WCMatch", "8.5.2")
    assert not exception.covers("GHSA-2", "wcmatch", "8.5.2")
    assert not exception.covers("GHSA-1", "other", "8.5.2")
    assert not exception.covers("GHSA-1", "wcmatch", "8.5.3")
    assert exception.matches_any(("GHSA-1", "CVE-1"), "wcmatch", "8.5.2")


def test_exception_expires_after_review_date() -> None:
    exception = make_exception()
    assert not exception.is_expired(date(2026, 12, 22))
    assert exception.is_expired(date(2026, 12, 23))


def test_license_classification() -> None:
    policy = LicensePolicy(
        approved=frozenset({"MIT", "Apache-2.0"}),
        review=frozenset({"MPL-2.0"}),
        prohibited=frozenset({"GPL-3.0-only"}),
    )
    assert policy.classify(None) is LicenseDecision.UNKNOWN
    assert policy.classify("MIT") is LicenseDecision.APPROVED
    assert policy.classify("MIT OR Apache-2.0") is LicenseDecision.APPROVED
    assert policy.classify("MIT AND GPL-3.0-only") is LicenseDecision.PROHIBITED
    assert policy.classify("MPL-2.0") is LicenseDecision.REVIEW
    assert policy.classify("MIT OR MPL-2.0") is LicenseDecision.REVIEW
    assert policy.classify("WTFPL") is LicenseDecision.UNKNOWN


def test_reviewed_licenses_require_explicit_acceptance() -> None:
    policy = LicensePolicy(
        approved=frozenset({"MIT"}),
        review=frozenset({"MPL-2.0"}),
        prohibited=frozenset({"GPL-3.0-only"}),
        reviewed={"MPL-2.0": "accepted for certifi"},
    )
    assert policy.classify("MPL-2.0") is LicenseDecision.REVIEW
    assert policy.accepted("MPL-2.0")
    assert policy.accepted("MIT OR MPL-2.0")
    assert policy.accepted("MIT")
    assert not policy.accepted(None)
    assert not policy.accepted("")
    assert not policy.accepted("WTFPL")


def test_reviewed_license_table_is_loaded(tmp_path: Path) -> None:
    write_policies(
        tmp_path,
        licenses=(
            'approved = ["MIT"]\nreview = ["MPL-2.0"]\nprohibited = []\n'
            '[reviewed]\n"MPL-2.0" = "accepted for certifi"\n'
        ),
    )
    policy = load_policy(tmp_path)
    assert policy.licenses.reviewed == {"MPL-2.0": "accepted for certifi"}
    assert policy.licenses.accepted("MPL-2.0")


@pytest.mark.parametrize(
    ("licenses", "message"),
    [
        (
            'approved = ["MIT"]\nreview = ["MPL-2.0"]\nprohibited = []\n'
            '[reviewed]\n"MPL-2.0" = 1\n',
            "non-empty string",
        ),
        (
            'approved = ["MIT"]\nreview = ["MPL-2.0"]\nprohibited = []\n'
            '[reviewed]\nMIT = "already approved"\n',
            "approved or prohibited",
        ),
        (
            'approved = ["MIT"]\nreview = ["MPL-2.0"]\nprohibited = ["GPL-3.0-only"]\n'
            '[reviewed]\n"GPL-3.0-only" = "prohibited"\n',
            "approved or prohibited",
        ),
    ],
)
def test_reviewed_license_validation(tmp_path: Path, licenses: str, message: str) -> None:
    write_policies(tmp_path, licenses=licenses)
    with pytest.raises(PolicyError, match=message):
        load_policy(tmp_path)


def test_dependency_review_allow_list_matches_repository_policy() -> None:
    allowed = dependency_review_licenses(Path(".github/dependency-review-config.yml"))
    policy = load_policy(Path("."))
    assert set(allowed) == set(policy.licenses.approved)
    assert "MPL-2.0" not in allowed
    assert policy.licenses.accepted("MPL-2.0")


def test_dependency_review_config_must_be_readable(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="cannot read"):
        dependency_review_licenses(tmp_path / "missing.yml")


def test_source_policy_checks() -> None:
    policy = SourcePolicy(
        allowed_registries=("https://pypi.org/simple",),
        allow_vcs=False,
        allow_url=False,
        reviewed_majors={"alpha": frozenset({1})},
    )
    assert policy.registry_allowed("https://pypi.org/simple/")
    assert not policy.registry_allowed("https://example.invalid/simple")
    assert policy.major_reviewed("Alpha", "1.9.0")
    assert not policy.major_reviewed("alpha", "2.0.0")
    assert not policy.major_reviewed("alpha", "dev")
