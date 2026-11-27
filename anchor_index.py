# Indexing Anchor Text Main Architecture:
# When we make the main inverted index, we read the data and parse the htmls.
# After we parse the htmls, the anchor index will be created alongside the main index, that way we don't parse docs twice.
# The anchor index will store the target urls and their anchor words. Format: {(target_url, token): count,...,...}
# Need to store urls because the target link might not be indexed/seen yet so we won't know its docid.
# Create partial anchor files and url to docid mapping for future merging w/ main index by docid. 
# After the docs have all been indexed in the main loop, map the anchor url records to their docids.
#       Anchor Record Before: https://example.com   example 3
#       Anchor Record After: example    0000000015  3       where 15 is the docid of the target url
# Note: With removing duplicate/invalid pages implemented, if a target url isn't in the index, their anchor information is discarded as well.
# Then sort and compile the records by token, docid. Counts for same token and docid will be combined.
# Final anchor index file looks like: 
#   example 15:0:{"anchor":3}
#   word    15:0:{"anchor":6}
# Merge anchor postings with main index: 
#   example 15:4:{"title":1, "anchor":3}

import heapq
import json
import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlsplit, urlunsplit

DOCID_WIDTH = 12

# these anchor words are common, but don't provide any real info on the target page
# these shouldn't increase the ranking of the target page
ANCHOR_STOPWORDS = {"click", "here", "read", "more", "link", "page", "next", "previou", "prev"}


class AnchorCollector:
    # collects anchor words, 
    # counts how many words point to a specific url,
    # saves the info to disk

    def __init__(self, batch_size=25000, directory='.'):
        # store anchor word freqs in an empty dictionary
        # { ("url", "word"): freq, ... } where freq is the number of times word was used in an anchor text for url in the corpus
        self.counts = {}

        if batch_size < 1:
            raise ValueError("batch_size must be positive")
    
        self.batch_size = batch_size # batch_size = max num of keys to keep in the dictionary before saving to disk
        self.directory = Path(directory) # default to working directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.files = [] # list to keep track of the partial anchor files we write to

    def add(self, anchors):
        # collect and count anchor words
        # anchors = [ ("url", ["word1", "word2"]), ("url2", ["word1", "word2"]), ]
        for url, words in anchors:
            for word in words:
                key = (url, word)  # URL first: enables disk-based join
                self.counts[key] = self.counts.get(key, 0) + 1 # update the anchor word freqs
                if len(self.counts) >= self.batch_size: # write to file if we reach max
                    self.flush()

    def flush(self):
        # save the anchor words freqs dictionary to file in sorted order
        if not self.counts:
            return
        
        path = self.directory / f'partial_anchors_{len(self.files)}.tsv'
        with open(path, 'w', encoding='utf-8') as f:
            for (url, word), count in sorted(self.counts.items()):
                f.write(f'{url}\t{word}\t{count}\n')
        self.files.append(str(path))
        self.counts.clear() # empty the dict in ram 

    def finish(self):
        # save left over anchors
        self.flush()
        return self.files



def normalize_url(url):
    # make urls follow the same format and are valid

    if not isinstance(url, str): 
        return None  # check if string

    try:
        url, _ = urldefrag(url.strip()) # get rid of fragment (pg. 8 of assignment)
        p = urlsplit(url)   #get parts of url

        if p.scheme.lower() not in ('http', 'https') or not p.hostname: #check valid url
            return None

        # scheme and hostname lower case, remove trailing /, keep query, fragment is empty
        result = urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/') or '/', p.query, ''))

        if any(c in result for c in '\t\r\n'): # newlines, returns and tabs in url not valid
            return None
        
        return result
    
    except ValueError:
        return None

def extract_anchors(soup, source_url, tokenize):
    # get the target url and the anchor text tokens

    source = normalize_url(source_url)

    if source is None:
        return
    
    for tag in soup.find_all('a', href=True): # find all links in the doc
        href = tag['href'].strip() # get target link

        # skip empty links, links that link to another section of the same page, and links that execute something (email, call, etc)
        if not href or href.lower().startswith(('#', 'mailto:', 'javascript:', 'tel:')):
            continue

        try:
            target = normalize_url(urljoin(source_url, href)) # get full link 
        except ValueError:
            continue

        if target is None or target == source:
            continue
        # get each token in the anchor text
        words = [w for w in tokenize(tag.get_text(' ', strip=True)) if w not in ANCHOR_STOPWORDS]
        if words:
            yield target, words  # produces ("targeturl", ["word1", "word2"])


