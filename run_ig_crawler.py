#!/usr/bin/env python3
"""
CLI entry for Instagram crawler.
"""

import argparse

from ig_crawler import IGCrawler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-url", required=True, help="Instagram post URL")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--max-comments", type=int, default=None, help="Stop after N unique comments")
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument("--resume", action="store_true", help="Resume from previous state")
    resume_group.add_argument("--no-resume", action="store_true", help="Disable resume")
    replies_group = parser.add_mutually_exclusive_group()
    replies_group.add_argument("--fetch-replies", action="store_true", help="Force enable replies")
    replies_group.add_argument("--no-replies", action="store_true", help="Disable replies")
    args = parser.parse_args()

    crawler = IGCrawler(config_file=args.config)
    resume = None
    if args.resume:
        resume = True
    if args.no_resume:
        resume = False

    if args.fetch_replies:
        crawler.fetch_replies = True
    if args.no_replies:
        crawler.fetch_replies = False

    result = crawler.crawl_post_comments(
        args.post_url,
        max_comments=args.max_comments,
        resume=resume,
    )

    print(f"Saved: {result.get('output_path')}")
    print(f"Comments: {result.get('comment_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
