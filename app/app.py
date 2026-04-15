import os
import pathlib
import requests
import hashlib
import json
from datetime import datetime
import flask
#from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
import validators
from flask import render_template, request
from helpers import get_matches, fetch_abstract, error

# Load environment variables from .env file
#load_dotenv()

app = flask.Flask(__name__)
EMBEDDING_CACHE_DIR = pathlib.Path(os.getenv("EMBEDDING_CACHE_DIR", "embeddingjson"))


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    return OpenAI(api_key=api_key)


def get_openai_embedding(text: str, model: str) -> list[float]:
    response = get_openai_client().embeddings.create(model=model, input=text)
    return response.data[0].embedding


def get_ollama_embedding(text: str, model: str) -> list:
    """Get embedding from local Ollama server
    
    Args:
        text (str): Text to embed
        model (str): Model name to use
        
    Returns:
        list: Embedding vector
        
    Raises:
        Exception: If embedding fails
    """
    url = OLLAMA_URL
    payload = {
        "model": model,
        "prompt": text,
        "stream": False
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json().get('embedding', [])

def get_cached_embedding(text: str, model: str) -> list:
    """Get embedding from cache or compute and cache it"""
    print("get_cached_embedding",request.host,model)
    
    # Generate consistent filename from text
    text_hash = hashlib.sha256(text.lower().encode('utf-8')).hexdigest()
    # the file name has to contain the model name, otherwise the cache will be shared between models of different embedding dimensions and semantics    
    cache_file = EMBEDDING_CACHE_DIR / f"{model}-{text_hash}.json"
    cache_file.parent.mkdir(exist_ok=True, parents=True)
    
    # Check cache first
    if cache_file.exists():
        with cache_file.open('r') as f:
            data = json.load(f)
            return data['embedding']
    
    # Get new embedding if not cached
    fn = globals()[CONFIG[request.host]["embedding_fn"]]
    embedding = fn(text, model)
        
    # Cache the result
    data = {
        "text": text,
        "embedding": embedding,
        "model": model,
        "timestamp": datetime.now().isoformat()
    }
    with cache_file.open('w') as f:
        json.dump(data, f, indent=2)
    
    return embedding

# OLLAMA_URL = "http://localhost:8090/api/embeddings"
OLLAMA_URL = "http://130.237.224.95:8080/api/embeddings"
CONFIG = {
    "127.0.0.1:8000": {
        "site_title": "Local test",
        "label_people": "Reviewers",
        "model": "text-embedding-3-small",
        "index": "tse-text-embedding-3-small-202508",
        "embedding_fn": "get_openai_embedding",
        "capabilities": ["credit"]
    },
    "localhost:8000": {
        "site_title": "Local test",
        "label_people": "Reviewers",
        "model": "text-embedding-3-small",
        "index": "tse-text-embedding-3-small-202508",
        "embedding_fn": "get_openai_embedding",
        "capabilities": ["credit"]
    },
    "0.0.0.0:8000": {
        "site_title": "Local test",
        "label_people": "Reviewers",
        "model": "text-embedding-3-small",
        "index": "search-the-arxiv",
        "embedding_fn": "get_openai_embedding",
        "capabilities": ["credit"]
    },
    "tse.local:8083": {
        "site_title": "Semantic TSE Reviewer Search",
        "label_people": "Reviewers",
        "model": "text-embedding-3-small",
        "index": "tse-text-embedding-3-small-202508",
        "embedding_fn": "get_openai_embedding",
        "capabilities": ["credit"]
    },
    "se-search.local:8083": {
        "site_title": "Semantic Software Engineering Search",
        "label_people": "Authors",
        "model": "mxbai-embed-large",
        "index": "se-mxbai-embed-large",
        "embedding_fn": "get_ollama_embedding",
        "capabilities": []
    },
    "OLD_________se-search.local:8083": {
        "site_title": "Semantic Software Engineering Search",
        "label_people": "Authors",
        "model": "jeffh/intfloat-multilingual-e5-large-instruct:f16",
        "index": "se-intfloat-multilingual-e5-large-instruct",
        "embedding_fn": "get_ollama_embedding",
        "capabilities": []
    }
}

@app.route("/config")
def config():
    return flask.jsonify(CONFIG[request.host])

@app.route("/")
def home():
    # split request.host in name port
    site_title = request.host.split(":")[0] if ":" in request.host else request.host
    
    return render_template("index.html", site_title=CONFIG[request.host]["site_title"], label_people = CONFIG[request.host]["label_people"])

@app.route("/annotations")
def annotations():
    if request.host == "tse.local:8083" or request.host == "127.0.0.1:8000":
        return open("tse.csv").read()
    return ""

@app.route("/about")
def about():
    return render_template(f"about-{request.host}.html", model = CONFIG[request.host]["model"])

@app.route("/search")
def search():
    query = request.args.get("query")
    # Get model from request, fallback to default
    model = request.args.get("model", CONFIG[request.host]["model"])
    # print("model: ",model,request.host)

    if not query:
        return error("Missing query.")
     
    # special logic for handling arxiv url queries
    # if validators.url(query):
    #     arxiv_id = query.split("/")[-1]
    #     matches = index.fetch([arxiv_id])["vectors"]
    #     if len(matches) == 0:
    #         abstract = fetch_abstract(query)
    #         embed = get_embedding(abstract, MODEL)
    #         return get_matches(index, K, vector=embed, exclude=arxiv_id)
    #     return get_matches(index, K, id=arxiv_id, exclude=arxiv_id)
    
    # reject natural language queries longer than 200 characters
    if len(query) > 1000:
        return error("Sorry! The length of your query cannot be too long.")

    # connect to Pinecone only after basic query validation
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index = pc.Index(CONFIG[request.host]["index"])

    K = 100 # number of matches to request from Pinecone
    
    if query.startswith("similar:"):
        paper_id = query.split(":")[-1]
        embed = get_embedding_paper(paper_id)
        return get_matches(index, K, vector=embed, exclude=paper_id)

    # old version for TSE, using openai
    embed = get_cached_embedding(query, model)
    
    # once we have the query embedding, find closest matches in Pinecone
    try:
        return get_matches(index, K, vector=embed)
    except Exception as e:
        print(f"Encountered error when fetching matches from Pinecone: {e}", flush=True)
        return error("Pinecone not responding. Try again in a few minutes.")

@app.route("/robots.txt")
def robots():
    with open("static/robots.txt", "r") as f:
        content = f.read()
    return content

def get_embedding_paper(paper_id):
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index = pc.Index(CONFIG[request.host]["index"])
    data = index.fetch([paper_id])
    return data["vectors"][paper_id]["values"]

@app.route("/embedding")
def get_embedding_route():
    return flask.jsonify(get_embedding_paper(request.args.get("id")))
