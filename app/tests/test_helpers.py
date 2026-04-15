import unittest
from types import SimpleNamespace

from helpers import get_authors


class HelperTests(unittest.TestCase):
    def test_get_authors_groups_and_sorts_by_best_score(self):
        papers = [
            SimpleNamespace(
                id="paper-1",
                title="Paper 1",
                score=0.81,
                authors_v2=[
                    {"dblp_id": "alice", "name": "Alice"},
                    {"dblp_id": "bob", "name": "Bob"},
                ],
            ),
            SimpleNamespace(
                id="paper-2",
                title="Paper 2",
                score=0.93,
                authors_v2=[{"dblp_id": "alice", "name": "Alice"}],
            ),
        ]

        authors = get_authors(papers)

        self.assertEqual([author["author"] for author in authors], ["Alice", "Bob"])
        self.assertEqual(authors[0]["avg_score"], 0.93)
        self.assertEqual(len(authors[0]["papers"]), 2)


if __name__ == "__main__":
    unittest.main()
