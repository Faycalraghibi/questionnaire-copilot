"""Model wrapper: OpenAI, Anthropic, and offline stub provider (rules section 6)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from qc.config import DEFAULT_MODELS, MODEL_PRICES_USD_PER_M, get_settings

DEFAULT_STUB_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "stub"


class CostCapExceeded(RuntimeError):
    """Raised when accumulated model spend exceeds MAX_EVAL_COST_USD (decision D22)."""


@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    model: str


class LLM(Protocol):
    def complete(
        self, system: str, messages: list[dict], *, max_tokens: int = 800
    ) -> tuple[str, LLMUsage]: ...

    def structured(
        self,
        system: str,
        messages: list[dict],
        schema: type[BaseModel],
        *,
        max_tokens: int = 1500,
    ) -> tuple[BaseModel, LLMUsage]: ...


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = MODEL_PRICES_USD_PER_M.get(model, (0.0, 0.0))
    return round((input_tokens * in_rate + output_tokens * out_rate) / 1_000_000, 6)


class _SpendTracker:
    def __init__(self, max_cost_usd: float | None = None) -> None:
        self.total_cost_usd = 0.0
        self.max_cost_usd = (
            get_settings().max_eval_cost_usd if max_cost_usd is None else max_cost_usd
        )

    def check_budget(self) -> None:
        if self.total_cost_usd >= self.max_cost_usd:
            raise CostCapExceeded(
                f"Spend {self.total_cost_usd:.4f} USD reached cap {self.max_cost_usd:.4f} USD"
            )

    def record(self, cost_usd: float) -> None:
        self.total_cost_usd += cost_usd


class OpenAILLM(_SpendTracker):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        max_cost_usd: float | None = None,
    ):
        super().__init__(max_cost_usd)
        from openai import OpenAI

        self.model = model
        self._client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY") or None,
            base_url=base_url or os.environ.get("OPENAI_BASE_URL") or None,
        )

    def complete(
        self, system: str, messages: list[dict], *, max_tokens: int = 800
    ) -> tuple[str, LLMUsage]:
        self.check_budget()
        t0 = time.perf_counter()
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        in_tok = resp.usage.prompt_tokens if resp.usage else 0
        out_tok = resp.usage.completion_tokens if resp.usage else 0
        cost = compute_cost_usd(self.model, in_tok, out_tok)
        self.record(cost)
        text = resp.choices[0].message.content or ""
        return text, LLMUsage(in_tok, out_tok, cost, latency_ms, self.model)

    def structured(
        self,
        system: str,
        messages: list[dict],
        schema: type[BaseModel],
        *,
        max_tokens: int = 1500,
    ) -> tuple[BaseModel, LLMUsage]:
        self.check_budget()
        t0 = time.perf_counter()
        resp = self._client.chat.completions.parse(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            response_format=schema,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        in_tok = resp.usage.prompt_tokens if resp.usage else 0
        out_tok = resp.usage.completion_tokens if resp.usage else 0
        cost = compute_cost_usd(self.model, in_tok, out_tok)
        self.record(cost)
        parsed = resp.choices[0].message.parsed
        if parsed is None:
            raise ValueError("OpenAI structured output returned None")
        return parsed, LLMUsage(in_tok, out_tok, cost, latency_ms, self.model)


class AnthropicLLM(_SpendTracker):
    def __init__(self, model: str, api_key: str | None = None, max_cost_usd: float | None = None):
        super().__init__(max_cost_usd)
        from anthropic import Anthropic

        self.model = model
        self._client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY") or None)

    def complete(
        self, system: str, messages: list[dict], *, max_tokens: int = 800
    ) -> tuple[str, LLMUsage]:
        self.check_budget()
        t0 = time.perf_counter()
        resp = self._client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        cost = compute_cost_usd(self.model, in_tok, out_tok)
        self.record(cost)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return text, LLMUsage(in_tok, out_tok, cost, latency_ms, self.model)

    def structured(
        self,
        system: str,
        messages: list[dict],
        schema: type[BaseModel],
        *,
        max_tokens: int = 1500,
    ) -> tuple[BaseModel, LLMUsage]:
        self.check_budget()
        t0 = time.perf_counter()
        resp = self._client.messages.parse(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            output_format=schema,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        cost = compute_cost_usd(self.model, in_tok, out_tok)
        self.record(cost)
        if resp.parsed_output is None:
            raise ValueError("Anthropic structured output returned None")
        return resp.parsed_output, LLMUsage(in_tok, out_tok, cost, latency_ms, self.model)


class StubLLM(_SpendTracker):
    """Offline stub reading canned JSON outputs from tests/fixtures/stub/*.json."""

    def __init__(
        self,
        model: str = "stub",
        fixture_dir: Path | None = None,
        canned: dict[str, dict] | None = None,
        max_cost_usd: float | None = None,
    ) -> None:
        super().__init__(max_cost_usd)
        self.model = model
        self.calls: list[dict] = []
        self._canned: dict[str, dict] = {}
        root = fixture_dir or DEFAULT_STUB_DIR
        if root.exists():
            for path in sorted(root.glob("*.json")):
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._canned[path.stem] = data
        if canned:
            self._canned.update(canned)

    def _match_fixture(self, prompt_text: str) -> dict | None:
        low = prompt_text.lower()
        for key, payload in self._canned.items():
            match = str(payload.get("match", key)).lower()
            if match and match in low:
                return payload
        return self._canned.get("default")

    def complete(
        self, system: str, messages: list[dict], *, max_tokens: int = 800
    ) -> tuple[str, LLMUsage]:
        self.check_budget()
        prompt_text = "\n".join(str(m.get("content", "")) for m in messages)
        self.calls.append({"mode": "complete", "system": system, "messages": messages})
        payload = self._match_fixture(prompt_text) or {}
        text = str(payload.get("text", "OK"))
        usage = LLMUsage(100, 20, 0.0, 1, self.model)
        return text, usage

    def structured(
        self,
        system: str,
        messages: list[dict],
        schema: type[BaseModel],
        *,
        max_tokens: int = 1500,
    ) -> tuple[BaseModel, LLMUsage]:
        self.check_budget()
        prompt_text = "\n".join(str(m.get("content", "")) for m in messages)
        self.calls.append(
            {
                "mode": "structured",
                "schema": schema.__name__,
                "system": system,
                "messages": messages,
            }
        )
        payload = self._match_fixture(prompt_text) or {}
        output = payload.get("output", payload)
        parsed = schema.model_validate(output)
        usage = LLMUsage(150, 50, 0.0, 1, self.model)
        return parsed, usage


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    fixture_dir: Path | None = None,
) -> LLM:
    settings = get_settings()
    prov = (provider or settings.llm_provider).lower()
    mdl = model or settings.llm_model or DEFAULT_MODELS.get(prov, "stub")
    if prov == "stub":
        return StubLLM(model=mdl, fixture_dir=fixture_dir, max_cost_usd=settings.max_eval_cost_usd)
    if prov == "openai":
        return OpenAILLM(
            model=mdl,
            api_key=settings.openai_api_key or None,
            base_url=settings.openai_base_url or None,
            max_cost_usd=settings.max_eval_cost_usd,
        )
    if prov == "anthropic":
        return AnthropicLLM(
            model=mdl,
            api_key=settings.anthropic_api_key or None,
            max_cost_usd=settings.max_eval_cost_usd,
        )
    raise ValueError(f"Unknown llm_provider: {prov}")
