import inverted_index 
import search

def main():

    index, partial_index_files = inverted_index.build_index("/Users/gracysutaria/Documents/UCI/CS_121/DEV")

    unique_tokens = inverted_index.merge_partial_indexes(partial_index_files, "index.txt")
    index.save_documents()

    inverted_index.report(len(index.doc), unique_tokens, "index.txt")

    # Build and save lexicon
    lexicon = inverted_index.build_lexicon("index.txt")


   # Test lexicon
    print("Lexicon entries:", len(lexicon))
    print("Academia offset:", lexicon.get("academia"))

    # Test get_postings()
    postings = inverted_index.get_postings("academia", lexicon, "index.txt")

    # Test search function
    #search.test_search()

    print("\nPostings for 'academia':")
    for posting in postings[:10]:
        print(
            "DocID:", posting.docid,
            "Frequency:", posting.freq,
            "Fields:", posting.fields)
    print("Unique tokens:", unique_tokens)
    print("Lexicon entries:", len(lexicon))
    print("Match:", unique_tokens == len(lexicon)) # should match

if __name__ == "__main__":
    main()