from argparse import Namespace

import pytest

import scripts.replay_evaluation as evaluation
from scripts.replay_evaluation import percentile, rouge_l_f1, select_corpus


def test_select_corpus_is_deterministic_and_filters_unmatched_languages():
    rows = [
        {
            "prompt": {
                "message_id": "b",
                "text": "Second prompt",
                "role": "prompter",
                "lang": "en",
                "replies": [{"message_id": "rb", "text": "Answer B", "role": "assistant"}],
            }
        },
        {
            "prompt": {
                "message_id": "a",
                "text": "First prompt",
                "role": "prompter",
                "lang": "en",
                "replies": [{"message_id": "ra", "text": "Answer A", "role": "assistant"}],
            }
        },
        {
            "prompt": {
                "message_id": "c",
                "text": "Spanish prompt",
                "role": "prompter",
                "lang": "es",
                "replies": [{"message_id": "rc", "text": "Respuesta", "role": "assistant"}],
            }
        },
    ]

    selected = select_corpus(rows, 1)

    assert selected == [{"id": "a", "prompt": "First prompt", "reference": "Answer A"}]


def test_rouge_l_f1_and_percentile():
    assert rouge_l_f1("a b c", "a b x") == 2 / 3
    assert rouge_l_f1("", "reference") == 0
    assert percentile([8, 2, 5, 1], 0.5) == 2
    assert percentile([], 0.95) == 0


def test_replay_separates_estimated_routing_and_cache_savings(monkeypatch, tmp_path):
    corpus = [{"id": "a", "prompt": "question", "reference": "reference answer"}]
    monkeypatch.setattr(evaluation, "load_corpus", lambda _path, _limit: corpus)
    responses = iter([
        {"ok": True, "status": 200, "latency_ms": 100, "cache_hit": False,
         "body": {"model": "large", "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                  "choices": [{"message": {"content": "reference answer"}}]}},
        {"ok": True, "status": 200, "latency_ms": 90, "cache_hit": False,
         "body": {"model": "large", "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                  "choices": [{"message": {"content": "reference answer"}}]}},
        {"ok": True, "status": 200, "latency_ms": 40, "cache_hit": False,
         "body": {"model": "small", "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                  "choices": [{"message": {"content": "reference answer"}}]}},
        {"ok": True, "status": 200, "latency_ms": 5, "cache_hit": True,
         "body": {"model": "small", "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                  "choices": [{"message": {"content": "reference answer"}}]}},
    ])
    monkeypatch.setattr(evaluation, "_post_completion", lambda *args, **kwargs: next(responses))
    args = Namespace(
        corpus=tmp_path / "unused.jsonl", limit=1,
        baseline_url="http://gateway", optimized_url="http://gateway",
        baseline_model="large", optimized_model="small", gateway_key="gateway-key",
        baseline_provider="provider", optimized_provider="provider",
        baseline_provider_key="baseline-key", optimized_provider_key="optimized-key",
        timeout=10, baseline_input_price=1.0, baseline_output_price=2.0,
        optimized_input_price=0.5, optimized_output_price=1.0,
        pricing_date="2026-10-18", baseline_price_source="baseline source",
        optimized_price_source="optimized source",
    )

    result = evaluation.replay(args)

    assert result["summary"]["estimated_savings_usd"] == pytest.approx(0.0003)
    assert result["summary"]["estimated_cache_savings_usd"] == pytest.approx(0.0001)
    assert result["summary"]["optimized_cache_hit_ratio"] == 0.5
    assert result["metadata"]["baseline_resolved_models"] == ["large"]
