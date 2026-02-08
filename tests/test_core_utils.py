from ig_crawler import extract_shortcode, parse_timestamp, render_template, shortcode_to_media_id


def test_extract_shortcode_supports_post_reel_tv():
    assert extract_shortcode("https://www.instagram.com/p/ABC123xyz/") == "ABC123xyz"
    assert extract_shortcode("https://www.instagram.com/reel/REEL9_-/") == "REEL9_-"
    assert extract_shortcode("https://www.instagram.com/tv/TVcode99/?utm_source=test") == "TVcode99"


def test_extract_shortcode_invalid_url_returns_none():
    assert extract_shortcode("https://www.instagram.com/explore/") is None
    assert extract_shortcode("https://example.com/p/ABC123/") is None


def test_shortcode_to_media_id_known_value():
    assert shortcode_to_media_id("ABC123xyz") == "4593314372787"


def test_shortcode_to_media_id_invalid_character_returns_none():
    assert shortcode_to_media_id("BAD:CODE") is None


def test_render_template_replaces_simple_string():
    value = render_template("{shortcode}", {"shortcode": "POST_SHORTCODE"})
    assert value == "POST_SHORTCODE"


def test_render_template_drops_unresolved_values_in_dict_and_list():
    template = {
        "shortcode": "{shortcode}",
        "cursor": "{cursor}",
        "drop_missing": "{missing_key}",
        "items": ["ok", "{media_id}", "{unknown}"],
        "nested": {"comment_id": "{comment_id}", "keep": "x"},
    }
    rendered = render_template(
        template,
        {
            "shortcode": "abc",
            "cursor": "c1",
            "media_id": 42,
            "comment_id": "1001",
        },
    )

    assert rendered == {
        "shortcode": "abc",
        "cursor": "c1",
        "items": ["ok", "42"],
        "nested": {"comment_id": "1001", "keep": "x"},
    }


def test_render_template_none_replacement_returns_none():
    assert render_template("{cursor}", {"cursor": None}) is None


def test_parse_timestamp_from_unix_seconds():
    assert parse_timestamp(1700000000) == "2023-11-14T22:13:20Z"
