#!/usr/bin/env python3
"""Replay a fixed OASST1 sample against baseline and optimized gateway routes."""

from __future__ import annotations

import argparse
from datetime import date
import gzip
import json
import math
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable


DATASET_REVISION = "fdf72ae0827c1cda404aff25b6603abec9e3399b"
DATASET_FILE = "2023-04-12_oasst_ready.trees.jsonl.gz"
DATASET_URL = (
    "https://huggingface.co/datasets/OpenAssistant/oasst1/resolve/"
    f"{DATASET_REVISION}/{DATASET_FILE}?download=true"
)


def _message(node: dict[str, Any]) -> dict[str, Any] | None:
    """Unwrap the nested OASST tree node representation."""
    message = node.get("message", node)
    return message if isinstance(message, dict) else None


def _first_assistant_reply(prompt: dict[str, Any]) -> dict[str, Any] | None:
    replies = prompt.get("replies") or []
    candidates: list[dict[str, Any]] = []
    for node in replies:
        message = _message(node)
        if message and message.get("role") == "assistant" and message.get("text"):
            candidates.append(message)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: str(item.get("message_id", "")))[0]


def select_corpus(rows: Iterable[dict[str, Any]], limit: int) -> list[dict[str, str]]:
    """Select a stable English prompt/reference sample from ready OASST1 trees."""
    selected: list[dict[str, str]] = []
    for row in rows:
        prompt = _message(row.get("prompt", {}))
        if not prompt or prompt.get("role") != "prompter" or prompt.get("lang") != "en":
            continue
        prompt_text = str(prompt.get("text", "")).strip()
        reply = _first_assistant_reply(prompt)
        if not prompt_text or not reply:
            continue
        reference = str(reply.get("text", "")).strip()
        if not reference:
            continue
        selected.append({
            "id": str(prompt.get("message_id", "")),
            "prompt": prompt_text,
            "reference": reference,
        })
    selected.sort(key=lambda item: item["id"])
    return selected[:limit]


def load_corpus(path: Path, limit: int) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return select_corpus((json.loads(line) for line in stream if line.strip()), limit)


def rouge_l_f1(candidate: str, reference: str) -> float:
    """Return ROUGE-L F1 as a lexical similarity proxy, not a quality verdict."""
    left = candidate.casefold().split()
    right = reference.casefold().split()
    if not left or not right:
        return 0.0
    previous = [0] * (len(right) + 1)
    for token in left:
        current = [0]
        for index, ref_token in enumerate(right, start=1):
            current.append(previous[index - 1] + 1 if token == ref_token else max(previous[index], current[-1]))
        previous = current
    overlap = previous[-1]
    precision = overlap / len(left)
    recall = overlap / len(right)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def _post_completion(
    base_url: str,
    gateway_key: str,
    model: str,
    prompt: str,
    provider: str | None,
    provider_key: str | None,
    timeout: float,
    bypass_cache: bool = False,
) -> dict[str, Any]:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 512,
    }).encode()
    headers = {
        "Authorization": f"Bearer {gateway_key}",
        "Content-Type": "application/json",
    }
    if provider:
        headers["X-Provider"] = provider
    if provider_key:
        headers["X-Provider-Api-Key"] = provider_key
    if bypass_cache:
        headers["Cache-Control"] = "no-cache"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "cache_hit": response.headers.get("X-Cache-Hit", "MISS") == "HIT",
                "body": body,
            }
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read())
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"error": "non-JSON error response"}
        return {
            "ok": False,
            "status": error.code,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "cache_hit": False,
            "body": body,
        }
    except Exception as error:
        return {
            "ok": False,
            "status": None,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "cache_hit": False,
            "body": {"error": type(error).__name__},
        }


def _usage(result: dict[str, Any]) -> tuple[int, int]:
    usage = result.get("body", {}).get("usage") or {}
    return int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def _cost(prompt_tokens: int, completion_tokens: int, input_rate: float, output_rate: float) -> float:
    return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000


