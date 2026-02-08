#!/usr/bin/env python3
"""
Interactive auth setup for Instagram crawler.
Logs in via Playwright, captures cookies + headers + endpoints from network.
"""

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

from config_loader import ConfigLoader


HEADER_KEYS = {
    "x-csrftoken": "X-CSRFToken",
    "x-ig-app-id": "X-IG-App-ID",
    "x-ig-www-claim": "X-IG-WWW-Claim",
    "x-asbd-id": "X-ASBD-ID",
    "referer": "Referer",
    "user-agent": "User-Agent",
}


def extract_shortcode_from_url(url: str) -> str | None:
    match = re.search(r"instagram\.com/(p|reel|tv)/([^/?#]+)/?", url)
    if not match:
        return None
    return match.group(2)


def normalize_headers(headers: dict) -> dict:
    normalized = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in HEADER_KEYS and value:
            normalized[HEADER_KEYS[lower]] = value
    return normalized


def parse_request_payload(request) -> dict:
    if request.method.upper() == "GET":
        parsed = urlparse(request.url)
        return {k: v[0] for k, v in parse_qs(parsed.query).items()}

    if not request.post_data:
        return {}

    # Try JSON first
    try:
        json_payload = request.post_data_json()
        if isinstance(json_payload, dict):
            return json_payload
    except Exception:
        pass

    # Fallback to querystring
    try:
        return {k: v[0] for k, v in parse_qs(request.post_data).items()}
    except Exception:
        return {}


def render_variables_template(variables: dict, known: dict) -> dict:
    if not isinstance(variables, dict):
        return {}

    template = {}
    for key, value in variables.items():
        if key in {"shortcode", "short_code"}:
            template[key] = "{shortcode}"
        elif key in {"after", "cursor"}:
            template[key] = "{cursor}"
        elif key in {"comment_id", "parent_comment_id"}:
            template[key] = "{comment_id}"
        elif key in {"media_id", "mediaId"}:
            template[key] = "{media_id}"
        else:
            template[key] = value
    return template


def classify_endpoint(payload: dict, url: str) -> str | None:
    variables = payload.get("variables")
    if isinstance(variables, str):
        try:
            variables = json.loads(variables)
        except Exception:
            variables = None

    friendly_name = payload.get("fb_api_req_friendly_name") or payload.get("friendly_name")
    friendly_lower = friendly_name.lower() if isinstance(friendly_name, str) else ""
    if friendly_lower:
        if "comment" in friendly_lower:
            if "reply" in friendly_lower or "repl" in friendly_lower or "child" in friendly_lower:
                return "comment_replies"
            return "comments"
        if "shortcode" in friendly_lower or "media" in friendly_lower:
            return "post_by_shortcode"
        if "timeline" in friendly_lower or "feed" in friendly_lower or "stories" in friendly_lower:
            return None

    if isinstance(variables, dict):
        if "comment_id" in variables or "parent_comment_id" in variables:
            return "comment_replies"
        if "shortcode" in variables or "short_code" in variables:
            return "post_by_shortcode"
        if "media_id" in variables and "first" in variables:
            return "comments"
        if "first" in variables and ("after" in variables or "cursor" in variables):
            return "comments"

    if "comment" in url:
        return "comments"

    return None


def build_endpoint_config(request, known: dict) -> dict:
    payload = parse_request_payload(request)
    variables = payload.get("variables")
    if isinstance(variables, str):
        try:
            variables = json.loads(variables)
        except Exception:
            variables = None

    endpoint = {
        "type": "graphql" if "graphql" in request.url else "rest",
        "method": request.method.upper(),
        "url": request.url.split("?")[0],
    }

    if "doc_id" in payload:
        endpoint["doc_id"] = payload.get("doc_id")
    if "query_hash" in payload:
        endpoint["query_hash"] = payload.get("query_hash")

    if isinstance(variables, dict):
        endpoint["variables"] = render_variables_template(variables, known)

    # Keep any fixed params (non-variables, non-doc_id) if present
    extra_params = {}
    for key, value in payload.items():
        if key in {"variables", "doc_id", "query_hash"}:
            continue
        extra_params[key] = value
    if extra_params:
        endpoint["params"] = extra_params

    return endpoint


