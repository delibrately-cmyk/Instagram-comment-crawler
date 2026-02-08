import sys

import run_ig_crawler


def test_cli_main_with_resume_and_fetch_replies(monkeypatch, capsys):
    calls = {}

    class DummyCrawler:
        def __init__(self, config_file):
            calls["config_file"] = config_file
            self.fetch_replies = False

        def crawl_post_comments(self, post_url, max_comments=None, resume=None):
            calls["post_url"] = post_url
            calls["max_comments"] = max_comments
            calls["resume"] = resume
            calls["fetch_replies"] = self.fetch_replies
            return {"output_path": "out.json", "comment_count": 3}

    monkeypatch.setattr(run_ig_crawler, "IGCrawler", DummyCrawler)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ig_crawler.py",
            "--post-url",
            "https://www.instagram.com/p/ABC123/",
            "--config",
            "config.example.json",
            "--max-comments",
            "12",
            "--resume",
            "--fetch-replies",
        ],
    )

    exit_code = run_ig_crawler.main()
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert calls["config_file"] == "config.example.json"
    assert calls["post_url"] == "https://www.instagram.com/p/ABC123/"
    assert calls["max_comments"] == 12
    assert calls["resume"] is True
    assert calls["fetch_replies"] is True
    assert "Saved: out.json" in captured
    assert "Comments: 3" in captured


def test_cli_main_with_no_resume_and_no_replies(monkeypatch):
    calls = {}

    class DummyCrawler:
        def __init__(self, config_file):
            self.fetch_replies = True

        def crawl_post_comments(self, post_url, max_comments=None, resume=None):
            calls["resume"] = resume
            calls["fetch_replies"] = self.fetch_replies
            return {"output_path": "out2.json", "comment_count": 1}

    monkeypatch.setattr(run_ig_crawler, "IGCrawler", DummyCrawler)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ig_crawler.py",
            "--post-url",
            "https://www.instagram.com/p/ABC123/",
            "--no-resume",
            "--no-replies",
        ],
    )

    exit_code = run_ig_crawler.main()
    assert exit_code == 0
    assert calls["resume"] is False
    assert calls["fetch_replies"] is False
