"""Turn index matches into the JSON the UI consumes: papers, and authors ranked by best paper."""

import json
from collections import defaultdict

from paper import Paper


def compute_score(papers):
    # return avg_score(papers) # not good, overfavor prolific authors who are typically not available
    return max_score(papers)

def max_score(papers):
    # max is much better as usual, think fuzzy logic
    final_score = max([p.score for p in papers])
    return round(final_score, 2)

def avg_score(papers):
    avg_score = sum([p.score for p in papers]) / len(papers)
    return round(avg_score, 2)

def get_matches(index, k, text, exclude=None):
    """Top-k papers for `text` and their authors, as a JSON string."""
    matches = index.query(text=text, top_k=k + 1, include_metadata=True)["matches"]
    papers = [Paper(match) for match in matches if match["id"] != exclude][:k]
    authors = get_authors(papers)[:k]
    papers = [paper.__dict__ for paper in papers]
    return json.dumps({"papers": papers, "authors": authors})


def get_authors(papers):
    authors_ids = defaultdict(list)
    for paper in papers:
        for author in paper.authors_v2:
            if "dblp_id" not in author:
                continue
            if author["dblp_id"] not in authors_ids:
                authors_ids[author["dblp_id"]] = {
                    "author": author["name"],
                    "author_v2": author, # new info, contains dblp_id
                    "papers": [paper]
                }
            else:
                authors_ids[author["dblp_id"]]["papers"].append(paper)

    authors = [{
        "author": data["author"],
        "author_v2": data["author_v2"],  # new info
        "papers": [paper.__dict__ for paper in data["papers"]],
        "avg_score": compute_score(data["papers"])}
                for author, data in authors_ids.items()]
    authors = sorted(authors, key=lambda e: e["avg_score"], reverse=True)
    # authors = sorted(authors, key=lambda e: len(e["papers"]), reverse=True)
    return authors

def error(msg):
    return json.dumps({"error": msg})
