#!/usr/bin/env python3
"""
Instagram single-post comments crawler.
"""

import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from config_loader import ConfigLoader


def extract_shortcode(post_url: str) -> Optional[str]:
    match = re.search(r"instagram\.com/(p|reel|tv)/([^/?#]+)/?", post_url)
    if not match:
        return None
    return match.group(2)


def shortcode_to_media_id(shortcode: str) -> Optional[str]:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    media_id = 0
    try:
        for char in shortcode:
            media_id = media_id * 64 + alphabet.index(char)
    except ValueError:
        return None
    return str(media_id)


def deep_get(data: Any, path: List[Any]) -> Any:
    cur = data
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
            continue
        if isinstance(cur, list) and isinstance(key, int) and 0 <= key < len(cur):
            cur = cur[key]
            continue
        return None
    return cur


def render_template(value: Any, variables: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        for key, replacement in variables.items():
            placeholder = "{" + key + "}"
            if placeholder in value:
                if replacement is None:
                    return None
                value = value.replace(placeholder, str(replacement))
        if re.search(r"\{[a-zA-Z0-9_]+\}", value):
            # unresolved placeholder remains
            return None
        return value
    if isinstance(value, dict):
        rendered = {}
        for k, v in value.items():
            rv = render_template(v, variables)
            if rv is not None:
                rendered[k] = rv
        return rendered
    if isinstance(value, list):
        rendered_list = []
        for item in value:
            rv = render_template(item, variables)
            if rv is not None:
                rendered_list.append(rv)
        return rendered_list
    return value


def pick_first_path(data: dict, paths: List[List[str]]) -> Any:
    for path in paths:
        value = deep_get(data, path)
        if value is not None:
            return value
    return None


def find_connection_in_data(payload: dict, suffixes: List[str]) -> Optional[dict]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        for suffix in suffixes:
            if key.endswith(suffix):
                return value
    return None


def parse_timestamp(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value).isoformat() + "Z"
    if isinstance(value, str):
        return value
    return None


def extract_gif_url(node: dict) -> Optional[str]:
    info = node.get("giphy_media_info")
    if not isinstance(info, dict):
        return None

    def pick_url(images: Any) -> Optional[str]:
        if not isinstance(images, dict):
            return None
        for key in ["original", "fixed_width", "fixed_height", "downsized", "preview_gif"]:
            entry = images.get(key)
            if isinstance(entry, dict):
                url = entry.get("url") or entry.get("mp4")
                if url:
                    return url
        for entry in images.values():
            if isinstance(entry, dict):
                url = entry.get("url") or entry.get("mp4")
                if url:
                    return url
        return None

    if isinstance(info.get("url"), str):
        return info.get("url")

    # Prefer first-party proxied URLs when present.
    proxy_images = info.get("first_party_cdn_proxied_images")
    url = pick_url(proxy_images)
    if url:
        return url

    # Fall back to giphy images.
    images = info.get("images")
    url = pick_url(images)
    if url:
        return url
    return None


class IGCrawler:
    def __init__(self, data_dir: str = "crawler_data", config_file: str = "config.json"):
        self.data_dir = Path(os.getenv("DATA_DIR", data_dir))
        (self.data_dir / "ig_comments").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "raw_responses").mkdir(parents=True, exist_ok=True)

        self.config_loader = ConfigLoader(config_file)
        self.config = self.config_loader.config.get("instagram", {})

        settings = self.config.get("settings", {})
        self.requests_per_minute = settings.get("requests_per_minute", 6)
        self.retry_attempts = settings.get("retry_attempts", 3)
        self.retry_delay = settings.get("retry_delay", 5)
        self.timeout = settings.get("timeout", 30)
        self.max_comments = settings.get("max_comments", 400)
        self.fetch_replies = settings.get("fetch_replies", True)
        self.resume_by_default = settings.get("resume_by_default", True)
        self.comments_first = settings.get("comments_first", 20)
        self.replies_first = settings.get("replies_first", 20)
        self.request_jitter_ratio = settings.get("request_jitter_ratio", 0.2)
        self.save_raw_mode = settings.get("save_raw_responses", "errors")
        self.raw_keep = settings.get("raw_responses_keep", 200)
        self.raw_max_mb = settings.get("raw_responses_max_mb", 100)
        self.page_retry_attempts = settings.get("page_retry_attempts", 2)
        self.page_retry_delay = settings.get("page_retry_delay", 3.0)

        self.session = requests.Session()
        self._last_request_ts = 0.0

        self.setup_session()

    def setup_session(self) -> None:
        headers = self.config.get("authentication", {}).get("headers", {})
        self.session.headers.update({
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        for key, value in headers.items():
            if value and not str(value).startswith("YOUR_"):
                self.session.headers[key] = value

        cookies = self.config.get("authentication", {}).get("cookies", {})
        for key, value in cookies.items():
            if value and not str(value).startswith("YOUR_"):
                self.session.cookies.set(key, value)

        proxy_settings = self.config_loader.get_proxy_settings()
        if proxy_settings:
            self.session.proxies = proxy_settings

    def rate_limit_check(self) -> None:
        if not self.requests_per_minute or self.requests_per_minute <= 0:
            return
        min_interval = 60.0 / float(self.requests_per_minute)
        now = time.time()
        elapsed = now - self._last_request_ts
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        # Add jitter to avoid fixed intervals
        jitter = random.uniform(0, min_interval * max(0.0, min(self.request_jitter_ratio, 1.0)))
        time.sleep(jitter)
        self._last_request_ts = time.time()

    def save_raw_response(self, label: str, url: str, params: dict, status: int, data: Any) -> None:
        mode = str(self.save_raw_mode or "errors").lower()
        if mode in {"none", "off", "false", "0"}:
            return
        if mode in {"errors", "error"} and status == 200:
            return
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{timestamp}_{label}.json"
        path = self.data_dir / "raw_responses" / filename
        payload = {
            "url": url,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": status,
            "params": params,
            "data": data,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.cleanup_raw_responses()

    def cleanup_raw_responses(self) -> None:
        raw_dir = self.data_dir / "raw_responses"
        if not raw_dir.exists():
            return
        files = sorted(raw_dir.glob("*_response.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if self.raw_keep is not None and self.raw_keep >= 0:
            for path in files[self.raw_keep:]:
                try:
                    path.unlink()
                except Exception:
                    pass
        if self.raw_max_mb is not None and self.raw_max_mb > 0:
            max_bytes = self.raw_max_mb * 1024 * 1024
            files = sorted(raw_dir.glob("*_response.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            total = 0
            for path in files:
                try:
                    total += path.stat().st_size
                except Exception:
                    continue
            if total > max_bytes:
                for path in reversed(files):
                    try:
                        size = path.stat().st_size
                    except Exception:
                        size = 0
                    try:
                        path.unlink()
                    except Exception:
                        pass
                    total -= size
                    if total <= max_bytes:
                        break

    def request_with_retry(self, method: str, url: str, params: dict, data: dict) -> Optional[dict]:
        for attempt in range(1, self.retry_attempts + 1):
            self.rate_limit_check()
            try:
                response = self.session.request(method, url, params=params, data=data, timeout=self.timeout)
            except Exception as exc:
                if attempt < self.retry_attempts:
                    print(f"Request error, retrying... ({exc})")
                    time.sleep(self.retry_delay)
                continue

            try:
                payload = response.json()
            except Exception:
                payload = {"error": response.text}

            self.save_raw_response("response", url, {"params": params, "data": data}, response.status_code, payload)

            if response.status_code == 200:
                return payload

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt < self.retry_attempts:
                    print(f"HTTP {response.status_code}, retrying...")
                    time.sleep(self.retry_delay * attempt)
                    continue

            return None

        return None

    def build_request(self, endpoint: dict, variables: dict) -> Tuple[str, str, dict, dict]:
        url = endpoint.get("url")
        if not url:
            raise ValueError("Endpoint URL missing")

        method = endpoint.get("method", "POST").upper()
        params = {}
        data = {}

        endpoint_type = endpoint.get("type", "graphql")
        if endpoint_type == "graphql":
            if endpoint.get("doc_id"):
                data["doc_id"] = endpoint.get("doc_id")
            if endpoint.get("query_hash"):
                data["query_hash"] = endpoint.get("query_hash")
            if endpoint.get("params"):
                data.update(endpoint.get("params"))
            if variables:
                data["variables"] = json.dumps(variables, separators=(",", ":"), ensure_ascii=False)
        else:
            if endpoint.get("params"):
                params.update(endpoint.get("params"))
            if variables:
                data.update(variables)

        if method == "GET":
            params.update(data)
            data = {}

        return method, url, params, data

    def resolve_media_id(self, shortcode: str) -> Tuple[Optional[str], dict]:
        endpoint = self.config.get("endpoints", {}).get("post_by_shortcode")
        base_media_id = shortcode_to_media_id(shortcode)
        if not endpoint or str(endpoint.get("doc_id", "")).startswith("YOUR_"):
            print("post_by_shortcode endpoint not configured. Falling back to shortcode decode/HTML.")
            media_id = base_media_id or self.resolve_media_id_from_html(shortcode)
            return media_id, {"media_id": media_id}

        variables_template = endpoint.get("variables", {})
        variables = render_template(variables_template, {
            "shortcode": shortcode,
            "media_id": None,
            "cursor": None,
            "comment_id": None,
        })

        method, url, params, data = self.build_request(endpoint, variables)
        payload = self.request_with_retry(method, url, params, data)
        if not payload:
            print("post_by_shortcode request failed. Falling back to shortcode decode/HTML.")
            return None, {}

        media_id = pick_first_path(payload, [
            ["data", "xdt_shortcode_media", "id"],
            ["data", "shortcode_media", "id"],
            ["data", "xdt_shortcode_media", "pk"],
            ["data", "shortcode_media", "pk"],
            ["data", "media", "id"],
            ["data", "media", "pk"],
        ])

        post_info = {
            "media_id": media_id,
            "owner_id": pick_first_path(payload, [
                ["data", "xdt_shortcode_media", "owner", "id"],
                ["data", "shortcode_media", "owner", "id"],
            ]),
            "caption": pick_first_path(payload, [
                ["data", "xdt_shortcode_media", "edge_media_to_caption", "edges", 0, "node", "text"],
                ["data", "shortcode_media", "edge_media_to_caption", "edges", 0, "node", "text"],
            ]),
            "created_at": parse_timestamp(pick_first_path(payload, [
                ["data", "xdt_shortcode_media", "taken_at_timestamp"],
                ["data", "shortcode_media", "taken_at_timestamp"],
            ])),
        }

        resolved_media_id = str(media_id) if media_id else None
        if not resolved_media_id:
            resolved_media_id = base_media_id
        return resolved_media_id, post_info

    def resolve_media_id_from_html(self, shortcode: str) -> Optional[str]:
        url = f"https://www.instagram.com/p/{shortcode}/"
        try:
            response = self.session.get(url, timeout=self.timeout)
        except Exception:
            return None
        if response.status_code != 200:
            return None
        text = response.text
        patterns = [
            r'"media_id":"(\\d+)"',
            rf'"id":"(\\d+)","shortcode":"{re.escape(shortcode)}"',
            rf'"pk":"(\\d+)","shortcode":"{re.escape(shortcode)}"',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def extract_comment_connection(self, payload: dict) -> Tuple[List[dict], dict, Optional[int]]:
        candidates = [
            ["data", "xdt_api__v1__media__media_id__comments__connection"],
            ["data", "xdt_shortcode_media", "edge_media_to_parent_comment"],
            ["data", "shortcode_media", "edge_media_to_parent_comment"],
            ["data", "xdt_shortcode_media", "edge_media_to_comment"],
            ["data", "shortcode_media", "edge_media_to_comment"],
        ]
        for path in candidates:
            connection = deep_get(payload, path)
            if connection and isinstance(connection, dict):
                edges = connection.get("edges", [])
                page_info = connection.get("page_info", {})
                count = connection.get("count")
                return edges, page_info, count
        connection = find_connection_in_data(payload, ["__comments__connection"])
        if connection and isinstance(connection, dict):
            return connection.get("edges", []), connection.get("page_info", {}), connection.get("count")
        return [], {}, None

    def extract_reply_connection(self, payload: dict) -> Tuple[List[dict], dict, Optional[int]]:
        candidates = [
            ["data", "comment", "edge_threaded_comments"],
            ["data", "comment", "edge_media_to_parent_comment"],
            ["data", "comment", "edge_media_to_comment"],
        ]
        for path in candidates:
            connection = deep_get(payload, path)
            if connection and isinstance(connection, dict):
                edges = connection.get("edges", [])
                page_info = connection.get("page_info", {})
                count = connection.get("count")
                return edges, page_info, count
        connection = find_connection_in_data(payload, ["__replies__connection", "__comments__replies__connection"])
        if connection and isinstance(connection, dict):
            return connection.get("edges", []), connection.get("page_info", {}), connection.get("count")
        connection = find_connection_in_data(payload, ["__child_comments__connection"])
        if connection and isinstance(connection, dict):
            return connection.get("edges", []), connection.get("page_info", {}), connection.get("count")
        return self.extract_comment_connection(payload)

    def parse_user(self, node: dict) -> dict:
        user = node.get("owner") or node.get("user") or {}
        return {
            "id": user.get("id") or user.get("pk"),
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "is_verified": user.get("is_verified"),
        }

    def parse_comment_node(self, node: dict, post_owner_id: Optional[str]) -> dict:
        comment_id = node.get("id") or node.get("pk")
        created_at = parse_timestamp(node.get("created_at") or node.get("created_at_utc") or node.get("created_at_time"))
        like_count = node.get("like_count")
        if like_count is None:
            like_count = node.get("comment_like_count")
        if like_count is None:
            like_count = deep_get(node, ["edge_liked_by", "count"])

        user = self.parse_user(node)
        is_author = post_owner_id and user.get("id") and str(user.get("id")) == str(post_owner_id)

        reply_count = None
        if isinstance(node.get("edge_threaded_comments"), dict):
            reply_count = node.get("edge_threaded_comments", {}).get("count")
        if reply_count is None:
            reply_count = node.get("child_comment_count")

        return {
            "id": str(comment_id) if comment_id is not None else None,
            "text": node.get("text") or node.get("comment_text"),
            "created_at": created_at,
            "like_count": like_count,
            "gif_url": extract_gif_url(node),
            "user": user,
            "is_author": bool(is_author),
            "reply_count": reply_count or 0,
            "replies": [],
        }

    def extract_replies_from_node(self, node: dict) -> Tuple[List[dict], dict]:
        if not isinstance(node.get("edge_threaded_comments"), dict):
            return [], {}
        connection = node.get("edge_threaded_comments", {})
        edges = connection.get("edges", [])
        page_info = connection.get("page_info", {})
        return edges, page_info

    def fetch_comments_page(self, shortcode: str, media_id: Optional[str], cursor: Optional[str]) -> Optional[dict]:
        endpoint = self.config.get("endpoints", {}).get("comments")
        if not endpoint or str(endpoint.get("doc_id", "")).startswith("YOUR_"):
            print("Comments endpoint not configured.")
            return None

        variables_template = endpoint.get("variables", {})
        variables = render_template(variables_template, {
            "shortcode": shortcode,
            "media_id": media_id,
            "cursor": cursor,
            "comment_id": None,
        })
        if isinstance(variables, dict) and "first" in variables and self.comments_first:
            variables["first"] = self.comments_first

        method, url, params, data = self.build_request(endpoint, variables)
        return self.request_with_retry(method, url, params, data)

    def fetch_comment_replies(self, comment_id: str, cursor: Optional[str], media_id: Optional[str]) -> Optional[dict]:
        endpoint = self.config.get("endpoints", {}).get("comment_replies")
        if not endpoint or str(endpoint.get("doc_id", "")).startswith("YOUR_"):
            return None

        variables_template = endpoint.get("variables", {})
        variables = render_template(variables_template, {
            "shortcode": None,
            "media_id": media_id,
            "cursor": cursor,
            "comment_id": comment_id,
        })
        if isinstance(variables, dict) and "first" in variables and self.replies_first:
            variables["first"] = self.replies_first

        method, url, params, data = self.build_request(endpoint, variables)
        return self.request_with_retry(method, url, params, data)

    def crawl_post_comments(self, post_url: str, max_comments: Optional[int] = None, resume: Optional[bool] = None) -> dict:
        print(f"Start: {post_url}")
        shortcode = extract_shortcode(post_url)
        if not shortcode:
            raise ValueError("Invalid Instagram post URL")

        print(f"Shortcode: {shortcode}")
        max_comments = max_comments if max_comments is not None else self.max_comments
        resume = self.resume_by_default if resume is None else resume

        resume_state = None
        if resume:
            resume_state = self.load_resume_state(shortcode)
            if resume_state and resume_state.get("complete"):
                print("Resume state is marked complete. Starting fresh.")
                resume_state = None
            elif resume_state:
                print("Resuming from previous state.")
            else:
                print("No resume state found. Starting fresh.")

        if resume_state:
            post_info = resume_state.get("post", {})
            media_id = post_info.get("media_id") or shortcode_to_media_id(shortcode)
        else:
            media_id, post_info = self.resolve_media_id(shortcode)
            post_info.update({"url": post_url, "shortcode": shortcode, "media_id": media_id})
        print(f"Media ID: {media_id}")

        all_comments: List[dict] = []
        seen_comment_ids = set()
        cursor = None
        last_cursor = None
        page = 0
        prev_cursor = None
        backtrack_used = False
        total_count = None
        interrupted = False
        stop_reason = None

        if resume_state:
            all_comments = resume_state.get("comments", [])
            seen_comment_ids = set(resume_state.get("seen_comment_ids", []))
            cursor = resume_state.get("cursor")
            last_cursor = resume_state.get("last_cursor")
            page = resume_state.get("pages", 0)
            total_count = resume_state.get("expected_comment_count")

        start_time = time.monotonic()
        try:
            while True:
                page_start = time.monotonic()
                current_cursor = cursor
                payload = None
                for attempt in range(self.page_retry_attempts + 1):
                    payload = self.fetch_comments_page(shortcode, media_id, current_cursor)
                    if payload:
                        break
                    if attempt < self.page_retry_attempts:
                        delay = self.page_retry_delay * (attempt + 1)
                        print(f"Page fetch failed, retrying in {delay:.1f}s...")
                        time.sleep(delay)

                if not payload:
                    if prev_cursor and prev_cursor != current_cursor and not backtrack_used:
                        print("Page fetch failed. Backtracking to previous cursor and retrying...")
                        cursor = prev_cursor
                        backtrack_used = True
                        continue
                    print("Stop: no payload")
                    stop_reason = "no_payload"
                    break

                backtrack_used = False
                page += 1

                edges, page_info, count = self.extract_comment_connection(payload)
                if total_count is None:
                    total_count = count
                page_elapsed = time.monotonic() - page_start
                print(f"Page {page}: {len(edges)} comments, {len(seen_comment_ids)} total, {page_elapsed:.2f}s")

                for edge in edges:
                    node = edge.get("node") if isinstance(edge, dict) else None
                    if not node:
                        continue

                    parsed = self.parse_comment_node(node, post_info.get("owner_id"))
                    parsed_id = parsed.get("id")
                    if parsed_id in seen_comment_ids:
                        continue
                    seen_comment_ids.add(parsed_id)

                    reply_count = parsed.get("reply_count") or 0
                    replies_endpoint = self.config.get("endpoints", {}).get("comment_replies", {})
                    replies_enabled = self.fetch_replies and bool(replies_endpoint) and not str(replies_endpoint.get("doc_id", "")).startswith("YOUR_")

                    # Inline replies if present
                    reply_edges, reply_page = self.extract_replies_from_node(node)
                    if reply_edges:
                        for reply_edge in reply_edges:
                            reply_node = reply_edge.get("node") if isinstance(reply_edge, dict) else None
                            if not reply_node:
                                continue
                            reply = self.parse_comment_node(reply_node, post_info.get("owner_id"))
                            reply["parent_id"] = parsed_id
                            reply_id = reply.get("id")
                            if reply_id and reply_id not in seen_comment_ids:
                                seen_comment_ids.add(reply_id)
                                parsed["replies"].append(reply)

                    # Fetch replies if needed
                    if replies_enabled and parsed_id and (reply_count > len(parsed["replies"]) or reply_page.get("has_next_page")):
                        reply_cursor = reply_page.get("end_cursor") if reply_page.get("has_next_page") else None
                        last_reply_cursor = None
                        while True:
                            reply_payload = self.fetch_comment_replies(parsed_id, reply_cursor, media_id)
                            if not reply_payload:
                                break
                            reply_edges2, reply_page2, _ = self.extract_reply_connection(reply_payload)
                            for reply_edge in reply_edges2:
                                reply_node = reply_edge.get("node") if isinstance(reply_edge, dict) else None
                                if not reply_node:
                                    continue
                                reply = self.parse_comment_node(reply_node, post_info.get("owner_id"))
                                reply["parent_id"] = parsed_id
                                reply_id = reply.get("id")
                                if reply_id and reply_id not in seen_comment_ids:
                                    seen_comment_ids.add(reply_id)
                                    parsed["replies"].append(reply)
                            if not reply_page2.get("has_next_page"):
                                break
                            reply_cursor = reply_page2.get("end_cursor")
                            if not reply_cursor or reply_cursor == last_reply_cursor:
                                break
                            last_reply_cursor = reply_cursor

                    all_comments.append(parsed)

                    if max_comments and len(seen_comment_ids) >= max_comments:
                        print("Stop: max comments reached")
                        stop_reason = "max_reached"
                        raise StopIteration

                if not page_info.get("has_next_page"):
                    print("Stop: no more pages")
                    stop_reason = "no_more_pages"
                    break
                prev_cursor = current_cursor
                cursor = page_info.get("end_cursor")
                if not cursor:
                    print("Stop: missing cursor")
                    stop_reason = "missing_cursor"
                    break
                if cursor == last_cursor:
                    print("Stop: cursor stalled")
                    stop_reason = "cursor_stalled"
                    break
                last_cursor = cursor

                self.save_resume_state(
                    shortcode=shortcode,
                    post_info=post_info,
                    comments=all_comments,
                    seen_ids=seen_comment_ids,
                    cursor=cursor,
                    last_cursor=last_cursor,
                    page=page,
                    expected_count=total_count,
                    stop_reason=stop_reason,
                    complete=False,
                )
        except KeyboardInterrupt:
            interrupted = True
            stop_reason = "interrupted"
            print("Stop: interrupted")
        except StopIteration:
            pass

        result = {
            "post": post_info,
            "comment_count": len(all_comments),
            "expected_comment_count": total_count,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "comments": all_comments,
            "pages": page,
            "stop_reason": stop_reason,
        }

        output_path = self.save_output(shortcode, result)
        result["output_path"] = str(output_path)
        print(f"Saved output: {output_path}")
        total_elapsed = time.monotonic() - start_time
        print(f"Total time: {total_elapsed:.2f}s")

        complete = (stop_reason == "no_more_pages")
        if complete:
            self.clear_resume_state(shortcode)
        else:
            self.save_resume_state(
                shortcode=shortcode,
                post_info=post_info,
                comments=all_comments,
                seen_ids=seen_comment_ids,
                cursor=cursor,
                last_cursor=last_cursor,
                page=page,
                expected_count=total_count,
                stop_reason=stop_reason,
                complete=False,
            )
        return result

    def save_output(self, shortcode: str, data: dict) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{shortcode}_{timestamp}.json"
        path = self.data_dir / "ig_comments" / filename
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def resume_path(self, shortcode: str) -> Path:
        return self.data_dir / "ig_comments" / f"{shortcode}_resume.json"

    def load_resume_state(self, shortcode: str) -> Optional[dict]:
        path = self.resume_path(shortcode)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def save_resume_state(
        self,
        shortcode: str,
        post_info: dict,
        comments: List[dict],
        seen_ids: set,
        cursor: Optional[str],
        last_cursor: Optional[str],
        page: int,
        expected_count: Optional[int],
        stop_reason: Optional[str],
        complete: bool,
    ) -> None:
        state = {
            "post": post_info,
            "comment_count": len(comments),
            "comments": comments,
            "seen_comment_ids": list(seen_ids),
            "cursor": cursor,
            "last_cursor": last_cursor,
            "pages": page,
            "expected_comment_count": expected_count,
            "stop_reason": stop_reason,
            "complete": complete,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        path = self.resume_path(shortcode)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear_resume_state(self, shortcode: str) -> None:
        path = self.resume_path(shortcode)
        if path.exists():
            path.unlink()
