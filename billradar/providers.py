"""The models behind BillRadar, one job each: SAM 3.1 finds sheets, Muse Spark reads, Muse Wonder checks.

BILLRADAR_LIVE=1 plus MODEL_API_KEY calls the live API; otherwise the client replays recorded answers and fails
loudly on a request it has no recording for.
"""

from __future__ import annotations

from billradar import sam
from billradar.meta_client import MetaClient


def name() -> str:
    return "meta"


def make_client() -> MetaClient:
    return MetaClient()


def sheet_finder(client):
    return sam.find_sheets


def models(client=None) -> dict[str, str]:
    """Which model did which step, for screens and logs."""
    return {"sheets": "sam-3.1", "read": "muse-spark-1.3", "text": "muse-spark-1.3", "ask": "muse-spark-1.3",
            "check": "muse-wonder-1.0"}


def _short(model_id: str) -> str:
    """muse-spark-1.3 -> Muse Spark; sam-3.1 -> SAM 3.1."""
    named = {"sam-3.1": "SAM 3.1", "muse-spark-1.3": "Muse Spark", "muse-wonder-1.0": "Muse Wonder",
             "muse-voice-transcribe-1.0": "Muse Voice Transcribe", "muse-image-1.0": "Muse Image",
             "meta-models/muse-spark-open-1026": "Muse Spark Open"}
    return named.get(model_id, model_id.split("/")[-1].replace("-", " "))


def labels(client=None) -> dict[str, str]:
    """Screen names of the models for every role."""
    return {"provider": "meta", "platform": "Meta models", "find": "SAM 3.1", "read": "Muse Spark", "ask": "Muse Spark",
            "text": "Muse Spark", "review": "Muse Wonder", "agent": "Muse Spark", "voice": "Muse Voice Transcribe",
            "portal": "Muse Spark"}
