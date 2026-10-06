import unittest

from app.feed_parser import FeedParseError, parse_feed


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example RSS</title>
    <item>
      <guid>rss-1</guid>
      <title>RSS 게시글</title>
      <link>https://example.com/rss-1</link>
      <author>개발팀</author>
      <description><![CDATA[<p>RSS 요약</p>]]></description>
      <pubDate>Tue, 06 Oct 2026 01:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom</title>
  <entry>
    <id>tag:example.com,2026:atom-1</id>
    <title>Atom 게시글</title>
    <link href="https://example.com/atom-1" />
    <author><name>플랫폼팀</name></author>
    <summary>Atom 요약</summary>
    <content type="html">&lt;p&gt;Atom 본문&lt;/p&gt;</content>
    <published>2026-10-06T02:00:00Z</published>
    <updated>2026-10-06T03:00:00Z</updated>
  </entry>
</feed>
"""


class FeedParserTest(unittest.TestCase):
    def test_parses_rss(self):
        articles = parse_feed(RSS, blog_id=1, fetched_at="2026-10-06T12:00:00+09:00")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["entry_key"], "rss-1")
        self.assertEqual(articles[0]["title"], "RSS 게시글")
        self.assertEqual(articles[0]["published_at"], "2026-10-06T01:00:00+00:00")

    def test_parses_atom_and_prefers_content(self):
        article = parse_feed(ATOM, blog_id=2)[0]

        self.assertEqual(article["entry_key"], "tag:example.com,2026:atom-1")
        self.assertEqual(article["author"], "플랫폼팀")
        self.assertEqual(article["content"], "<p>Atom 본문</p>")
        self.assertEqual(article["feed_updated_at"], "2026-10-06T03:00:00+00:00")

    def test_uses_url_when_guid_is_missing(self):
        feed = RSS.replace("<guid>rss-1</guid>", "")
        article = parse_feed(feed, blog_id=1)[0]

        self.assertEqual(article["entry_key"], "https://example.com/rss-1")

    def test_rejects_invalid_feed(self):
        with self.assertRaises(FeedParseError):
            parse_feed("not xml", blog_id=1)


if __name__ == "__main__":
    unittest.main()
