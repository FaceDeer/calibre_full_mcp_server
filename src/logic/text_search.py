import re
import logging
from nltk.stem import PorterStemmer
from collections import defaultdict

def _find_fts_matches(text, query, window_size=500):
    logging.debug(f"_find_fts_matches called for text of length '{len(text)}' and query '{query}' and window_size '{window_size}'")
    stemmer = PorterStemmer()
    query_words = re.findall(r'\w+', query.lower())
    query_stems = list(set(stemmer.stem(w) for w in query_words))
    num_terms = len(query_stems)
    
    # 1. Extract all "Candidate Hits" for any of the query stems
    # We store them as: (start_pos, end_pos, stem)
    candidates = []
    for match in re.finditer(r'\w+', text):
        stem = stemmer.stem(match.group().lower())
        if stem in query_stems:
            candidates.append({
                'start': match.start(),
                'end': match.end(),
                'stem': stem
            })

    # 2. Sliding Window Logic
    results = []
    counts = defaultdict(int)
    unique_stems_in_window = 0
    left = 0
    
    for right in range(len(candidates)):
        # Add the right-most candidate to our current window
        stem_r = candidates[right]['stem']
        if counts[stem_r] == 0:
            unique_stems_in_window += 1
        counts[stem_r] += 1
        
        # While the window contains ALL query stems, try to shrink it from the left
        while unique_stems_in_window == num_terms:
            # Calculate the current span
            span_start = candidates[left]['start']
            span_end = candidates[right]['end']
            
            # If the span is within our maximum allowed character distance
            if (span_end - span_start) <= window_size:
                results.append((span_start, span_end))
            
            # Shrink the window from the left to find a tighter match or move on
            stem_l = candidates[left]['stem']
            counts[stem_l] -= 1
            if counts[stem_l] == 0:
                unique_stems_in_window -= 1
            left += 1

    # 3. Clean up: Merge overlapping or adjacent results
    if not results:
        logging.debug("_find_fts_matches returning empty results")
        return []
    
    results.sort()
    merged = [results[0]]
    for current_start, current_end in results[1:]:
        last_start, last_end = merged[-1]
        # If the new match overlaps or is very close to the last one, merge them
        if current_start <= last_end:
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))
    
    logging.debug(f"_find_fts_matches returning merged results of length {len(merged)}")
    return merged