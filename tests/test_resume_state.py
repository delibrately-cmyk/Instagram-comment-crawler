import json


def test_resume_state_save_load_and_clear(crawler):
    shortcode = "TESTCODE"
    post_info = {"shortcode": shortcode, "media_id": "12345"}
    comments = [{"id": "1"}, {"id": "2"}]

    crawler.save_resume_state(
        shortcode=shortcode,
        post_info=post_info,
        comments=comments,
        seen_ids={"1", "2"},
        cursor="cursor-1",
        last_cursor="cursor-0",
        page=2,
        expected_count=100,
        stop_reason="no_payload",
        complete=False,
    )

    loaded = crawler.load_resume_state(shortcode)
    assert loaded is not None
    assert loaded["post"]["media_id"] == "12345"
    assert loaded["comment_count"] == 2
    assert set(loaded["seen_comment_ids"]) == {"1", "2"}
    assert loaded["cursor"] == "cursor-1"

    crawler.clear_resume_state(shortcode)
    assert crawler.load_resume_state(shortcode) is None


def test_resume_state_load_corrupted_file_returns_none(crawler):
    shortcode = "BROKEN"
    path = crawler.resume_path(shortcode)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    assert crawler.load_resume_state(shortcode) is None


def test_resume_state_file_contains_expected_keys(crawler):
    shortcode = "KEYCHECK"
    crawler.save_resume_state(
        shortcode=shortcode,
        post_info={"shortcode": shortcode},
        comments=[],
        seen_ids=set(),
        cursor=None,
        last_cursor=None,
        page=0,
        expected_count=None,
        stop_reason=None,
        complete=False,
    )

    raw = json.loads(crawler.resume_path(shortcode).read_text(encoding="utf-8"))
    required_keys = {
        "post",
        "comment_count",
        "comments",
        "seen_comment_ids",
        "cursor",
        "last_cursor",
        "pages",
        "expected_comment_count",
        "stop_reason",
        "complete",
        "updated_at",
    }
    assert required_keys.issubset(raw.keys())
