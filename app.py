import time
import json
import streamlit as st
import inverted_index
import search


st.title('Search Engine')

# can use the st.cache_resource decorator: works like a cache
# - the same query doesn't have to load every time
@st.cache_resource
def load_engine():
    # Build and save lexicon
    with open('lexicon.json', 'r', encoding='utf-8') as f:
        lexicon = json.load(f) 
    with open('doc.json', 'r', encoding='utf-8') as f:
        doc_urls = json.load(f)
    with open('doc_length.json', 'r', encoding='utf-8') as f:
        doc_lengths = json.load(f)
    return lexicon, doc_urls, doc_lengths


lexicon, doc_urls, doc_lengths = load_engine()

query = st.text_input('Search:', placeholder='Search...')
if query:
    results = search.search(query, lexicon, 'index.txt', len(doc_urls), doc_lengths)
    st.caption(f'Found {len(results)} results for "{query}"')

    for r in results:
        st.markdown(f'[{r["title"]}]({r["url"]})')
        st.caption(f'{r["url"]}: score: {r["score"]}')
    #st.write(f'Searching for: {query}') 