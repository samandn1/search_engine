import inverted_index
import json
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

def search(query, lexicon, index_file):
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
        common_docs = intersect(result, post)
        result = [p for p in result if p.docid in common_docs]

    return result
    

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


def search_interface():
    # Load the lexicon and document URLs from M1
    with open("lexicon.json", "r", encoding="utf-8") as f:
        lexicon = json.load(f)

    with open("doc.json", "r", encoding="utf-8") as f:
        documents = json.load(f)

    print("UCI Search Engine")
    print("Type 'quit' to exit.")

    while True:
        query = input("\nEnter search query: ").strip()

        if query.lower() == "quit":
            print("Goodbye!")
            break

        if not query:
            print("Please enter a search query.")
            continue

        # Call the team's existing search function
        results = search(query, lexicon, "index.txt")

        if not results:
            print("No matching documents found.")
            continue

        print(f"\nFound {len(results)} matching documents.")
        print("First 5 matching URLs:")

        # Convert document IDs into URLs
        for i, posting in enumerate(results[:5], start=1):
            url = documents.get(str(posting.docid), "URL not found")
            print(f"{i}. {url}")


if __name__ == "__main__":
    search_interface()
