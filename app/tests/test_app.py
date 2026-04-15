import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app as app_module


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_home_route_renders_for_localhost(self):
        response = self.client.get("/", headers={"Host": "localhost:8000"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Local test", response.data)

    def test_config_route_returns_localhost_config(self):
        response = self.client.get("/config", headers={"Host": "localhost:8000"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["model"], "text-embedding-3-small")

    def test_search_requires_query(self):
        response = self.client.get("/search", headers={"Host": "localhost:8000"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)["error"], "Missing query.")

    def test_search_rejects_long_queries_before_pinecone(self):
        with patch.object(app_module, "Pinecone") as pinecone_cls:
            response = self.client.get(
                "/search",
                query_string={"query": "x" * 1001},
                headers={"Host": "localhost:8000"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.data)["error"],
            "Sorry! The length of your query cannot be too long.",
        )
        pinecone_cls.assert_not_called()

    def test_search_returns_matches_with_mocked_dependencies(self):
        pinecone_client = MagicMock()
        pinecone_index = MagicMock()
        pinecone_client.Index.return_value = pinecone_index

        with (
            patch.dict(app_module.os.environ, {"PINECONE_API_KEY": "test-key"}, clear=False),
            patch.object(app_module, "Pinecone", return_value=pinecone_client),
            patch.object(app_module, "get_cached_embedding", return_value=[0.1, 0.2, 0.3]),
            patch.object(
                app_module,
                "get_matches",
                return_value=json.dumps({"papers": [], "authors": []}),
            ),
        ):
            response = self.client.get(
                "/search",
                query_string={"query": "vector databases"},
                headers={"Host": "localhost:8000"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), {"papers": [], "authors": []})
        pinecone_client.Index.assert_called_once_with("tse-text-embedding-3-small-202508")


class EmbeddingCacheTests(unittest.TestCase):
    def test_get_cached_embedding_uses_cache_after_first_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                app_module.app.test_request_context("/", headers={"Host": "localhost:8000"}),
                patch.object(app_module, "EMBEDDING_CACHE_DIR", Path(tmpdir)),
                patch.object(
                    app_module,
                    "get_openai_embedding",
                    side_effect=[[1.0, 2.0, 3.0]],
                ) as embedding_fn,
            ):
                first = app_module.get_cached_embedding("Hello world", "text-embedding-3-small")
                second = app_module.get_cached_embedding("Hello world", "text-embedding-3-small")

        self.assertEqual(first, [1.0, 2.0, 3.0])
        self.assertEqual(second, [1.0, 2.0, 3.0])
        embedding_fn.assert_called_once_with("Hello world", "text-embedding-3-small")


if __name__ == "__main__":
    unittest.main()
