import unittest

from paper import Paper


def paper(id_, **metadata):
    return Paper({"id": id_, "score": 1.0, "metadata": {"title": "t", **metadata}})


class PaperUrlTests(unittest.TestCase):
    def test_bare_doi_gets_resolver_prefix(self):
        self.assertEqual(paper("10.1109#tse.2024.1", doi="10.1109/tse.2024.1").url, "https://doi.org/10.1109/tse.2024.1")

    def test_dblp_doi_is_already_a_url(self):
        p = paper("https:##doi.org#10.1109#TSE.2021.3067156", doi="https://doi.org/10.1109/TSE.2021.3067156")
        self.assertEqual(p.url, "https://doi.org/10.1109/TSE.2021.3067156")

    def test_id_fallback(self):
        self.assertEqual(paper("10.1109#32.106985").url, "https://doi.org/10.1109/32.106985")
        self.assertEqual(paper("https:##doi.org#10.1109#32.1").url, "https://doi.org/10.1109/32.1")

    def test_explicit_url_wins(self):
        self.assertEqual(paper("x", url="https://arxiv.org/abs/1", doi="10.1/x").url, "https://arxiv.org/abs/1")
