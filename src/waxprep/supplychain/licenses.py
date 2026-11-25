"""License resolution for Stage 09.

License metadata is read from the installed distribution for the exact
lockfile version. That is the only offline source available to the gate, and it
is sufficient to classify declared licenses; it is not legal advice.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from importlib.metadata import PackageNotFoundError, metadata

MetadataReader = Callable[[str], Mapping[str, str] | None]

_ALIASES: dict[str, str] = {
    "mit": "MIT",
    "mit license": "MIT",
    "bsd license": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "apache software license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "isc": "ISC",
    "isc license": "ISC",
    "isc license (iscl)": "ISC",
    "python software foundation license": "PSF-2.0",
    "psf-2.0": "PSF-2.0",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "mpl-2.0": "MPL-2.0",
    "gnu general public license v3 (gplv3)": "GPL-3.0-only",
    "gpl-3.0-only": "GPL-3.0-only",
    "gnu affero general public license v3": "AGPL-3.0-only",
    "agpl-3.0-only": "AGPL-3.0-only",
}

_CLASSIFIER_ALIASES: tuple[tuple[str, str], ...] = (
    ("mit license", "MIT"),
    ("bsd license", "BSD-3-Clause"),
    ("apache software license", "Apache-2.0"),
    ("isc license", "ISC"),
    ("mozilla public license 2.0", "MPL-2.0"),
    ("gnu general public license v3", "GPL-3.0-only"),
    ("gnu affero general public license v3", "AGPL-3.0-only"),
)

_EXPRESSION_OPERATOR = re.compile(r"\s+(?:OR|AND)\s+")


def normalize_license(value: str | None) -> str | None:
    """Normalize one license value to SPDX identifiers, or ``None``."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.upper() == "UNKNOWN":
        return None
    atoms = [atom.strip() for atom in _EXPRESSION_OPERATOR.split(cleaned) if atom.strip()]
    normalized = tuple(_ALIASES.get(atom.lower(), atom) for atom in atoms)
    return " OR ".join(normalized)


def read_distribution_metadata(name: str) -> Mapping[str, str] | None:
    """Read license-relevant metadata for an installed distribution."""
    try:
        distribution = metadata(name)
    except PackageNotFoundError:
        return None
    classifiers = distribution.get_all("Classifier") or []
    return {
        "License-Expression": distribution.get("License-Expression") or "",
        "License": distribution.get("License") or "",
        "Classifiers": "; ".join(classifiers),
    }


def license_from_metadata(name: str, reader: MetadataReader | None = None) -> str | None:
    """Resolve a package license from installed metadata.

    ``License-Expression`` wins; the legacy ``License`` field and trove
    classifiers are fallbacks. Missing metadata is unknown, never approved.
    """
    data = (reader or read_distribution_metadata)(name)
    if not data:
        return None

    for key in ("License-Expression", "License"):
        resolved = normalize_license(data.get(key))
        if resolved is not None:
            return resolved

    for classifier in data.get("Classifiers", "").split(";"):
        lowered = classifier.strip().lower()
        for fragment, license_id in _CLASSIFIER_ALIASES:
            if fragment in lowered:
                return license_id
    return None
