import inverted_index
import json
import time
import math
#from inverted_index import get_postings, Posting

def intersect(postings1, postings2):
    # Given 2 postings lists (sorted in ascending order) for 2 different tokens,
    # Return the intersection of docids
    common_docs = []
    p1 = 0
    p2 = 0

    # Lecture 15 psudeocode:
    while p1 < len(postings1) and p2 < len(postings2):
        if postings1[p1].docid == postings2[p2].docid: # check if the docid are the same. 
            common_docs.append(postings1[p1].docid)    # Add to list if so
            p1 += 1                                    # Move pointers forward
            p2 += 1
        elif postings1[p1].docid < postings2[p2].docid: # Move smallest pointer if no match
            p1 += 1
        else:
            p2 += 1

    return common_docs

def search(query, lexicon, index_file, num_docs=None, doc_lengths=None):
    # can remove duplicates by using a dictionary
    tokens = list(dict.fromkeys(inverted_index.tokenize(query)))
    if not tokens:
        return []

    # list of postings for each token
    all_postings = []
    for token in tokens:
        postings = inverted_index.get_postings(token, lexicon, index_file)
        if not postings:
            return []
        all_postings.append(postings)

    # want to sort all_postings by shortest length
    all_postings.sort(key=len)

    # gets first postings list
    result = all_postings[0]
    for post in all_postings[1:]:
        # intersect the current result with the next postings list
        common_docs = set(intersect(result, post))
        result = [p for p in result if p.docid in common_docs]

    if num_docs is not None:
        result = rank(result, all_postings, num_docs, doc_lengths)
    return result
    

def rank(result, all_postings, num_docs, doc_lengths=None):
    # Score matching documents using TF-IDF with HTML field boosts
    keep = {p.docid for p in result}
    scores = {}

    for postings in all_postings:
        if not postings:
            continue

        # Rare terms receive higher IDF scores
        idf = math.log(num_docs / len(postings))

        for p in postings:
            if p.docid not in keep:
                continue

            # Start with the regular frequency of the word
            weighted_freq = p.freq

            # Give extra importance to words in HTML fields
            fields = p.fields or {}

            weighted_freq += (
                4 * fields.get("title", 0)
                + 3 * fields.get("h1", 0)
                + 2 * fields.get("h2", 0)
                + 1.5 * fields.get("h3", 0)
                + 1 * fields.get("bold", 0)
            )

            # Logarithmic TF prevents repeated words from dominating
            tf = 1 + math.log(weighted_freq)

            # Add the TF-IDF contribution for this query term
            scores[p.docid] = (
                scores.get(p.docid, 0) + tf * idf
            )

    # cosine normalization: divide by document length so long pages don't win just by size
    if doc_lengths is not None:
        for docid in scores:
            scores[docid] /= doc_lengths[str(docid)]
    # Return matching documents from highest to lowest score
    return sorted(
        result,
        key=lambda p: scores[p.docid],
        reverse=True
    )


# def test_intersect():
#     postings1 = [Posting(1, 1, {}), Posting(2, 2, {}), Posting(3, 1, {})]
#     postings2 = [Posting(1, 1, {}), Posting(2, 2, {}), Posting(3, 1, {}), Posting(4, 4, {})]
#     print(intersect(postings1, postings2))

# test_intersect()

# def test_search():
#     # Example test for the search function
#     fake = {
#         "milk":  [inverted_index.Posting(1, 1, {}), inverted_index.Posting(2, 2, {}), inverted_index.Posting(3, 1, {})],
#         "cookies":  [inverted_index.Posting(1, 1, {}), inverted_index.Posting(2, 2, {}), inverted_index.Posting(3, 1, {}), inverted_index.Posting(4, 4, {})],
#         "chocolate": [inverted_index.Posting(2, 1, {}), inverted_index.Posting(4, 1, {})],
#     }

#     # temporarily replace the real file lookup with the fake dictionary
#     real_get_postings = inverted_index.get_postings
#     inverted_index.get_postings = lambda token, lexicon, index_file: fake.get(token, [])

#     def docids(query):
#         return [p.docid for p in search(query, None, None)]

#     print(docids("milk"))            # [1, 2, 3]
#     print(docids("milk cookie"))    # [1, 2, 3]
#     print(docids("milk cookie chocolate"))   # [2]  (only page 2 has all three)
#     print(docids("milk bird"))       # []   (bird isn't in the index)
#     print(docids("Milk MILK"))       # [1, 2, 3]  (lowercased, duplicates removed)
#     print(docids("!!!"))            # []   (no tokens)




def run_search():
    # starts search interface in the console and loads lexicon and docid -> url map

    # load the lexicon (token -> byte offset in index.txt)
    # small enough to keep in memory, unlike full index
    with open("lexicon.json", "r", encoding="utf-8") as f:
        lexicon = json.load(f)

    # load docid -> url map so we can show urls instead of docids
    with open("doc.json", "r", encoding="utf-8") as f:
        doc_urls = json.load(f)

    # load docid -> document length for cosine normalization
    with open("doc_lengths.json", "r", encoding="utf-8") as f:
        doc_lengths = json.load(f)
    # keep asking for queries until the user presses enter on an empty line
    while True:
        query = input("\nSearch (or press Enter to quit): ").strip()
        if not query:
            break  # empty query -> quit

        # start timer to measure how long the search takes (<= 300 ms)
        start = time.time()

        # find all pages that contain every word in the query (boolean AND)
        results = search(query, lexicon, "index.txt", len(doc_urls), doc_lengths)

        # turn the top 5 Posting objects into urls
        urls = inverted_index.get_urls(results, doc_urls)

        # stop the timer and convert seconds -> milliseconds
        elapsed_ms = (time.time() - start) * 1000

        # print the results
        if not urls:
            print("No results found.")
        for i, url in enumerate(urls, 1):  # numbers the results starting at 1
            print(f"{i}. {url}")

        # show how many pages matched in total and how long the search took
        print(f"({len(results)} matching pages, {elapsed_ms:.1f} ms)")

if __name__ == "__main__":
    run_search()