def replay(args: argparse.Namespace) -> dict[str, Any]:
    corpus = load_corpus(args.corpus, args.limit)
    if not corpus:
        raise ValueError("The corpus did not contain eligible prompt/reference pairs")

    baseline: list[dict[str, Any]] = []
    optimized: list[dict[str, Any]] = []
    baseline_repeats: list[dict[str, Any]] = []
    optimized_repeats: list[dict[str, Any]] = []
    for item in corpus:
        baseline_result = _post_completion(
            args.baseline_url, args.gateway_key, args.baseline_model,
            item["prompt"], args.baseline_provider, args.baseline_provider_key, args.timeout,
            bypass_cache=True,
        )
        baseline_repeat = _post_completion(
            args.baseline_url, args.gateway_key, args.baseline_model,
            item["prompt"], args.baseline_provider, args.baseline_provider_key, args.timeout,
            bypass_cache=True,
        )
        optimized_result = _post_completion(
            args.optimized_url, args.gateway_key, args.optimized_model,
            item["prompt"], args.optimized_provider, args.optimized_provider_key, args.timeout,
        )
        repeat_result = _post_completion(
            args.optimized_url, args.gateway_key, args.optimized_model,
            item["prompt"], args.optimized_provider, args.optimized_provider_key, args.timeout,
        )
        baseline.append(baseline_result)
        baseline_repeats.append(baseline_repeat)
        optimized.append(optimized_result)
        optimized_repeats.append(repeat_result)

    baseline_costs: list[float] = []
    optimized_costs: list[float] = []
    cache_savings: list[float] = []
    baseline_quality: list[float] = []
    optimized_quality: list[float] = []
    raw_records: list[dict[str, Any]] = []
    for index, item in enumerate(corpus):
        before = baseline[index]
        after = optimized[index]
        repeat = optimized_repeats[index]
        baseline_repeat = baseline_repeats[index]
        before_tokens = _usage(before)
        before_repeat_tokens = _usage(baseline_repeat)
        after_tokens = _usage(after)
        repeat_tokens = _usage(repeat)
        before_cost = _cost(*before_tokens, args.baseline_input_price, args.baseline_output_price)
        before_repeat_cost = _cost(*before_repeat_tokens, args.baseline_input_price, args.baseline_output_price)
        after_uncached_cost = _cost(*after_tokens, args.optimized_input_price, args.optimized_output_price)
        after_cost = 0.0 if after["cache_hit"] else after_uncached_cost
        repeat_cost = 0.0 if repeat["cache_hit"] else _cost(
            *repeat_tokens, args.optimized_input_price, args.optimized_output_price
        )
        before_text = _response_text(before)
        after_text = _response_text(after)
        if before["ok"] and after["ok"] and before_text and after_text:
            baseline_quality.append(rouge_l_f1(before_text, item["reference"]))
            optimized_quality.append(rouge_l_f1(after_text, item["reference"]))
        comparable = all(
            result["ok"] and bool(result.get("body", {}).get("usage"))
            for result in (before, baseline_repeat, after, repeat)
        )
        if comparable:
            baseline_costs.extend([before_cost, before_repeat_cost])
            optimized_costs.extend([after_cost, repeat_cost])
            cache_savings.append(
                (after_uncached_cost if after["cache_hit"] else 0.0)
                + (_cost(*repeat_tokens, args.optimized_input_price, args.optimized_output_price)
                   if repeat["cache_hit"] else 0.0)
            )
        raw_records.append({
            "id": item["id"],
            "prompt": item["prompt"],
            "reference": item["reference"],
            "baseline": before,
            "baseline_repeat_no_cache": baseline_repeat,
            "optimized": after,
            "optimized_repeat": repeat,
            "baseline_rouge_l_f1": rouge_l_f1(before_text, item["reference"]) if before_text else None,
            "optimized_rouge_l_f1": rouge_l_f1(after_text, item["reference"]) if after_text else None,
            "baseline_estimated_cost_usd": before_cost,
            "baseline_repeat_estimated_cost_usd": before_repeat_cost,
            "optimized_estimated_cost_usd": after_cost,
            "repeat_estimated_cost_usd": repeat_cost,
            "optimized_estimated_cache_savings_usd": (
                after_uncached_cost if after["cache_hit"] else 0.0
            ),
            "repeat_estimated_cache_savings_usd": (
                _cost(*repeat_tokens, args.optimized_input_price, args.optimized_output_price)
                if repeat["cache_hit"] else 0.0
            ),
        })

    baseline_total = sum(baseline_costs)
    optimized_total = sum(optimized_costs)
    cache_hits = sum(item["cache_hit"] for item in optimized_repeats)
    optimized_cache_hits = cache_hits + sum(item["cache_hit"] for item in optimized)
    return {
        "metadata": {
            "dataset": "OpenAssistant/oasst1",
            "dataset_url": DATASET_URL,
            "dataset_revision": DATASET_REVISION,
            "dataset_file": DATASET_FILE,
            "dataset_license": "Apache-2.0",
            "sample_count": len(corpus),
            "baseline_model": args.baseline_model,
            "baseline_provider": args.baseline_provider,
            "baseline_resolved_models": sorted({
                str(result.get("body", {}).get("model"))
                for result in baseline + baseline_repeats
                if result.get("body", {}).get("model")
            }),
            "optimized_model": args.optimized_model,
            "optimized_provider": args.optimized_provider,
            "optimized_resolved_models": sorted({
                str(result.get("body", {}).get("model"))
                for result in optimized + optimized_repeats
                if result.get("body", {}).get("model")
            }),
            "price_inputs_usd_per_million_tokens": {
                "baseline_input": args.baseline_input_price,
                "baseline_output": args.baseline_output_price,
                "optimized_input": args.optimized_input_price,
                "optimized_output": args.optimized_output_price,
            },
            "pricing_effective_date": args.pricing_date,
            "pricing_sources": {
                "baseline": args.baseline_price_source,
                "optimized": args.optimized_price_source,
            },
            "request_settings": {"temperature": 0, "max_tokens": 512},
            "cache_modes": {"baseline": "bypass", "optimized": "exact-match"},
            "cost_method": "estimated from observed API token usage and supplied per-token prices; not a provider invoice",
        },
        "summary": {
            "baseline": _summarize(baseline + baseline_repeats, baseline_quality, baseline_total),
            "optimized": _summarize(optimized + optimized_repeats, optimized_quality, optimized_total),
            "cost_comparisons": len(baseline_costs) // 2,
            "estimated_savings_usd": baseline_total - optimized_total if baseline_costs else None,
            "estimated_savings_fraction": (baseline_total - optimized_total) / baseline_total if baseline_total else None,
            "estimated_cache_savings_usd": sum(cache_savings) if cache_savings else None,
            "optimized_cache_hits": optimized_cache_hits,
            "optimized_cache_hit_ratio": optimized_cache_hits / (len(optimized) + len(optimized_repeats)),
            "quality_delta_rouge_l_f1": (
                statistics.mean(optimized_quality) - statistics.mean(baseline_quality)
                if optimized_quality and baseline_quality else None
            ),
            "quality_metric_note": "ROUGE-L F1 is a lexical similarity proxy against one human reference, not a comprehensive quality judgment.",
        },
        "records": raw_records,
    }