def update_env_file(env_path: Path, updates: dict) -> None:
    if not env_path.exists():
        content = ""
    else:
        content = env_path.read_text(encoding="utf-8")

    for key, value in updates.items():
        pattern = rf"^{re.escape(key)}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, content, flags=re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            content += f"\n{replacement}"

    env_path.write_text(content.strip() + "\n", encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-url", help="Optional Instagram post URL to open")
    parser.add_argument("--config", default="config.json", help="Config file path")
    args = parser.parse_args()

    post_url = args.post_url
    shortcode = extract_shortcode_from_url(post_url) if post_url else None

    user_data_dir = Path(__file__).parent / "browser_data"
    config_path = Path(args.config)

    captured_headers = {}
    captured_endpoints = {}
    capture_log = []
    request_count = 0
    candidate_count = 0

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        def handle_request(request):
            if "instagram.com" not in request.url:
                return
            nonlocal request_count, candidate_count
            request_count += 1

            payload = parse_request_payload(request)
            payload_keys = list(payload.keys()) if isinstance(payload, dict) else []
            is_candidate = any(key in payload_keys for key in ["doc_id", "query_hash", "variables", "fb_api_req_friendly_name"])
            if is_candidate:
                candidate_count += 1

            headers = normalize_headers(request.headers)
            for key, value in headers.items():
                if key not in captured_headers:
                    captured_headers[key] = value

            endpoint_type = classify_endpoint(payload, request.url) if is_candidate else None
            if endpoint_type and endpoint_type not in captured_endpoints:
                captured_endpoints[endpoint_type] = build_endpoint_config(request, {"shortcode": shortcode})
                print(f"Captured endpoint: {endpoint_type}")

            # Log every Instagram XHR/Fetch request for debugging
            if request.resource_type in {"xhr", "fetch"}:
                capture_log.append({
                    "timestamp": time.time(),
                    "url": request.url,
                    "method": request.method,
                    "resource_type": request.resource_type,
                    "endpoint_type": endpoint_type,
                    "payload_keys": payload_keys,
                    "payload": payload,
                    "headers": {
                        k: v for k, v in request.headers.items()
                        if k.lower() in {"x-csrftoken", "x-ig-app-id", "x-ig-www-claim", "x-asbd-id", "referer", "user-agent"}
                    },
                })

        page.on("request", handle_request)

        if post_url:
            await page.goto(post_url)
        else:
            await page.goto("https://www.instagram.com/")

        print("\nActions:")
        print("1) Log in if needed")
        print("2) Open a target post")
        print("3) Scroll comments so comment requests fire")
        print("4) Wait for capture logs, then press Ctrl+C")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            # Capture cookies
            cookies = await context.cookies()
            cookie_map = {c["name"]: c["value"] for c in cookies}

            loader = ConfigLoader(config_file=config_path)
            config = loader.config
            ig = config.get("instagram", {})

            ig_cookies = ig.get("authentication", {}).get("cookies", {})
            ig_headers = ig.get("authentication", {}).get("headers", {})

            for key in ["sessionid", "csrftoken", "ds_user_id", "rur"]:
                if cookie_map.get(key):
                    ig_cookies[key] = cookie_map.get(key)

            for key, value in captured_headers.items():
                ig_headers[key] = value

            endpoints = ig.get("endpoints", {})
            for key, value in captured_endpoints.items():
                endpoints[key] = value

            ig["authentication"]["cookies"] = ig_cookies
            ig["authentication"]["headers"] = ig_headers
            ig["endpoints"] = endpoints
            config["instagram"] = ig

            loader.config = config
            loader.save_to_json(config_path)

            env_updates = {
                "IG_SESSIONID": ig_cookies.get("sessionid", ""),
                "IG_CSRFTOKEN": ig_cookies.get("csrftoken", ""),
                "IG_DS_USER_ID": ig_cookies.get("ds_user_id", ""),
                "IG_RUR": ig_cookies.get("rur", ""),
                "IG_X_CSRF_TOKEN": ig_headers.get("X-CSRFToken", ""),
                "IG_X_IG_APP_ID": ig_headers.get("X-IG-App-ID", ""),
                "IG_X_IG_WWW_CLAIM": ig_headers.get("X-IG-WWW-Claim", ""),
                "IG_X_ASBD_ID": ig_headers.get("X-ASBD-ID", ""),
                "IG_USER_AGENT": ig_headers.get("User-Agent", ""),
                "IG_REFERER": ig_headers.get("Referer", ""),
            }

            env_path = Path(__file__).parent / ".env"
            update_env_file(env_path, env_updates)

            # Save capture log for debugging
            if capture_log:
                capture_dir = Path(__file__).parent / "crawler_data" / "raw_responses"
                capture_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
                capture_path = capture_dir / f"ig_auth_capture_{timestamp}.json"
                capture_path.write_text(json.dumps(capture_log, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Saved capture log: {capture_path}")
                friendly_names = sorted({
                    item.get("payload", {}).get("fb_api_req_friendly_name")
                    for item in capture_log
                    if item.get("payload", {}).get("fb_api_req_friendly_name")
                })
                if friendly_names:
                    print("Captured friendly names:")
                    for name in friendly_names:
                        print(f"  - {name}")
            else:
                print(f"No XHR/Fetch requests captured. Total requests seen: {request_count}")
                print(f"Candidate requests seen: {candidate_count}")

            await context.close()

    print("Done. Config and .env updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
