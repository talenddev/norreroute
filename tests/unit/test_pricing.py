"""Unit tests for pricing.py — ModelPrice, CostEstimate, estimate_cost, count_tokens_approx."""  # noqa: E501

from __future__ import annotations

import pytest

from norreroute.errors import UnknownModelError
from norreroute.pricing import (
    CostEstimate,
    ModelPrice,
    count_tokens_approx,
    estimate_cost,
)
from norreroute.pricing_data import MODEL_PRICING
from norreroute.types import ChatRequest, ChatResponse, Message, TextPart, Usage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    model: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> ChatResponse:
    return ChatResponse(
        model=model,
        content=[TextPart(text="result")],
        finish_reason="stop",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        raw={},
    )


def _make_request(text: str = "hello world") -> ChatRequest:
    return ChatRequest(
        model="test-model",
        messages=[Message(role="user", content=[TextPart(text=text)])],
    )


# ---------------------------------------------------------------------------
# ModelPrice
# ---------------------------------------------------------------------------


class TestModelPrice:
    def test_frozen_dataclass(self) -> None:
        price = ModelPrice(input_per_mtok_usd=3.0, output_per_mtok_usd=15.0)
        with pytest.raises(Exception):
            price.input_per_mtok_usd = 1.0  # type: ignore[misc]

    def test_zero_price(self) -> None:
        price = ModelPrice(input_per_mtok_usd=0.0, output_per_mtok_usd=0.0)
        assert price.input_per_mtok_usd == 0.0
        assert price.output_per_mtok_usd == 0.0


# ---------------------------------------------------------------------------
# MODEL_PRICING data
# ---------------------------------------------------------------------------


class TestModelPricingData:
    def test_all_required_models_present(self) -> None:
        required = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "llama3.1",
            "qwen2.5",
        ]
        for model in required:
            assert model in MODEL_PRICING, f"{model} missing from MODEL_PRICING"

    def test_claude_sonnet_prices(self) -> None:
        p = MODEL_PRICING["claude-3-5-sonnet-20241022"]
        assert p.input_per_mtok_usd == 3.00
        assert p.output_per_mtok_usd == 15.00

    def test_claude_haiku_prices(self) -> None:
        p = MODEL_PRICING["claude-3-5-haiku-20241022"]
        assert p.input_per_mtok_usd == 0.80
        assert p.output_per_mtok_usd == 4.00

    def test_claude_opus_prices(self) -> None:
        p = MODEL_PRICING["claude-3-opus-20240229"]
        assert p.input_per_mtok_usd == 15.00
        assert p.output_per_mtok_usd == 75.00

    def test_ollama_models_are_free(self) -> None:
        for model in ["llama3.1", "qwen2.5"]:
            p = MODEL_PRICING[model]
            assert p.input_per_mtok_usd == 0.0
            assert p.output_per_mtok_usd == 0.0


# ---------------------------------------------------------------------------
# estimate_cost — table-driven for known models
# ---------------------------------------------------------------------------


class TestEstimateCostKnownModels:
    @pytest.mark.parametrize(
        "model,input_tokens,output_tokens,expected_input,expected_output",
        [
            # claude-3-5-sonnet: 3.00/15.00 per mtok
            (
                "claude-3-5-sonnet-20241022",
                1_000_000,
                1_000_000,
                3.00,
                15.00,
            ),
            (
                "claude-3-5-sonnet-20241022",
                500_000,
                200_000,
                1.50,
                3.00,
            ),
            # claude-3-5-haiku: 0.80/4.00 per mtok
            (
                "claude-3-5-haiku-20241022",
                1_000_000,
                1_000_000,
                0.80,
                4.00,
            ),
            # claude-3-opus: 15.00/75.00 per mtok
            (
                "claude-3-opus-20240229",
                1_000_000,
                1_000_000,
                15.00,
                75.00,
            ),
            # ollama — free
            ("llama3.1", 100_000, 50_000, 0.0, 0.0),
            ("qwen2.5", 100_000, 50_000, 0.0, 0.0),
        ],
    )
    def test_cost_math(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        expected_input: float,
        expected_output: float,
    ) -> None:
        resp = _make_response(model, input_tokens, output_tokens)
        est = estimate_cost(resp)
        assert est.model == model
        assert est.input_tokens == input_tokens
        assert est.output_tokens == output_tokens
        assert abs(est.input_cost_usd - expected_input) < 1e-9
        assert abs(est.output_cost_usd - expected_output) < 1e-9
        assert abs(est.total_cost_usd - (expected_input + expected_output)) < 1e-9
        assert est.is_estimate is False


# ---------------------------------------------------------------------------
# estimate_cost — error cases
# ---------------------------------------------------------------------------


