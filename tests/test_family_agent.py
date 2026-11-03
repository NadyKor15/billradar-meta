"""Muse Spark acting for a family uses BillRadar's MCP tools (Я23). The model's turns are SYNTHETIC:
`function_call` items in the shape documented at dev.meta.ai/docs/tool-calling.md."""

import asyncio
import json

import pytest

from billradar import agent_api, family_agent
from billradar.mcp_server import build_server
from billradar.meta_client import MetaClient


@pytest.fixture(autouse=True)
def runs(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_api, "RUNS", tmp_path / "agents")


class ScriptedSpark:
    """Turn 1 analyzes the pack, turn 2 reads the findings of the case it got back, turn 3 answers."""

    def __init__(self, extra_call=None):
        self.bodies, self.extra_call = [], extra_call

    def events(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        n = len(self.bodies)
        if n == 1:
            calls = [("analyze_case", {"sample_pack": "brs1-birth-all-errors", "fictional": True})]
            if self.extra_call:
                calls.append(self.extra_call)
        elif n == 2:
            first = next(i for i in body["input"] if i.get("type") == "function_call_output")
            calls = [("get_findings", {"case_id": json.loads(first["output"])["case_id"]})]
        else:
            text = "Up to $1,596.53 may come off. Apply by April 1, 2026. Three letters are ready to sign."
            return [{"type": "response.output_text.delta", "delta": text},
                    {"type": "response.completed", "response": {"id": "r", "usage": {}, "output": [
                        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}]}}]
        out = [{"type": "function_call", "id": f"fc_{n}_{i}", "call_id": f"call_{n}_{i}", "name": name,
                "arguments": json.dumps(args), "status": "completed"} for i, (name, args) in enumerate(calls)]
        return [{"type": "response.completed", "response": {"id": f"r{n}", "usage": {}, "output": out}}]


def test_spark_uses_billradar_tools_and_answers():
    model = ScriptedSpark()
    r = asyncio.run(family_agent.run(MetaClient(transport=model, record_to=None, journal=None), build_server(),
                                     "Please check our bills."))
    assert [c.name for c in r.calls] == ["analyze_case", "get_findings"] and not any(c.is_error for c in r.calls)
    assert r.answer.startswith("Up to $1,596.53") and r.stopped == ""
    first = model.bodies[0]
    assert first["model"] == "muse-spark-1.3" and first["store"] is False
    names = {t["name"] for t in first["tools"]}
    assert "analyze_case" in names and "get_report_pdf" not in names
    assert all(t["type"] == "function" and t["parameters"]["type"] == "object" for t in first["tools"])
    second = model.bodies[1]["input"]
    kinds = [i.get("type", i.get("role")) for i in second]
    assert kinds == ["user", "function_call", "function_call_output"]  # results follow their calls
    assert second[2]["call_id"] == second[1]["call_id"]


def test_unknown_or_skipped_tool_is_refused_not_run():
    model = ScriptedSpark(extra_call=("get_report_pdf", {"case_id": "x"}))
    r = asyncio.run(family_agent.run(MetaClient(transport=model, record_to=None, journal=None), build_server(),
                                     "Please check our bills."))
    assert r.calls[1].name == "get_report_pdf" and r.calls[1].is_error


def test_turn_budget():
    class Loops(ScriptedSpark):
        def events(self, body):
            self.bodies.append(body)
            return [{"type": "response.completed", "response": {"id": "r", "usage": {}, "output": [
                {"type": "function_call", "id": "f", "call_id": f"c{len(self.bodies)}", "name": "list_sample_packs",
                 "arguments": "{}", "status": "completed"}]}}]
    r = asyncio.run(family_agent.run(MetaClient(transport=Loops(), record_to=None, journal=None), build_server(), "x"))
    assert r.stopped == "turn budget reached" and len(r.calls) == family_agent.MAX_TURNS
