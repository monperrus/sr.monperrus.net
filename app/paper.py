import base64
import json

class Paper(dict):
    def __init__(self, match):
        super().__init__()
        
        self.id = match["id"]
        self.score = round(match["score"], 2)
        
        metadata = match["metadata"]
        self.title = metadata["title"] if "title" in metadata else "notitle"
        
        self.authors = metadata["authors"]  if "authors" in metadata else "noauthors"

        self.year = metadata["year"]  if "year" in metadata else "noyear"

        if "url" in metadata:
            self.url = metadata["url"]
        else:
            # dblp stores the DOI as a resolver URL, Crossref as a bare DOI (same rule as static/script.js)
            doi = metadata["doi"] if "doi" in metadata else self.id.replace("#", "/")
            self.url = doi if doi.startswith("http") else f"https://doi.org/{doi}"

        self.abstract = metadata["abstract"]  if "abstract" in metadata else "noabstract"
        self.month = metadata["month"]  if "month" in metadata else "nomonth"
        
        # self.authors_parsed is a list
        self.authors_parsed = self.authors
        if type(self.authors) == str:
            self.authors_parsed = [author.strip() for author in self.authors.split(",")]
            
        # self.authors_parsed is a list of items
        if "authors_v2" in metadata and metadata["authors_v2"]:
            self.authors_v2 = json.loads(base64.b64decode(metadata["authors_v2"]))

