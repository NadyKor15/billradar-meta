"""The second read on Muse Spark Open: Meta's open weights, served by Baseten through its OpenAI-style API.

A different model from the first read makes the two reads independent. It speaks through the same MetaClient as every
other call, so the journal, the recordings and the receipt work as they do for Spark; only the wire differs. It takes
covered images and text, never a PDF: files go to it as covered page images in private mode, the only mode it runs in.
Spending comes from Baseten's hackathon credits, under its own cap.
"""

from __future__ import annotations

import os
import time

import requests

from billradar.meta_client import ROOT, MetaAPIError, MetaClient, ReplayTransport, SpendLedger, call_cost

MODEL = "meta-models/muse-spark-open-1026"
URL = "https://inference.baseten.co/v1/chat/completions"
SPEND = ROOT / "runs" / "baseten-spend.jsonl"
RETRY_STATUS = {429, 500, 503}
MAX_IMAGES = 8  # "Too many images: 14 (max 8)", HTTP 400
IMAGE_TOKENS_GUESS = 3000  # per image, for the reservation only


def to_chat(body: dict, schema: bool = True) -> dict:
    messages, images = [], 0
    for message in body["input"]:
        role = "system" if message["role"] == "developer" else message["role"]
        parts = []
        for part in message["content"]:
            if part["type"] == "input_text":
                parts.append({"type": "text", "text": part["text"]})
            elif part["type"] == "input_image":
                parts.append({"type": "image_url", "image_url": {"url": part["image_url"]}})
                images += 1
            else:
                raise MetaAPIError(f"the open model takes text and images here, not {part['type']}")
        messages.append({"role": role, "content": " ".join(p["text"] for p in parts) if role == "system" else parts})
    chat = {"model": MODEL, "messages": messages, "max_tokens": body.get("max_output_tokens", 4000), "stream": False}
    form = (body.get("text") or {}).get("format")
    if form:
        chat["response_format"] = ({"type": "json_schema", "json_schema": {"name": form["name"], "schema": form["schema"],
                                                                           "strict": True}}
                                   if schema else {"type": "json_object"})
    return chat


class BasetenTransport:
    """One blocking request, returned as the events MetaClient reads."""

    live = True

    def __init__(self, api_key: str, post=requests.post, ledger: SpendLedger | None = None, attempts: int = 4,
                 timeout: float = 300.0):
        self.api_key, self.post, self.attempts, self.timeout = api_key, post, attempts, timeout
        self.ledger = ledger or SpendLedger(SPEND, cap=float(os.environ.get("BASETEN_SPEND_CAP_USD", "20")))

    def _send(self, chat: dict):
        return self.post(URL, json=chat, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=self.timeout)

    def events(self, body: dict) -> list[dict]:
        chat = to_chat(body)
        images = sum(p["type"] == "image_url" for m in chat["messages"] if isinstance(m["content"], list) for p in m["content"])
        reserve = call_cost(MODEL, {"input_tokens": 5000 + images * IMAGE_TOKENS_GUESS, "output_tokens": chat["max_tokens"]})
        self.ledger.reserve(reserve, f"reserve {MODEL}")
        r = None
        try:
            for attempt in range(self.attempts):
                r = self._send(chat)
                if r.status_code == 400 and chat.get("response_format", {}).get("type") == "json_schema":
                    chat = to_chat(body, schema=False)  # the page does not say it takes a schema: ask for JSON and let code check it
                    continue
                if r.status_code == 200:
                    break
                if r.status_code not in RETRY_STATUS:
                    break
                time.sleep(0 if attempt == 0 else 1.5 * attempt)
            if r is None or r.status_code != 200:
                raise MetaAPIError(f"Baseten answered HTTP {getattr(r, 'status_code', '-')}: {getattr(r, 'text', '')[:300]}")
            raw = r.json()
        except (MetaAPIError, requests.RequestException, ValueError) as exc:
            self.ledger.settle(-reserve, f"release {MODEL}: {type(exc).__name__}")
            raise MetaAPIError(f"the open model did not answer: {exc}") from exc
        got = raw.get("usage") or {}
        usage = {"input_tokens": got.get("prompt_tokens", 0), "output_tokens": got.get("completion_tokens", 0)}
        self.ledger.settle(call_cost(MODEL, usage) - reserve, f"settle {MODEL}")
        choice = (raw.get("choices") or [{}])[0]
        if choice.get("finish_reason") not in ("stop", None):
            raise MetaAPIError(f"the open model stopped early: {choice.get('finish_reason')}")
        text = (choice.get("message") or {}).get("content") or ""
        return [{"type": "response.output_text.delta", "delta": text},
                {"type": "response.completed", "response": {"id": raw.get("id", ""), "usage": usage}}]


def second_reader() -> MetaClient | None:
    """The client for the second read on the open model: BILLRADAR_SECOND_READER=open switches it on, and a run recorded
    that way replays without the key."""
    if os.environ.get("BILLRADAR_SECOND_READER") != "open":
        return None
    key = os.environ.get("BASETEN_API_KEY", "")
    live = key and os.environ.get("BILLRADAR_LIVE") == "1"
    reader_client = MetaClient(transport=BasetenTransport(key) if live else ReplayTransport())
    reader_client.read_model = MODEL
    reader_client.max_images = MAX_IMAGES
    return reader_client


__all__ = ["MODEL", "BasetenTransport", "ReplayTransport", "second_reader", "to_chat"]
