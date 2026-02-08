#!/usr/bin/env python3
"""
Config loader for Instagram crawler.
Priority: .env > config.json > defaults.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class ConfigLoader:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self):
        config = {
            "instagram": {
                "authentication": {
                    "cookies": {
                        "sessionid": "YOUR_SESSIONID_HERE",
                        "csrftoken": "YOUR_CSRFTOKEN_HERE",
                        "ds_user_id": "YOUR_DS_USER_ID_HERE",
                        "rur": "YOUR_RUR_HERE",
                    },
                    "headers": {
                        "X-CSRFToken": "YOUR_X_CSRF_TOKEN_HERE",
                        "X-IG-App-ID": "YOUR_X_IG_APP_ID_HERE",
                        "X-IG-WWW-Claim": "YOUR_X_IG_WWW_CLAIM_HERE",
                        "X-ASBD-ID": "YOUR_X_ASBD_ID_HERE",
                        "Referer": "https://www.instagram.com/",
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                    },
                },
                "endpoints": {
                    "post_by_shortcode": {
                        "type": "graphql",
                        "method": "POST",
                        "url": "https://www.instagram.com/api/graphql",
                        "doc_id": "YOUR_DOC_ID_HERE",
                        "variables": {
                            "shortcode": "{shortcode}"
                        },
                    },
                    "comments": {
                        "type": "graphql",
                        "method": "POST",
                        "url": "https://www.instagram.com/api/graphql",
                        "doc_id": "YOUR_DOC_ID_HERE",
                        "variables": {
                            "shortcode": "{shortcode}",
                            "first": 50,
                            "after": "{cursor}"
                        },
                    },
                    "comment_replies": {
                        "type": "graphql",
                        "method": "POST",
                        "url": "https://www.instagram.com/api/graphql",
                        "doc_id": "YOUR_DOC_ID_HERE",
                        "variables": {
                            "comment_id": "{comment_id}",
                            "first": 50,
                            "after": "{cursor}"
                        },
                    },
                },
                "settings": {
                    "requests_per_minute": 8,
                    "retry_attempts": 3,
                    "retry_delay": 5,
                    "timeout": 30,
                    "max_comments": 400,
                    "fetch_replies": True,
                    "resume_by_default": True,
                    "comments_first": 20,
                    "replies_first": 20,
                    "request_jitter_ratio": 0.2,
                    "save_raw_responses": "errors",
                    "raw_responses_keep": 200,
                    "raw_responses_max_mb": 100,
                },
                "proxy": {
                    "http": None,
                    "https": None,
                },
            }
        }

        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as file:
                json_config = json.load(file)
                self._deep_update(config, json_config)

        ig = config["instagram"]

        # Cookie overrides
        if os.getenv("IG_SESSIONID"):
            ig["authentication"]["cookies"]["sessionid"] = os.getenv("IG_SESSIONID")
        if os.getenv("IG_CSRFTOKEN"):
            ig["authentication"]["cookies"]["csrftoken"] = os.getenv("IG_CSRFTOKEN")
        if os.getenv("IG_DS_USER_ID"):
            ig["authentication"]["cookies"]["ds_user_id"] = os.getenv("IG_DS_USER_ID")
        if os.getenv("IG_RUR"):
            ig["authentication"]["cookies"]["rur"] = os.getenv("IG_RUR")

        # Header overrides
        if os.getenv("IG_X_CSRF_TOKEN"):
            ig["authentication"]["headers"]["X-CSRFToken"] = os.getenv("IG_X_CSRF_TOKEN")
        if os.getenv("IG_X_IG_APP_ID"):
            ig["authentication"]["headers"]["X-IG-App-ID"] = os.getenv("IG_X_IG_APP_ID")
        if os.getenv("IG_X_IG_WWW_CLAIM"):
            ig["authentication"]["headers"]["X-IG-WWW-Claim"] = os.getenv("IG_X_IG_WWW_CLAIM")
        if os.getenv("IG_X_ASBD_ID"):
            ig["authentication"]["headers"]["X-ASBD-ID"] = os.getenv("IG_X_ASBD_ID")
        if os.getenv("IG_USER_AGENT"):
            ig["authentication"]["headers"]["User-Agent"] = os.getenv("IG_USER_AGENT")
        if os.getenv("IG_REFERER"):
            ig["authentication"]["headers"]["Referer"] = os.getenv("IG_REFERER")

        # Proxy overrides
        if os.getenv("HTTP_PROXY"):
            ig["proxy"]["http"] = os.getenv("HTTP_PROXY")
        if os.getenv("HTTPS_PROXY"):
            ig["proxy"]["https"] = os.getenv("HTTPS_PROXY")

        # Settings overrides
        if os.getenv("IG_REQUESTS_PER_MINUTE"):
            ig["settings"]["requests_per_minute"] = int(os.getenv("IG_REQUESTS_PER_MINUTE"))
        if os.getenv("IG_RETRY_ATTEMPTS"):
            ig["settings"]["retry_attempts"] = int(os.getenv("IG_RETRY_ATTEMPTS"))
        if os.getenv("IG_RETRY_DELAY"):
            ig["settings"]["retry_delay"] = int(os.getenv("IG_RETRY_DELAY"))
        if os.getenv("IG_TIMEOUT"):
            ig["settings"]["timeout"] = int(os.getenv("IG_TIMEOUT"))
        if os.getenv("IG_MAX_COMMENTS"):
            ig["settings"]["max_comments"] = int(os.getenv("IG_MAX_COMMENTS"))
        if os.getenv("IG_FETCH_REPLIES"):
            ig["settings"]["fetch_replies"] = os.getenv("IG_FETCH_REPLIES").lower() in {"1", "true", "yes", "on"}
        if os.getenv("IG_RESUME_BY_DEFAULT"):
            ig["settings"]["resume_by_default"] = os.getenv("IG_RESUME_BY_DEFAULT").lower() in {"1", "true", "yes", "on"}
        if os.getenv("IG_COMMENTS_FIRST"):
            ig["settings"]["comments_first"] = int(os.getenv("IG_COMMENTS_FIRST"))
        if os.getenv("IG_REPLIES_FIRST"):
            ig["settings"]["replies_first"] = int(os.getenv("IG_REPLIES_FIRST"))
        if os.getenv("IG_JITTER_RATIO"):
            ig["settings"]["request_jitter_ratio"] = float(os.getenv("IG_JITTER_RATIO"))
        if os.getenv("IG_SAVE_RAW_RESPONSES"):
            ig["settings"]["save_raw_responses"] = os.getenv("IG_SAVE_RAW_RESPONSES").strip().lower()
        if os.getenv("IG_RAW_RESPONSES_KEEP"):
            ig["settings"]["raw_responses_keep"] = int(os.getenv("IG_RAW_RESPONSES_KEEP"))
        if os.getenv("IG_RAW_RESPONSES_MAX_MB"):
            ig["settings"]["raw_responses_max_mb"] = int(os.getenv("IG_RAW_RESPONSES_MAX_MB"))

        return config

    def _deep_update(self, base, update):
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def get(self, key_path, default=None):
        keys = key_path.split(".")
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def save_to_json(self, output_file=None):
        output_file = output_file or self.config_file
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(self.config, file, ensure_ascii=False, indent=2)
        print(f"Config saved: {output_file}")

    def get_proxy_settings(self):
        proxy = self.config.get("instagram", {}).get("proxy", {})
        if proxy.get("http") or proxy.get("https"):
            return {
                "http": proxy.get("http"),
                "https": proxy.get("https"),
            }
        return None

    def validate(self):
        ig = self.config.get("instagram", {})
        cookies = ig.get("authentication", {}).get("cookies", {})
        required = ["sessionid", "csrftoken", "ds_user_id"]
        missing = [name for name in required if not cookies.get(name) or str(cookies.get(name)).startswith("YOUR_")]
        if missing:
            print("Missing required cookies: " + ", ".join(missing))
            return False
        return True


def main():
    loader = ConfigLoader()
    ig = loader.config.get("instagram", {})
    print("Loaded Instagram config")
    print("Cookies:")
    for key, value in ig.get("authentication", {}).get("cookies", {}).items():
        preview = str(value)[:8] + "..." if value else "<empty>"
        print(f"  {key}: {preview}")
    print("Headers:")
    for key, value in ig.get("authentication", {}).get("headers", {}).items():
        preview = str(value)[:16] + "..." if value else "<empty>"
        print(f"  {key}: {preview}")


if __name__ == "__main__":
    main()
