# To Do:
# Fetch all local documents 
# Parse json and extract text
# Tokenize text and remove stop words
# Create a dictionary of terms and their corresponding document IDs
# Map with tokens as the keys and a list of corresponding postings.

class Posting:
    def __init__(self, docid, freq, fields):
        self.docid = docid
        self.freq = freq   # change to tfidf when we implement it later
        self.fields = fields # fields are where/how the token appeared (i.e. Header, bold)