def _sort_file_in_chunks(source, tmpdir, batch_size=25000):
    # External sort of lines. each batch holds at most batch_size lines .
    # read in small batches, sort it, save to new file
    paths = [] # tmp files tracker

    with open(source, 'r', encoding='utf-8') as src:
        while True:
            lines = [] # holds the current batch of dict lines to sort
            for _ in range(batch_size): # only read up to 25000 lines at a time
                line = src.readline()
                if not line:
                    break
                lines.append(line)
            if not lines:
                break
            lines.sort() # sort alphabetically -> same target urls are together
            path = Path(tmpdir) / f'sort_{len(paths)}.tsv' # save to tmp files. temp/sort_1.tsv
            with open(path, 'w', encoding='utf-8') as out:
                out.writelines(lines)
            paths.append(str(path))
    return paths


def _merge_sorted_files(paths, output, tmpdir, fan_in=32):
    # merge the sorted files into one w/o loading all into RAM 
    # -> fan_in ctrls how many can be merged at once
    if fan_in < 2:
        raise ValueError("fan_in must be >= 2")
    
    paths = list(paths)
    step = 0 # tracks how many rounds of merging were done

    # if no input files to be merged, return empty output file
    if not paths:
        Path(output).write_text('', encoding='utf-8')
        return
    
    while len(paths) > 1: # merge until 1 file is left. last file will be finished one when loop ends
        merged_paths = [] # holds new merged files

        # merge by fan_in sized groups at a time
        for i in range(0, len(paths), fan_in):
            group = paths[i:i + fan_in]
            dest = str(Path(tmpdir) / f'merge_{step}_{i}.tsv') # temp/merge_0_2.tsv 
            # ExitStack() is used to manage multiple open files
            with ExitStack() as stack: 
                # open the files in the batch for reading
                inputs = [stack.enter_context(open(p, 'r', encoding='utf-8')) for p in group]
                with open(dest, 'w', encoding='utf-8') as out:
                    # heaps only keep track of the next lowest item from each input file and merges them in order.
                    # doesn't load all contents
                    out.writelines(heapq.merge(*inputs))
            merged_paths.append(dest)
        
        paths = merged_paths # update the list of files to be merged with the new ones to continue merging
        step += 1
    
    Path(paths[0]).replace(output) # move the final file out of the temp directory


def build_anchor_index(partial_anchor_files, url_doc_file='url_doc_map.tsv',
                       output_file='anchor_index.txt', batch_size=25000):
    """URL join + second external sort + aggregation. No json.load(doc.json)."""
    with tempfile.TemporaryDirectory(prefix='anchor_sort_') as tmp:
        # Sort URL -> docid map on disk.
        map_chunks = _sort_file_in_chunks(url_doc_file, tmp, batch_size)
        sorted_map = str(Path(tmp) / 'sorted_map.tsv')
        _merge_sorted_files(map_chunks, sorted_map, tmp)

        # Each anchor partial is sorted by (URL, token). Merge on disk.
        sorted_anchors = str(Path(tmp) / 'sorted_anchors.tsv')
        _merge_sorted_files(partial_anchor_files, sorted_anchors, tmp)

        # Streaming merge join on URL. Emit (token, zero-padded docid, count).
        resolved = str(Path(tmp) / 'resolved.tsv')
        with open(sorted_map, 'r', encoding='utf-8') as mapping, \
             open(sorted_anchors, 'r', encoding='utf-8') as anchors, \
             open(resolved, 'w', encoding='utf-8') as out:
            map_line = mapping.readline()
            map_url = map_line.split('\t', 1)[0] if map_line else None
            for line in anchors:
                url, token, count = line.rstrip('\n').split('\t', 2)
                while map_url is not None and map_url < url:
                    map_line = mapping.readline()
                    map_url = map_line.split('\t', 1)[0] if map_line else None
                if map_url == url:
                    # If several accepted documents have the same URL, use first docid.
                    docid = map_line.rstrip('\n').split('\t', 1)[1]
                    out.write(f'{token}\t{docid}\t{count}\n')

        # Sorting by token/docid is REQUIRED: URL order != docid order.
        resolved_chunks = _sort_file_in_chunks(resolved, tmp, batch_size)
        sorted_resolved = str(Path(tmp) / 'sorted_resolved.tsv')
        _merge_sorted_files(resolved_chunks, sorted_resolved, tmp)

        # Aggregate consecutive (token, docid) pairs; stream output postings.
        with open(sorted_resolved, 'r', encoding='utf-8') as src, \
             open(output_file, 'w', encoding='utf-8') as out:
            prev = None
            total = 0
            current_token = None

            def emit(key, count):
                nonlocal current_token
                if key is None:
                    return
                token, padded_docid = key
                if token != current_token:
                    if current_token is not None:
                        out.write('\n')
                    out.write(token)
                    current_token = token
                out.write(f' {int(padded_docid)}:0:{{"anchor":{count}}}')

            for line in src:
                token, padded_docid, count = line.rstrip('\n').split('\t', 2)
                key = (token, padded_docid)
                if prev is not None and key != prev:
                    emit(prev, total)
                    total = 0
                prev = key
                total += int(count)
            emit(prev, total)
            if current_token is not None:
                out.write('\n')
    return output_file


