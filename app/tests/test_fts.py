import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _fts


def authors_v2(*people):
    return base64.b64encode(
        json.dumps([{"name": n, "dblp_id": n.lower(), "active": True} for n in people]).encode()
    ).decode()


PAPERS = [
    ("p1", "Automated program repair with templates", ["Alice"]),
    ("p2", "Mutation testing at scale", ["Bob"]),
    ("p3", "Repairing programs with large language models", ["Alice", "Carol"]),
    ("p4", "Flaky tests in continuous integration", ["Dave"]),
    ("p5", "A survey of code review practices", ["Erin"]),
]


def build(path):
    return _fts.upsert(
        path,
        (
            {
                "id": pid,
                "metadata": {
                    "title": title,
                    "authors": names,
                    "authors_v2": authors_v2(*names),
                    "year": "2020",
                    "doi": f"10.1/{pid}",
                },
            }
            for pid, title, names in PAPERS
        ),
    )


class FtsIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "idx.sqlite"
        build(self.path)
        self.index = _fts.LocalIndex(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_known_positive_ranks_title_match_first_with_score_one(self):
        matches = self.index.query(text="mutation testing")["matches"]
        self.assertEqual(matches[0]["id"], "p2")
        self.assertEqual(matches[0]["score"], 1.0)
        self.assertEqual(matches[0]["metadata"]["title"], "Mutation testing at scale")

    def test_stemming_matches_inflected_forms(self):
        ids = [m["id"] for m in self.index.query(text="program repair")["matches"]]
        self.assertEqual(set(ids[:2]), {"p1", "p3"})

    def test_scores_are_normalized_and_decreasing(self):
        scores = [m["score"] for m in self.index.query(text="repair tests review")["matches"]]
        self.assertEqual(scores[0], 1.0)
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(0 < s <= 1.0 for s in scores))

    def test_author_names_are_searchable(self):
        self.assertEqual({m["id"] for m in self.index.query(text="carol")["matches"]}, {"p3"})

    def test_known_negative_returns_no_match(self):
        self.assertEqual(self.index.query(text="blockchain")["matches"], [])

    def test_fts_syntax_in_user_input_is_neutralized(self):
        for text in ['foo" AND (', "NEAR(a b)", "test*", "-repair", "title:repair", "))((", "", "  ?!  "]:
            with self.subTest(text=text):
                self.assertIsInstance(self.index.query(text=text)["matches"], list)

    def test_top_k_limits_results(self):
        self.assertEqual(len(self.index.query(text="repair testing review flaky", top_k=2)["matches"]), 2)

    def test_fetch_returns_known_ids_only(self):
        vectors = self.index.fetch(["p1", "missing"])["vectors"]
        self.assertEqual(list(vectors), ["p1"])
        self.assertEqual(vectors["p1"]["metadata"]["doi"], "10.1/p1")

    def test_upsert_is_idempotent_and_updates(self):
        self.assertEqual(build(self.path), 0)
        _fts.upsert(self.path, [{"id": "p2", "metadata": {"title": "Fuzzing compilers"}}])
        self.assertEqual(self.index.count(), len(PAPERS))
        self.assertEqual(self.index.query(text="mutation")["matches"], [])
        self.assertEqual(self.index.query(text="fuzzing")["matches"][0]["id"], "p2")

    def test_index_is_opened_read_only(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.index._conn().execute("DELETE FROM papers")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            _fts.LocalIndex(Path(self.tmp.name) / "absent.sqlite")


if __name__ == "__main__":
    unittest.main()
