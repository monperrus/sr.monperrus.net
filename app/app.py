"""searchinTSE web app: keyword (SQLite FTS5) search over papers, grouped by author.

Each site (selected by the Host header) has its own SQLite index file
`$SEARCH_DB_DIR/<index>.sqlite` (default `db/`), built by `export_pinecone.py`
or by the ingestion job of reviewer-recommendation-system. No network call is
made at request time.
"""

from __future__ import annotations

import json
import os
import pathlib

import flask
from flask import render_template, request

from _fts import LocalIndex
from helpers import error, get_matches

app = flask.Flask(__name__)
SEARCH_DB_DIR = pathlib.Path(os.getenv("SEARCH_DB_DIR", "db"))
K = 100  # number of matching papers to rank authors from
MAX_QUERY_LENGTH = 1000

_TSE = {
    "site_title": "Semantic TSE Reviewer Search",
    "label_people": "Reviewers",
    # "model" is kept for backward compatibility of /config; search ignores it.
    "model": "text-embedding-3-small",
    "index": "tse-text-embedding-3-small-202508",
    "capabilities": ["credit"],
}
_LOCAL = {**_TSE, "site_title": "Local test"}
CONFIG = {
    "127.0.0.1:8000": _LOCAL,
    "localhost:8000": _LOCAL,
    "tse.local:8000": _TSE,
    "tse.local:8083": _TSE,
}
ANNOTATED_HOSTS = {"tse.local:8083", "tse.local:8000", "127.0.0.1:8000"}


def get_index() -> LocalIndex:
    return LocalIndex(SEARCH_DB_DIR / f"{CONFIG[request.host]['index']}.sqlite")


def search_matches(query: str) -> str:
    """JSON string {"papers": [...], "authors": [...]} or an error JSON."""
    try:
        index = get_index()
    except FileNotFoundError as e:
        print(f"Search index unavailable: {e}", flush=True)
        return error("Search index unavailable. Try again in a few minutes.")
    if query.startswith("similar:"):
        paper_id = query.split(":", 1)[-1]
        paper = index.fetch([paper_id])["vectors"].get(paper_id)
        if paper is None:
            return error("Unknown paper.")
        metadata = paper["metadata"]
        text = f"{metadata.get('title', '')} {metadata.get('abstract', '')}"
        return get_matches(index, K, text=text, exclude=paper_id)
    return get_matches(index, K, text=query)


def validate(query: str | None) -> str | None:
    if not query:
        return error("Missing query.")
    if len(query) > MAX_QUERY_LENGTH:
        return error("Sorry! The length of your query cannot be too long.")
    return None


@app.route("/config")
def config():
    return flask.jsonify(CONFIG[request.host])


@app.route("/")
def home():
    return render_template(
        "index.html",
        site_title=CONFIG[request.host]["site_title"],
        label_people=CONFIG[request.host]["label_people"],
    )


@app.route("/annotations")
def annotations():
    if request.host in ANNOTATED_HOSTS:
        return open("tse.csv").read()
    return ""


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/search")
def search():
    """Papers and authors matching `query` (`similar:<id>` for papers like <id>).

    The `model` parameter is accepted for backward compatibility and ignored.
    """
    query = request.args.get("query")
    return validate(query) or search_matches(query)


@app.route("/search-reviewers")
def search_reviewers():
    """Reviewers matching `query`, as JSON {"reviewers": [...]} sorted by score."""
    query = request.args.get("query")
    invalid = validate(query)
    if invalid:
        return invalid
    raw = search_matches(query)
    matches = json.loads(raw)
    if "error" in matches:
        return raw
    return flask.jsonify({"reviewers": matches.get("authors", [])})


@app.route("/robots.txt")
def robots():
    with open("static/robots.txt", "r") as f:
        return f.read()


@app.route("/embedding")
def get_embedding_route():
    """Kept for API compatibility: embeddings no longer exist, always []."""
    return flask.jsonify([])
