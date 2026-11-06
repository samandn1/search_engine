import os
import json
import re
from bs4 import BeautifulSoup
from nltk.stem import PorterStemmer

stemmer = PorterStemmer()
# To Do:
# Fetch all local documents 
# Parse json and extract text
# Tokenize text 
# Create a dictionary of terms and their corresponding document IDs
# Map with tokens as the keys and a list of corresponding postings.

class Posting:
    def __init__(self, docid, freq, fields):
        self.docid = docid
        self.freq = freq   # change to tfidf when we implement it later
        self.fields = fields # fields are where/how the token appeared (i.e. Header, bold)
                            # fields should probably look like this: {"html_field_tag": number of occurences}
                            # {"title": 1, "h1": 2, "h3":0, "bold": 2}
    def increase_frequency(self, field=None):
        # increase the freq of the token and where they show up in the fields
        # maybe change later 
        self.freq += 1
        if field in self.fields:
            self.fields[field] += 1

def read_data(folder_path):
    """ 
    Reads the json files in the DEV data folder.
    Yields the webpage's docid, url, and html content.
    """
    docid = 1      # docid starts at 1

    for root, dirs, files in os.walk(folder_path):
        dirs.sort() # sort the directories so that the docids 
                    # for each webpage stays consistent across everyone's devices

        for filename in sorted(files):
            if not filename.endswith(".json"):
                continue
            
            filepath = os.path.join(root, filename)

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                url = data.get("url", "")
                content = data.get("content", "")

                yield docid, url, content    # yield the results so that we don't write everything into ram 

                docid += 1
            except (OSError, ValueError) as e:
                print(f"Error reading {filepath}: {e}")

def tokenize(text):
    # Extract all alphanumeric sequences
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())

    # Stem every token (including stop words)
    return [stemmer.stem(token) for token in tokens]


def process_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-visible content
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Extract readable text
    text = soup.get_text(separator=" ", strip=True)

    # Tokenize and stem
    return tokenize(text)


def test_read_data(folder_path):
    # this is just to test the json reading
    # will delete later
    for docid, url, content in read_data(folder_path):
        print("Document ID: ", docid)
        print("URL: ", url)
        print("Content: ", content[:100])
        print("--------------------------------")

        if docid == 5:
            break

test_read_data("DEV")
# Temporary test for HTML parsing and tokenization
sample_html = """
<html>
    <head><title>Learning Python</title></head>
    <body>
        <h1>Programming Classes</h1>
        <p>Students are learning programming!</p>
    </body>
</html>
"""

print("Processed tokens:", process_html(sample_html))











def save_index(inverted_index, filename):
    with open(filename, "w", encoding="utf-8") as f:
        # loop through every token and its posting list
        for token, postings in sorted(inverted_index.items()):
            posting_list = []
            # sort the postings by docid (least to greatest) for the boolean querys later
            # loop through every Posting object for this token
            for posting in sorted(postings, key=lambda p: p.docid):
                # use json.dumps to convert fields dictionary to a compact string
                fields = json.dumps(posting.fields, separators=(",", ":"))
                # format: docid:frequency:fields
                posting_data = f"{posting.docid}:{posting.freq}:{fields}"
                posting_list.append(posting_data)

            # write token and its postings
            # each line in the file will be for one token like below
            # token docid:frequency:fields docid:frequency:fields ...
            f.write(token + " " + " ".join(posting_list) + "\n")

def test_saving_index():
    inverted_index = {
        "cat": [Posting(1, 1, {"title": 1}), Posting(2, 2, {"h1": 2})],
        "dog": [Posting(3, 3, {"h2": 3}), Posting(1, 1, {"bold": 1}), Posting(4, 4, {"h1": 4})]
    }

    save_index(inverted_index, "index.txt")
    print("Unique tokens:", len(inverted_index))
    print(f"Index size: {os.path.getsize('index.txt') / 1024:.2f} KB")

test_saving_index()