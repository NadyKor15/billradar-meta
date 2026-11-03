"""The case receipt: which model did each step, how long it took, what it cost, and what the same tokens would have
cost on one model for everything.

Built only from the client's own call log (MetaClient.calls), never from estimates of steps that did not run.
Costs use the published per-model prices (meta_client.PRICES). Replayed calls cost nothing now, so the receipt says
what the recorded run cost when it was live.
"""

from __future__ import annotations

from billradar import meta_client as mc

STEP = {"sam:sheet of paper": "Find sheets", "sam:video:sheet of paper": "Follow sheets through the video", "spark:read": "Read every sheet", "spark:read-2": "Read every sheet again", "open:read-2": "Read every sheet again", "spark:read-3": "Read a sheet a third time",
        "wonder:review": "Second read of the case"}
SPARK, WONDER = "muse-spark-1.3", "muse-wonder-1.0"


def _priced_as(model: str, call: dict) -> float:
    """The call at another model's token price; a call with no tokens (sheets, speech) stays what it cost."""
    return mc.cost_of(model, call["usage"]) if call["model"] in mc.PRICES else call.get("usd", 0.0)


def _row(call: dict) -> dict:
    u = call.get("usage") or {}
    return {
        "step": STEP.get(call.get("label", ""), call.get("label", "")),
        "model": call["model"],
        "seconds": call.get("seconds", 0.0),
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "reasoning_tokens": (u.get("output_tokens_details") or {}).get("reasoning_tokens", 0),
        "usd": call.get("usd", 0.0),
        "live": bool(call.get("live")),
        "request_id": call.get("response_id", ""),
    }


def once(calls: list[dict]) -> list[dict]:
    """A recorded answer can serve two identical requests in a replay; it was paid for once, so it is counted once."""
    seen: set[str] = set()
    out = []
    for c in calls:
        rid = c.get("response_id", "")
        if not rid or rid not in seen:
            seen.add(rid)
            out.append(c)
    return out


def build(calls: list[dict]) -> dict | None:
    """calls: the client's call log for one case, in order. None when there were no calls."""
    if not calls:
        return None
    calls = once(calls)
    rows = [_row(c) for c in calls]
    total = sum(r["usd"] for r in rows)
    return {
        "rows": rows,
        "total_usd": round(total, 6),
        "total_seconds": round(sum(r["seconds"] for r in rows), 2),
        "prices": {"ours": round(total, 6),
                   "all_spark": round(sum(_priced_as(SPARK, c) for c in calls), 6),
                   "all_wonder": round(sum(_priced_as(WONDER, c) for c in calls), 6),
                   "note": "Same tokens, other price: every text step at Muse Spark's or Muse Wonder's published price. "
                           "SAM 3.1 and speech have no token price, so they stay what they cost."},
        "replayed": not any(r["live"] for r in rows),
    }
