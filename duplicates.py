# duplicates.py
# exact (checksum) and near (simhash) duplicate detection, adapted from A2

import hashlib
from collections import deque
from nltk.stem import PorterStemmer

NUM_BITS = 32 # fingerprint size in bits
THRESHOLD = 30/32 # pages are near duplicates if at least 30 of 32 bits match
RECENT_LIMIT = 1000 # number of recent pages to compare against
MIN_TOKENS = 50 # skip simhash for very short pages

# stemmed stopwords, only used for the fingerprint (not the index)
stemmer = PorterStemmer()
try:
    with open("stopwords.txt", encoding="utf-8") as file:
        stopwords = {stemmer.stem(line.strip().lower()) for line in file if line.strip()}
except FileNotFoundError:
    stopwords = set()


class DuplicateDetector:
    def __init__(self):
        self.seen_checksums = set()
        self.recent_fingerprints = deque(maxlen=RECENT_LIMIT)
        self.exact_dups = 0
        self.near_dups = 0

    # true if the page is an exact or near duplicate of an already indexed page
    def is_duplicate(self, tokens, token_counts):
        # exact duplicate check
        checksum = page_checksum(tokens)
        if checksum in self.seen_checksums:
            self.exact_dups += 1
            return True
        self.seen_checksums.add(checksum)

        # near duplicate check
        if len(tokens) >= MIN_TOKENS:
            fingerprint = compute_simhash(compute_frequencies(token_counts))
            if is_near_duplicate(fingerprint, self.recent_fingerprints):
                self.near_dups += 1
                return True
            self.recent_fingerprints.append(fingerprint)

        return False


# md5 checksum of the page's tokens
def page_checksum(tokens):
    return hashlib.md5(" ".join(tokens).encode("utf-8")).hexdigest()

# token counts without stopwords and pure numbers
def compute_frequencies(token_counts):
    freq_dict = {}
    for token, count in token_counts.items():
        if token not in stopwords and not token.isdigit():
            freq_dict[token] = count
    return freq_dict

def hash_word(word):
    word_byte = word.encode("utf-8")
    word_4_bytes = hashlib.md5(word_byte).digest()[-4:]
    return int.from_bytes(word_4_bytes, "big")

# builds the page fingerprint from its word frequencies
def compute_simhash(freq_dict):
    start = [0] * NUM_BITS

    # for each bit position: add the word's count if the word's hash has a 1 there, subtract it if 0
    # so frequent words have more say in the final fingerprint
    for word, count in freq_dict.items():
        h = hash_word(word)
        for i in range(NUM_BITS):
            if (h >> i) & 1:
                start[i] += count
            else:
                start[i] -= count

    fingerprint = 0
    # fingerprint bit is 1 where the weighted total is positive, 0 otherwise
    for i in range(NUM_BITS):
        if start[i] > 0:
            fingerprint |= (1 << i)

    return fingerprint


# fraction of bits that match between two fingerprints
def compute_similarity(a, b):
    differences = bin(a ^ b).count("1")
    matching = NUM_BITS - differences
    return matching / NUM_BITS

# true if the page matches any recently seen fingerprint above the threshold
def is_near_duplicate(fingerprint, seen_fingerprints):
    for seen in seen_fingerprints:
        if compute_similarity(fingerprint, seen) >= THRESHOLD:
            return True
    return False
