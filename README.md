![searchthearXiv](.github/logo.png)

# searchinTSE

Reviewer search for IEEE Transactions on Software Engineering (TSE), served at sr.monperrus.net. Paste the title of a submitted paper (or a topic) and get the matching TSE papers and their authors, ranked as potential reviewers and decorated with their reviewer credit (`app/tse.csv`).

Forked from [searchthearxiv](https://github.com/augustwester/searchthearxiv) by August Wester. The original arXiv pipeline (OpenAI + Pinecone) is still in `data/`, but this app no longer uses it.

## How search works

Search is plain full-text search with SQLite FTS5 (Porter stemming, BM25 ranking: title weighted 3×, author names 1×). It makes no network call at request time: no embedding service, no vector database. A paper's `score` is its BM25 relative to the best match (best = 1.0), and an author's score is that of their best-matching paper. `similar:<paper id>` searches with that paper's title.

Each site (selected by the `Host` header, see `CONFIG` in `app/app.py`) reads one index file, `$SEARCH_DB_DIR/<index>.sqlite` (default `app/db/`, git-ignored).

## Branches and deployment

`main` is the only branch. Production (sr.monperrus.net, on rootmab) is a checkout of `main` in `~/searchintse`, run by the systemd user unit `app/searchintse.service` (install commands in its header). Deploy: `git push rootmab main` (the checkout updates in place), then `ssh rootmab systemctl --user restart searchintse`.

## Run

```
cd app
python3 -m venv . && bin/pip install -r requirements.txt
mkdir -p db && cp /path/to/tse-text-embedding-3-small-202508.sqlite db/
./start.sh     # gunicorn on 127.0.0.1:8000
```

Tests: `cd app && python -m unittest discover -s tests -q`.

## Building and updating the index

- New papers are added by `download-journals-crossref.py --push-to-sqlite DB` in the `reviewer-recommendation-system` workspace, which imports `app/_fts.py` (`upsert`) so writer and reader share one schema, and copies the updated file to the server's `app/db/` (`--deploy`). The index was seeded on 2026-11-26 from the former Pinecone index (exporter: `f44d6ba4:app/export_pinecone.py`).

## API

- `GET /search?query=...` → `{"papers": [...], "authors": [...]}` (or `{"error": ...}`); `model=` is accepted and ignored.
- `GET /search-reviewers?query=...` → `{"reviewers": [...]}`.
- `GET /config`, `GET /annotations` (reviewer credit CSV), `GET /about`.
- `GET /embedding?id=...` → `[]` (kept for compatibility; there are no embeddings anymore).
