"""Model registry for SupportDesk.

Reads models.yaml (or the file pointed to by SUPPORTDESK_MODELS_FILE) and
exposes model_for(feature) so every call site can resolve its model at call
time rather than at import time.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml

# Default location: models.yaml sits one level above the package directory
# (i.e. examples/supportdesk/models.yaml when the package is
# examples/supportdesk/supportdesk/).
_DEFAULT_MODELS_FILE = Path(__file__).resolve().parent.parent / "models.yaml"


@functools.cache
def _load() -> tuple[dict[str, str], str]:
    """Load the feature→model mapping. Returns (mapping, resolved_path_str)."""
    path = Path(os.environ.get("SUPPORTDESK_MODELS_FILE", str(_DEFAULT_MODELS_FILE)))
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["features"], str(path)


def model_for(feature: str) -> str:
    """Return the model name configured for *feature*.

    Raises KeyError if *feature* is not present in the config file.
    """
    mapping, path = _load()
    if feature not in mapping:
        raise KeyError(f"Unknown feature {feature!r} in {path}")
    return mapping[feature]