def _response_text(result: dict[str, Any]) -> str:
    try:
        return str(result["body"]["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return ""


def _summarize(results: list[dict[str, Any]], quality: list[float], estimated_cost: float) -> dict[str, Any]:
    latencies = [item["latency_ms"] for item in results]
    successes = sum(item["ok"] for item in results)
    usage_count = sum(bool(item.get("body", {}).get("usage")) for item in results)
    return {
        "requests": len(results),
        "successes": successes,
        "failures": len(results) - successes,
        "failure_rate": (len(results) - successes) / len(results) if results else 0,
        "latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
        "mean_rouge_l_f1": statistics.mean(quality) if quality else None,
        "quality_comparisons": len(quality),
        "requests_with_usage": usage_count,
        "estimated_cost_usd": estimated_cost,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", type=Path,
        default=Path("datasets") / DATASET_FILE,
        help="Pinned OASST1 trees JSONL(.gz) file (downloaded if absent)",
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--baseline-url", required=True, help="Gateway base URL for baseline requests")
    parser.add_argument("--optimized-url", help="Defaults to --baseline-url")
    parser.add_argument("--baseline-model", required=True, help="Baseline model name or alias")
    parser.add_argument("--optimized-model", required=True, help="Optimized model name or route alias")
    parser.add_argument("--baseline-provider", help="Provider for a concrete baseline model")
    parser.add_argument("--optimized-provider", help="Optional provider override for optimized route")
    parser.add_argument("--baseline-provider-key", default=os.getenv("BASELINE_PROVIDER_API_KEY"))
    parser.add_argument("--optimized-provider-key", default=os.getenv("OPTIMIZED_PROVIDER_API_KEY"))
    parser.add_argument("--gateway-key", default=os.getenv("GATEWAY_API_KEY"), required=not bool(os.getenv("GATEWAY_API_KEY")))
    parser.add_argument("--baseline-input-price", type=float, required=True, help="USD per million input tokens")
    parser.add_argument("--baseline-output-price", type=float, required=True, help="USD per million output tokens")
    parser.add_argument("--optimized-input-price", type=float, required=True, help="USD per million input tokens")
    parser.add_argument("--optimized-output-price", type=float, required=True, help="USD per million output tokens")
    parser.add_argument("--pricing-date", required=True, help="Date for supplied price inputs (YYYY-MM-DD)")
    parser.add_argument("--baseline-price-source", required=True, help="URL or identifier for baseline prices")
    parser.add_argument("--optimized-price-source", required=True, help="URL or identifier for optimized prices")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--output", type=Path, default=Path("benchmark-results.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1 or args.timeout <= 0:
        raise SystemExit("--limit and --timeout must be positive")
    prices = (
        args.baseline_input_price, args.baseline_output_price,
        args.optimized_input_price, args.optimized_output_price,
    )
    if any(not math.isfinite(price) or price < 0 for price in prices):
        raise SystemExit("Token prices must be finite, non-negative USD values")
    try:
        date.fromisoformat(args.pricing_date)
    except ValueError as error:
        raise SystemExit("--pricing-date must use YYYY-MM-DD") from error
    if args.optimized_url is None:
        args.optimized_url = args.baseline_url
    if not args.corpus.exists():
        args.corpus.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading pinned OASST1 corpus to {args.corpus}")
        urllib.request.urlretrieve(DATASET_URL, args.corpus)
    result = replay(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"Raw request and response records written to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
