#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any, Dict


def reasoning_tokens(payload: Dict[str, Any]) -> int | None:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None
    details = usage.get("output_tokens_details") or usage.get("completion_tokens_details")
    if isinstance(details, dict) and details.get("reasoning_tokens") is not None:
        return int(details["reasoning_tokens"])
    if usage.get("reasoning_tokens") is not None:
        return int(usage["reasoning_tokens"])
    return None


def send(base_url: str, api_key: str, model: str, effort: str, timeout: int) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/responses"
    body = json.dumps({
        "model": model,
        "input": "Reply with exactly: OK",
        "reasoning": {"effort": effort},
        "max_output_tokens": 16,
        "stream": False,
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {
                "effort": effort,
                "http_status": response.status,
                "reasoning_tokens": reasoning_tokens(payload),
                "response_id": str(payload.get("id") or "")[:24],
            }
    except urllib.error.HTTPError as error:
        return {"effort": effort, "http_status": error.code, "reasoning_tokens": None, "error": "upstream_http_error"}
    except Exception:
        return {"effort": effort, "http_status": 0, "reasoning_tokens": None, "error": "request_failed"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a controlled low/high reasoning A/B request through Lin Router")
    parser.add_argument("--base-url", default="http://127.0.0.1:18400/v1")
    parser.add_argument("--api-key", required=True, help="Lin Router group or aggregate route key; never printed")
    parser.add_argument("--model", required=True)
    parser.add_argument("--waf-state", choices=["off", "on"], required=True, help="Current WAF setting, used only as the report label")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    results = [send(args.base_url, args.api_key, args.model, effort, args.timeout) for effort in ("low", "high")]
    low_tokens = results[0].get("reasoning_tokens")
    high_tokens = results[1].get("reasoning_tokens")
    print(json.dumps({
        "waf_state": args.waf_state,
        "model": args.model,
        "results": results,
        "observable_difference": low_tokens is not None and high_tokens is not None and low_tokens != high_tokens,
        "note": "Check Lin Router logs for requested_reasoning_effort and reasoning_preserved. Equal upstream behavior can indicate channel-side ignore/unsupported behavior.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
