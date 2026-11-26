#!/usr/bin/env python3
"""One-shot export of a Pinecone index's metadata into a local SQLite FTS5 index.

Usage:
    PINECONE_API_KEY=... python export_pinecone.py INDEX_NAME [OUT.sqlite]

Needs `pip install pinecone` (not a runtime dependency of the app).
Vectors are not exported: the app searches by text only.
Prints nothing on success except the final count line.
"""

from __future__ import annotations

import argparse
import os
import sys

import _fts


def export(index_name: str, out: str) -> int:
    from pinecone import Pinecone

    index = Pinecone(api_key=os.environ["PINECONE_API_KEY"]).Index(index_name)
    expected = index.describe_index_stats().total_vector_count
    for ids in index.list():
        vectors = index.fetch(ids=list(ids)).vectors
        _fts.upsert(out, ({"id": v.id, "metadata": dict(v.metadata or {})} for v in vectors.values()))
    got = _fts.LocalIndex(out).count()
    print(f"{index_name}: {got} rows exported to {out} (Pinecone reports {expected})")
    return 0 if got == expected else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("index")
    parser.add_argument("out", nargs="?", help="default: db/<index>.sqlite")
    args = parser.parse_args()
    out = args.out or os.path.join("db", f"{args.index}.sqlite")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    return export(args.index, out)


if __name__ == "__main__":
    sys.exit(main())
