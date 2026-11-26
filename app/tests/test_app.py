import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from test_fts import build

INDEX = "tse-text-embedding-3-small-202508"
# Keys of the Pinecone-era /search response (captured 2026-11-26), which the UI relies on.
PAPER_KEYS = {"abstract", "authors", "authors_parsed", "authors_v2", "id", "month", "score", "title", "url", "year"}
AUTHOR_KEYS = {"author", "author_v2", "avg_score", "papers"}
HOST = {"Host": "tse.local:8000"}


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        build(Path(self.tmp.name) / f"{INDEX}.sqlite")
        self.db = patch.object(app_module, "SEARCH_DB_DIR", Path(self.tmp.name))
        self.db.start()
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()

    def get_json(self, path, **params):
        response = self.client.get(path, query_string=params, headers=HOST)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.data)

    def test_home_route_renders_for_localhost(self):
        response = self.client.get("/", headers={"Host": "localhost:8000"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Local test", response.data)

    def test_about_renders_for_every_host(self):
        for host in app_module.CONFIG:
            with self.subTest(host=host):
                self.assertEqual(self.client.get("/about", headers={"Host": host}).status_code, 200)

    def test_config_route_keeps_model_field(self):
        self.assertEqual(self.get_json("/config")["model"], "text-embedding-3-small")

    def test_search_requires_query(self):
        self.assertEqual(self.get_json("/search")["error"], "Missing query.")

    def test_search_rejects_long_queries(self):
        self.assertEqual(
            self.get_json("/search", query="x" * 1001)["error"],
            "Sorry! The length of your query cannot be too long.",
        )

    def test_search_returns_papers_and_authors_with_legacy_shape(self):
        data = self.get_json("/search", query="program repair", model="ignored")
        self.assertEqual(data["papers"][0]["score"], 1.0)
        self.assertEqual(set(data["papers"][0]), PAPER_KEYS)
        self.assertEqual(set(data["authors"][0]), AUTHOR_KEYS)
        self.assertEqual(data["authors"][0]["author"], "Alice")

    def test_search_without_match_is_empty(self):
        self.assertEqual(self.get_json("/search", query="blockchain"), {"papers": [], "authors": []})

    def test_similar_excludes_the_paper_itself(self):
        data = self.get_json("/search", query="similar:p1")
        ids = [p["id"] for p in data["papers"]]
        self.assertNotIn("p1", ids)
        self.assertEqual(ids[0], "p3")

    def test_similar_unknown_paper(self):
        self.assertEqual(self.get_json("/search", query="similar:nope")["error"], "Unknown paper.")

    def test_search_reviewers(self):
        reviewers = self.get_json("/search-reviewers", query="program repair")["reviewers"]
        self.assertEqual([r["author"] for r in reviewers][:1], ["Alice"])
        self.assertEqual(self.get_json("/search-reviewers")["error"], "Missing query.")

    def test_missing_index_is_an_error_not_a_crash(self):
        with patch.object(app_module, "SEARCH_DB_DIR", Path(self.tmp.name) / "nowhere"):
            self.assertIn("error", self.get_json("/search", query="repair"))

    def test_embedding_route_kept_and_empty(self):
        self.assertEqual(self.get_json("/embedding", id="p1"), [])


if __name__ == "__main__":
    unittest.main()
