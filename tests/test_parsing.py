from ig_crawler import parse_timestamp


def test_parse_comment_node_uses_like_fallback_and_author_check(crawler):
    node = {
        "id": 123,
        "comment_text": "hello",
        "created_at": 1700000000,
        "edge_liked_by": {"count": 7},
        "owner": {
            "id": "42",
            "username": "tester",
            "full_name": "Test User",
            "is_verified": True,
        },
        "child_comment_count": 2,
    }

    parsed = crawler.parse_comment_node(node, post_owner_id="42")
    assert parsed["id"] == "123"
    assert parsed["text"] == "hello"
    assert parsed["created_at"] == parse_timestamp(1700000000)
    assert parsed["like_count"] == 7
    assert parsed["is_author"] is True
    assert parsed["reply_count"] == 2
    assert parsed["replies"] == []


def test_parse_comment_node_prefers_comment_like_count_and_threaded_count(crawler):
    node = {
        "pk": "888",
        "text": "inline text",
        "created_at_utc": "2025-01-01T00:00:00Z",
        "comment_like_count": 3,
        "user": {"pk": "100", "username": "abc", "is_verified": False},
        "edge_threaded_comments": {"count": 5, "edges": []},
    }

    parsed = crawler.parse_comment_node(node, post_owner_id=None)
    assert parsed["id"] == "888"
    assert parsed["text"] == "inline text"
    assert parsed["created_at"] == "2025-01-01T00:00:00Z"
    assert parsed["like_count"] == 3
    assert parsed["is_author"] is False
    assert parsed["reply_count"] == 5


def test_extract_comment_connection_primary_path(crawler):
    payload = {
        "data": {
            "xdt_shortcode_media": {
                "edge_media_to_parent_comment": {
                    "edges": [{"node": {"id": "1"}}],
                    "page_info": {"has_next_page": True, "end_cursor": "abc"},
                    "count": 11,
                }
            }
        }
    }

    edges, page_info, count = crawler.extract_comment_connection(payload)
    assert len(edges) == 1
    assert page_info["has_next_page"] is True
    assert count == 11


def test_extract_comment_connection_suffix_fallback(crawler):
    payload = {
        "data": {
            "some_dynamic_key__comments__connection": {
                "edges": [{"node": {"id": "2"}}],
                "page_info": {"has_next_page": False},
                "count": 1,
            }
        }
    }

    edges, page_info, count = crawler.extract_comment_connection(payload)
    assert len(edges) == 1
    assert page_info["has_next_page"] is False
    assert count == 1


def test_extract_reply_connection_primary_path(crawler):
    payload = {
        "data": {
            "comment": {
                "edge_threaded_comments": {
                    "edges": [{"node": {"id": "r1"}}],
                    "page_info": {"has_next_page": False},
                    "count": 1,
                }
            }
        }
    }

    edges, page_info, count = crawler.extract_reply_connection(payload)
    assert len(edges) == 1
    assert page_info["has_next_page"] is False
    assert count == 1


def test_extract_reply_connection_child_comments_suffix_fallback(crawler):
    payload = {
        "data": {
            "dynamic_key__child_comments__connection": {
                "edges": [{"node": {"id": "r2"}}],
                "page_info": {"has_next_page": True},
                "count": 6,
            }
        }
    }

    edges, page_info, count = crawler.extract_reply_connection(payload)
    assert len(edges) == 1
    assert page_info["has_next_page"] is True
    assert count == 6


def test_extract_reply_connection_falls_back_to_comment_connection(crawler):
    payload = {
        "data": {
            "shortcode_media": {
                "edge_media_to_comment": {
                    "edges": [{"node": {"id": "fallback"}}],
                    "page_info": {"has_next_page": False},
                    "count": 3,
                }
            }
        }
    }

    edges, page_info, count = crawler.extract_reply_connection(payload)
    assert len(edges) == 1
    assert page_info["has_next_page"] is False
    assert count == 3
