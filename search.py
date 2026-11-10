from inverted_index import tokenize, get_postings, Posting

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


# def test_intersect():
#     postings1 = [Posting(1, 1, {}), Posting(2, 2, {}), Posting(3, 1, {})]
#     postings2 = [Posting(1, 1, {}), Posting(2, 2, {}), Posting(3, 1, {}), Posting(4, 4, {})]
#     print(intersect(postings1, postings2))

# test_intersect()