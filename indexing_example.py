"""Example indexing flow; integrate into existing main.py instead of replacing search logic."""
import time

from inverted_index import build_index, merge_partial_indexes, build_lexicon, report
from anchor_index import build_anchor_index, merge_anchor_with_main


def run_indexing(folder='DEV'):
    total_start = time.perf_counter()

    print("Starting document indexing...", flush=True)
    start = time.perf_counter()

    index, partial_main, partial_anchors = build_index(folder)

    print(f"Document indexing finished in {time.perf_counter() - start:.1f}s", flush=True)
    print(f"Indexed documents: {len(index.doc):,}", flush=True)
    print(f"Main partial files: {len(partial_main)}", flush=True)
    print(f"Anchor partial files: {len(partial_anchors)}", flush=True)

    print("\nMerging main index...", flush=True)
    start = time.perf_counter()
    merge_partial_indexes(partial_main, 'index_base.txt')
    print(f"Main merge finished in {time.perf_counter() - start:.1f}s", flush=True)

    print("\nBuilding anchor index...", flush=True)
    start = time.perf_counter()
    build_anchor_index(partial_anchors, 'url_doc_map.tsv', 'anchor_index.txt')
    print(f"Anchor indexing finished in {time.perf_counter() - start:.1f}s", flush=True)

    print("\nMerging anchor and main indexes...", flush=True)
    start = time.perf_counter()
    unique_tokens = merge_anchor_with_main(
        'index_base.txt', 'anchor_index.txt', 'index.txt'
    )
    print(f"Final merge finished in {time.perf_counter() - start:.1f}s", flush=True)

    print("\nBuilding lexicon...", flush=True)
    start = time.perf_counter()
    build_lexicon('index.txt')
    print(f"Lexicon finished in {time.perf_counter() - start:.1f}s", flush=True)

    report(len(index.doc), unique_tokens, 'index.txt')

    print(f"\nTOTAL RUNTIME: {time.perf_counter() - total_start:.1f}s", flush=True)


if __name__ == '__main__':
    run_indexing()