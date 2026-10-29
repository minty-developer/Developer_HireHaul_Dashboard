
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import rss_collector


class TestRSSCollector(unittest.TestCase):

    def test_empty_title_is_rejected(self):
        entry = {
            "title": "   ",
            "link": "https://example.com/post",
        }

        result = rss_collector.normalize_post(entry, "Test Blog")

        self.assertIsNone(result)

    def test_empty_link_is_rejected(self):
        entry = {
            "title": "테스트 게시글",
            "link": "",
        }

        result = rss_collector.normalize_post(entry, "Test Blog")

        self.assertIsNone(result)

    def test_post_data_is_normalized(self):
        entry = {
            "title": " 테스트 게시글 ",
            "link": " https://example.com/post ",
            "published": "2026-10-28T10:00:00+00:00",
        }

        result = rss_collector.normalize_post(entry, "Test Blog")

        self.assertEqual(result["title"], "테스트 게시글")
        self.assertEqual(result["link"], "https://example.com/post")
        self.assertEqual(result["blog"], "Test Blog")
        self.assertEqual(
            result["published"],
            "2026-10-28T10:00:00+00:00",
        )

    def test_posts_are_sorted_newest_first(self):
        posts = [
            {"title": "오래된 글", "published": "2026-10-20T00:00:00+00:00"},
            {"title": "최신 글", "published": "2026-10-29T00:00:00+00:00"},
            {"title": "날짜 없는 글", "published": None},
        ]

        result = rss_collector.sort_posts(posts)

        self.assertEqual(result[0]["title"], "최신 글")
        self.assertEqual(result[1]["title"], "오래된 글")
        self.assertEqual(result[2]["title"], "날짜 없는 글")

    @patch("rss_collector.fetch_feed")
    def test_duplicate_links_are_removed(self, mock_fetch):
        mock_fetch.return_value = SimpleNamespace(
            bozo=False,
            entries=[
                {
                    "title": "새 게시글",
                    "link": "https://example.com/new",
                },
                {
                    "title": "중복 게시글",
                    "link": "https://example.com/existing",
                },
            ],
        )

        test_blogs = [
            {
                "name": "Test Blog",
                "rss_url": "https://example.com/feed",
            }
        ]

        with patch.object(rss_collector, "BLOGS", test_blogs):
            result = rss_collector.collect_posts(
                {"https://example.com/existing"}
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "새 게시글")


if __name__ == "__main__":
    unittest.main()
