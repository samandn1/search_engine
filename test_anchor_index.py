
"""Run: python test_anchor_index.py (uses temporary synthetic DEV pages)."""

import json
import os
import tempfile
from pathlib import Path

import sys
import types

sys.modules.setdefault(
    "duplicates",
    types.SimpleNamespace(DuplicateDetector=lambda: None)
)

import inverted_index
from anchor_index import iter_index_postings, normalize_url


class FakeDetector:
    exact_dups = 0
    near_dups = 0

    def is_duplicate(self, tokens, token_counts):
        return False


def test_pipeline():
    inverted_index.duplicates.DuplicateDetector = FakeDetector

    old = Path.cwd()

    with tempfile.TemporaryDirectory() as td:
        os.chdir(td)

        try:
            dev = Path("DEV")
            dev.mkdir()

            # Six test documents
            pages = [
                # Document 1: Multiple links to document 2
                (
                    "https://example.org/a",
                    '<title>Alpha</title>'
                    '<a href="/b">Computer Science</a>'
                    '<a href="/b/">Computer Research</a>'
                ),

                # Document 2: Links back to document 1
                (
                    "https://example.org/b",
                    '<h1>Science</h1>'
                    '<a href="/a">Research Computer</a>'
                ),

                # Document 3: Links to documents 1 and 2
                (
                    "https://example.org/c",
                    '<a href="/a">Research</a>'
                    '<a href="/b">Science</a>'
                ),

                # Document 4: External link
                (
                    "https://example.org/d",
                    '<a href="https://google.com">Search Engine</a>'
                ),

                # Document 5: Self-link
                (
                    "https://example.org/e",
                    '<a href="/e">Self Link</a>'
                ),

                # Document 6: Link to nonexistent document
                (
                    "https://example.org/f",
                    '<a href="/missing">Missing Page</a>'
                )
            ]

            # Create synthetic DEV JSON files
            for i, (url, content) in enumerate(pages, 1):
                (dev / f"{i}.json").write_text(
                    json.dumps({
                        "url": url,
                        "content": content
                    }),
                    encoding="utf-8"
                )

            from anchor_index import (
                build_anchor_index,
                merge_anchor_with_main
            )

            # Small batches force multiple partial files
            idx, main_parts, anchor_parts = inverted_index.build_index(
                "DEV",
                offload=1,
                anchor_batch_size=2
            )

            assert len(main_parts) == 6
            assert len(anchor_parts) >= 2

            # Merge main partial indexes
            inverted_index.merge_partial_indexes(
                main_parts,
                "index_base.txt"
            )

            # Build anchor index
            build_anchor_index(
                anchor_parts,
                "url_doc_map.tsv",
                "anchor_index.txt",
                batch_size=2
            )

            print("\n===== URL TO DOCID MAPPING =====")
            with open("url_doc_map.tsv", "r") as f:
                print(f.read())

            print("\n===== ANCHOR INDEX =====")
            with open("anchor_index.txt", "r") as f:
                print(f.read())

            # Merge main and anchor indexes
            count = merge_anchor_with_main(
                "index_base.txt",
                "anchor_index.txt",
                "index.txt"
            )

            print("\n===== FINAL INVERTED INDEX =====")
            with open("index.txt", "r") as f:
                print(f.read())

            # Build lexicon
            lexicon = inverted_index.build_lexicon("index.txt")

            assert count == len(lexicon)

            # Read final postings
            postings = {
                (token, docid): (freq, fields)
                for token, docid, freq, fields
                in iter_index_postings("index.txt", block_size=7)
            }

            # TEST 1: Multiple links to document 2
            assert postings[("comput", 2)][1]["anchor"] == 2
            assert postings[("scienc", 2)][1]["anchor"] == 2
            assert postings[("research", 2)][1]["anchor"] == 1

            print("PASS: multiple links aggregate correctly")

            # TEST 2: Links to document 1
            assert postings[("research", 1)][1]["anchor"] == 2
            assert postings[("comput", 1)][1]["anchor"] == 1

            print("PASS: incoming links assigned to correct document")

            # TEST 3: External links are excluded as targets
            assert not any(
                token == "search" and fields.get("anchor", 0) > 0
                for (token, docid), (freq, fields) in postings.items()
            )

            print("PASS: external target excluded")

            # TEST 4: Self-links should not contribute anchor counts
            assert postings[("self", 5)][1].get("anchor", 0) == 0
            assert postings[("link", 5)][1].get("anchor", 0) == 0

            print("PASS: self-links excluded")

            # TEST 5: Missing target
            assert not any(
                token == "miss" and fields.get("anchor", 0) > 0
                for (token, docid), (freq, fields) in postings.items()
            )

            print("PASS: missing target excluded")

            # TEST 6: Every posting has a valid docID
            with open("doc.json", "r") as f:
                documents = json.load(f)

            valid_docids = {int(docid) for docid in documents}

            for token, docid in postings:
                assert docid in valid_docids, (
                    f"Invalid docID {docid} for token {token}"
                )

            print("PASS: all postings reference valid documents")

            # TEST 7: URL normalization
            assert normalize_url(
                "https://example.org/b/"
            ) == normalize_url(
                "https://example.org/b"
            )

            print("PASS: URL normalization")

            # TEST 8: Lexicon and postings retrieval
            assert any(
                p.docid == 2
                for p in inverted_index.get_postings(
                    "comput", lexicon, "index.txt"
                )
            )

            print("PASS: lexicon and postings retrieval")

            print("\nALL 6-DOCUMENT TESTS PASSED!")

        finally:
            os.chdir(old)


if __name__ == "__main__":
    test_pipeline()
