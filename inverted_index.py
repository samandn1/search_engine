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
        if field is not None:
            self.fields[field] = self.fields.get(field, 0) + 1 # if field exists add 1, if not default 1

class InvertedIndex:
    def __init__(self):
        # use a dictionary to store the index
        # the keys are tokens and the values are lists of postings
        self.index = {}
        # store docID to url
        self.doc = {}

    def add_posting(self, url, docID, token_counts):
        self.doc[docID] = url
        for token, freq in token_counts.items():
            # create positng object for each token and add it to the index
            posting = Posting(docID, freq, {}) 
            # checks for new token
            if token not in self.index:
                self.index[token] = []
            # add the posting to the list of postings for the token
            self.index[token].append(posting)

    def save_documents(self):
        with open("doc.json", "w", encoding="utf-8") as f:
            json.dump(self.doc,f)
    
    def save_index(self, filename):
        with open(filename, "w", encoding="utf-8") as f:
            # loop through every token and its posting list
            for token, postings in sorted(self.index.items()):
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

    def clear(self):
        # need to ofload the index from memory
        self.index.clear()


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


def build_index(folder_path, offload = 15000):
    inverted_index = InvertedIndex()
    # list to keep track of the partial index files
    partial_index_file = []  
    last_doc_offloaded = 0

    for docid, url, content in read_data(folder_path):
        tokens = process_html(content)
        token_counts = {} # dictionary to keep track of each token's freq {"token": 1}
       
        for token in tokens:
            if token not in token_counts:  # create a new key value pair for a new token
                token_counts[token] = 0
            token_counts[token] += 1 # increment the freq
        
        # add the document's tokens to the inverted index
        inverted_index.add_posting(url, docid, token_counts)
        last_doc_offloaded += 1

        # if docid % 1000 == 0:       # Progress markers (delete later)
        #     print(f"Indexed {docid} documents", flush=True)

        if last_doc_offloaded >= offload:
            offload_index(inverted_index, partial_index_file)
            last_doc_offloaded = 0
    
    if inverted_index.index:
        offload_index(inverted_index, partial_index_file) # saves leftover pages after loop
    return inverted_index, partial_index_file

def offload_index(inverted_index, partial_index_file):
    path = f"partial_indexes_{len(partial_index_file)}.txt"
    inverted_index.save_index(path)
    partial_index_file.append(path)
    inverted_index.save_documents()
    inverted_index.clear() 

def merge_partial_indexes(partial_files, output_file):
    # open every partial index file at once
    files = [open(p, "r", encoding="utf-8") for p in partial_files]

    # read the first row of each file -> (token, postings)
    current = [read_next(f) for f in files]

    unique_tokens = 0
    with open(output_file, "w", encoding="utf-8") as out:
        while True:
            # find the alphabetically smallest token among the current lines
            tokens = [line[0] for line in current if line is not None]
            if not tokens:
                break # every file is finished
            smallest = min(tokens)

            # combine postings from every file whose current token is the smallest
            # files are in docid order, so joining them in file order keeps postings sorted
            merged = []
            for i in range(len(files)):
                if current[i] is not None and current[i][0] == smallest:
                    merged.append(current[i][1])
                    current[i] = read_next(files[i]) # move that file to its next line

            out.write(smallest + " " + " ".join(merged) + "\n")
            unique_tokens += 1

    for f in files:
        f.close()
    return unique_tokens

def read_next(f):
    # read one line and split it into (token, postings). returns None at end of file
    line = f.readline()
    if not line:
        return None
    token, postings = line.rstrip("\n").split(" ", 1)
    return (token, postings)

def report(num_docs, unique_tokens, index_file):
    # divide by 1024 to convert  bytes to KB
    # index_file will be a txt file. 
    # assignment wants a pdf report, so might have to change this
    size = os.path.getsize(index_file) / 1024 
    with open("report.txt", "w") as f:
        f.write(f"Number of indexed documents: {num_docs}\n")
        f.write(f"Number of unique tokens: {unique_tokens}\n")
        f.write(f"Index size: {size:.2f} KB\n")


def build_lexicon(index_file):
    # Build a lexicon file so that we can find each token's location in the index file, 
    # without searching through the entire file --> avoids loading in the index in memory (Developer contraints)
    # A lexicon is a dictionary that maps each token to its location (byte offset) in the inverted index file.
    # lexicon = {"token1": 10} means token1's postings list start at byte position 18.
    # with the byte location, we can use .seek() to jump to that byte in the file to read.
    lexicon = {}

    # open the index file with "rb" = read binary (so read it in binary mode (bytes instead of strings)
    with open(index_file, "rb") as f:
        while True:
            # Get the current byte position
            offset = f.tell()

            # Read one line
            line = f.readline()

            # Stop at the end of the file
            if not line:
                break

            # Extract the token before the first space.
            token = line.split(b" ", 1)[0].decode("utf-8")

            # Store token and its byte position
            lexicon[token] = offset

    # Save lexicon to a JSON file
    with open("lexicon.json", "w", encoding="utf-8") as f:
        json.dump(lexicon, f)
    
    return lexicon


def get_postings(token, lexicon, index_file):
    # Given a specific token, get its postings list from the inverted_index file

    # Check if token exists
    if token not in lexicon:
        return []

    # Open index in binary mode
    with open(index_file, "rb") as f:
        f.seek(lexicon[token]) # Jump to the token's location
        line = f.readline().decode("utf-8") # Read that token's line

    parts = line.strip().split(" ", 1) # Separate token from its postings

    if len(parts) < 2: # check whether the line has both a token and its posting list.
        return []

    postings = []

    for entry in parts[1].split():
        docid, freq, fields = entry.split(":", 2)

        postings.append(Posting(int(docid), int(freq), json.loads(fields)))

    return postings


if __name__ == "__main__":
    inverted_index, partial_index_files = build_index("DEV")

    unique_tokens = merge_partial_indexes(partial_index_files, "index.txt")
    inverted_index.save_documents()

    report(len(inverted_index.doc), unique_tokens, "index.txt")

    # Build and save lexicon
    lexicon = build_lexicon("index.txt")


   # Test lexicon
    # print("Lexicon entries:", len(lexicon))
    # print("Academia offset:", lexicon.get("academia"))

    # # Test get_postings()
    # postings = get_postings("academia", lexicon, "index.txt")

    # print("\nPostings for 'academia':")
    # for posting in postings[:10]:
    #     print(
    #         "DocID:", posting.docid,
    #         "Frequency:", posting.freq,
    #         "Fields:", posting.fields)
    # print("Unique tokens:", unique_tokens)
    # print("Lexicon entries:", len(lexicon))
    # print("Match:", unique_tokens == len(lexicon)) # should match