def iter_index_postings(path, block_size=65536):
    """Yield (token, docid, freq, fields), never reading a whole token line."""
    with open(path, 'rb') as f:
        word = bytearray()
        expect_token = True
        token = None
        while True:
            block = f.read(block_size)
            if not block:
                break
            for b in block:
                if b not in (10, 32):  # newline, space
                    word.append(b)
                    continue
                if word:
                    value = word.decode('utf-8')
                    word.clear()
                    if expect_token:
                        token = value
                        expect_token = False
                    else:
                        docid, freq, fields = value.split(':', 2)
                        yield token, int(docid), int(freq), json.loads(fields)
                if b == 10:
                    expect_token = True
        if word and not expect_token:
            docid, freq, fields = word.decode('utf-8').split(':', 2)
            yield token, int(docid), int(freq), json.loads(fields)


def write_index_postings(rows, output_file):
    """Write sorted posting stream in existing one-line-per-token format."""
    current_token = None
    unique = 0
    with open(output_file, 'w', encoding='utf-8') as out:
        for token, docid, freq, fields in rows:
            if token != current_token:
                if current_token is not None:
                    out.write('\n')
                out.write(token)
                current_token = token
                unique += 1
            out.write(f' {docid}:{freq}:{json.dumps(fields, separators=(",", ":"))}')
        if current_token is not None:
            out.write('\n')
    return unique


def merge_main_partials(partial_files, output_file, fan_in=32):
    """Streaming k-way merge for main index; bounded open files and postings."""
    if fan_in < 2:
        raise ValueError("fan_in must be >= 2")
    with tempfile.TemporaryDirectory(prefix='main_merge_') as tmp:
        paths = list(partial_files)
        pass_num = 0
        if not paths:
            return write_index_postings((), output_file)
        while len(paths) > fan_in:
            next_paths = []
            for i in range(0, len(paths), fan_in):
                dest = str(Path(tmp) / f'main_{pass_num}_{i}.txt')
                streams = [iter_index_postings(p) for p in paths[i:i + fan_in]]
                rows = heapq.merge(*streams, key=lambda x: (x[0], x[1]))
                write_index_postings(rows, dest)
                next_paths.append(dest)
            paths = next_paths
            pass_num += 1
        streams = [iter_index_postings(p) for p in paths]
        return write_index_postings(
            heapq.merge(*streams, key=lambda x: (x[0], x[1])), output_file
        )


def merge_anchor_with_main(main_file, anchor_file, output_file='index.txt'):
    if os.path.abspath(output_file) in (os.path.abspath(main_file), os.path.abspath(anchor_file)):
        raise ValueError('Output must differ from both input files')
    main = iter(iter_index_postings(main_file))
    anchors = iter(iter_index_postings(anchor_file))
    a = next(main, None)
    b = next(anchors, None)

    def merged():
        nonlocal a, b
        while a is not None or b is not None:
            if b is None or (a is not None and (a[0], a[1]) < (b[0], b[1])):
                yield a
                a = next(main, None)
            elif a is None or (b[0], b[1]) < (a[0], a[1]):
                yield b
                b = next(anchors, None)
            else:
                token, docid, freq, fields = a
                for field, count in b[3].items():
                    fields[field] = fields.get(field, 0) + count
                yield token, docid, freq, fields
                a = next(main, None)
                b = next(anchors, None)

    return write_index_postings(merged(), output_file)