class TestEstimateCostErrors:
    def test_unknown_model_raises(self) -> None:
        resp = _make_response("totally-unknown-model-xyz")
        with pytest.raises(UnknownModelError):
            estimate_cost(resp)

    def test_explicit_pricing_overrides_builtin(self) -> None:
        custom = {"my-model": ModelPrice(1.0, 2.0)}
        resp = _make_response("my-model", 1_000_000, 1_000_000)
        est = estimate_cost(resp, custom)
        assert abs(est.input_cost_usd - 1.0) < 1e-9
        assert abs(est.output_cost_usd - 2.0) < 1e-9
        assert est.is_estimate is False

    def test_explicit_pricing_takes_precedence_over_builtin(self) -> None:
        """Even for a known model, explicit pricing wins."""
        override = {"claude-3-5-sonnet-20241022": ModelPrice(0.01, 0.02)}
        resp = _make_response("claude-3-5-sonnet-20241022", 1_000_000, 1_000_000)
        est = estimate_cost(resp, override)
        assert abs(est.input_cost_usd - 0.01) < 1e-9

    def test_prefix_match_builtin(self) -> None:
        """A model name like 'llama3.1:latest' prefix-matches 'llama3.1'."""
        resp = _make_response("llama3.1:latest", 1_000, 1_000)
        est = estimate_cost(resp)
        assert est.input_cost_usd == 0.0
        assert est.output_tokens == 1_000

    def test_prefix_match_explicit_pricing(self) -> None:
        """Prefix match also works in the caller-supplied pricing table."""
        custom = {"my-base": ModelPrice(5.0, 10.0)}
        resp = _make_response("my-base:instruct", 1_000_000, 1_000_000)
        est = estimate_cost(resp, custom)
        assert abs(est.input_cost_usd - 5.0) < 1e-9
        assert abs(est.output_cost_usd - 10.0) < 1e-9

    def test_missing_usage_sets_is_estimate(self) -> None:
        """Zero-usage response triggers approximation, sets is_estimate=True."""
        resp = ChatResponse(
            model="claude-3-5-sonnet-20241022",
            content=[TextPart(text="hi")],
            finish_reason="stop",
            usage=Usage(input_tokens=0, output_tokens=0),
            raw={},
        )
        est = estimate_cost(resp)
        assert est.is_estimate is True

    def test_missing_usage_with_request_approximates(self) -> None:
        resp = ChatResponse(
            model="claude-3-5-sonnet-20241022",
            content=[TextPart(text="hi")],
            finish_reason="stop",
            usage=Usage(input_tokens=0, output_tokens=0),
            raw={},
        )
        req = _make_request("hello world")  # 11 chars → 2 tokens
        est = estimate_cost(resp, request=req)
        assert est.is_estimate is True
        assert est.input_tokens == 2  # 11 // 4 = 2


# ---------------------------------------------------------------------------
# count_tokens_approx
# ---------------------------------------------------------------------------


class TestCountTokensApprox:
    def test_simple_text(self) -> None:
        req = ChatRequest(
            model="m",
            messages=[Message(role="user", content=[TextPart(text="abcd")])],
        )
        assert count_tokens_approx(req) == 1  # 4 chars // 4

    def test_multiple_messages(self) -> None:
        req = ChatRequest(
            model="m",
            messages=[
                Message(role="user", content=[TextPart(text="abcd")]),  # 4
                Message(role="assistant", content=[TextPart(text="efgh")]),  # 4
            ],
        )
        assert count_tokens_approx(req) == 2  # 8 // 4

    def test_system_prompt_counted(self) -> None:
        req = ChatRequest(
            model="m",
            system="AAAA",  # 4 chars
            messages=[Message(role="user", content=[TextPart(text="BBBB")])],  # 4
        )
        assert count_tokens_approx(req) == 2  # (4 + 4) // 4

    def test_empty_request(self) -> None:
        req = ChatRequest(
            model="m",
            messages=[],
        )
        assert count_tokens_approx(req) == 0

    def test_floor_division(self) -> None:
        req = ChatRequest(
            model="m",
            messages=[Message(role="user", content=[TextPart(text="abc")])],  # 3 chars
        )
        assert count_tokens_approx(req) == 0  # 3 // 4 = 0

    def test_large_input(self) -> None:
        text = "a" * 4000
        req = ChatRequest(
            model="m",
            messages=[Message(role="user", content=[TextPart(text=text)])],
        )
        assert count_tokens_approx(req) == 1000


# ---------------------------------------------------------------------------
# CostEstimate
# ---------------------------------------------------------------------------


class TestCostEstimate:
    def test_frozen_dataclass(self) -> None:
        est = CostEstimate(
            model="m",
            input_tokens=1,
            output_tokens=1,
            input_cost_usd=0.0,
            output_cost_usd=0.0,
            total_cost_usd=0.0,
            is_estimate=False,
        )
        with pytest.raises(Exception):
            est.model = "other"  # type: ignore[misc]
