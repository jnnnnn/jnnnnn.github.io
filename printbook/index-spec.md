# Automated Index Generator for epub2print

All python must be written to a file and run using `uv run`, do not use inline commands.

## Goal

Automatically generate a back-of-book index for any EPUB, using the
`in-dexter` Typst package. The index should surface what's *actually
interesting* in the book — the sexy parts of a romantasy, the unusual
vocabulary in non-fiction, the key characters and places in a novel.

## Architecture — unified two-pass

All scored index entries (proper nouns and rare words) use a
**collect-then-select** approach. Scene markers and chapter titles
remain single-pass (they're structural and cheap).

```
Pass 1  EPUB → EPUBParser → Typst source (scene/chapter markers only)
        ├ IndexTracker._check_proper_noun() records noun candidates
        ├ IndexTracker.collect_word() records rare word candidates
        └ annotate_text() returns escaped text UNCHANGED (no inline markers)

Score   After all chapters:
        ├ Score proper nouns: rarity × spread
        ├ Score rare words:  rarity × usedness × spread
        ├ Deduplicate (same lowercase → keep higher score)
        ├ Combine, sort, select top N (--index-size)
        └ Print full scored list with cutoff indicator

Pass 2  Post-process Typst source to insert #index[] for ALL selected
        entries (both nouns and rare words, same regex approach)
```

### Why two passes?

A single pass can't know which words are "best" until the entire book
is scanned. Early chapters would eat the budget. Two passes let us
score globally and allocate evenly.

This now applies to **proper nouns too** — they're collected during
pass 1 but markers are inserted during pass 2, just like rare words.
This eliminates the need for `_PROPER_NOUN_ZIPF_CEILING`; scoring
naturally ranks real character names above common words like Goodbye.

### Word cleaning

All word extraction uses a shared `_clean_word(raw)` helper that:

1. Strips leading/trailing apostrophes and curly quotes (`'`, `\u2019`)
2. Strips possessive suffixes: `'s`, `\u2019s` → removed
3. Strips contraction suffixes: `'d`, `'ll`, `'ve`, `'re`, `'t`
   (and their curly-quote equivalents) → removed
4. Returns the cleaned base word (e.g. `Sorcha's` → `Sorcha`,
   `It'd` → `It`, `I'll` → `I`, `Everything's` → `Everything`)

This ensures possessives and contractions are normalized to their base
form before any indexing decision. Words that clean down to < 3 chars
(e.g. `I'll` → `I`) are skipped.

### Noise filtering

`_clean_word` strips contraction suffixes, but the **residual fragment**
(e.g. `Hadn` from `Hadn't`, `Couldn` from `Couldn't`) is not a real
word. These fragments have low zipf scores (Hadn=2.12, Couldn=2.74)
and would otherwise be collected as rare word candidates.

**Contraction fragment filter** (in `collect_word`):
Before calling `_clean_word`, check if the raw token (after edge-quote
stripping) ends with a contraction-only suffix (`'t`, `'d`, `'ll`,
`'ve`, `'re`). If so, skip the word entirely — any cleaned residual
is a meaningless fragment.

```python
stripped = raw_word.strip("'\u2019")
for suffix in _CONTRACTION_ONLY_SUFFIXES:
    if stripped.endswith(suffix):
        return  # contraction fragment, not a real word
```

**Internal apostrophe filter** (in `_check_proper_noun`):
After all stripping, check `word.isalpha()`. Words with internal
apostrophes (e.g. `C'mon`) are skipped. This also filters contractions
like `y'all`. (Names like O'Brien are sacrificed; these are rare and
can be added manually if needed.)

**Affected words and their dispositions:**

| Token      | `_clean_word` | zipf  | Old behavior       | New behavior      |
|-----------|--------------|-------|--------------------|-------------------|
| Hadn't    | Hadn          | 2.12  | ❌ collected as rare | ✅ skipped (contraction) |
| Couldn't  | Couldn        | 2.74  | ❌ collected as rare | ✅ skipped (contraction) |
| C'mon     | C'mon         | 3.75  | ❌ noun candidate   | ✅ skipped (not alpha)   |
| Goodbye   | Goodbye       | 4.30  | ❌ indexed as noun  | ✅ scored low, excluded  |

### IndexTracker class

Holds all indexing state across the book:

- `noun_candidates: dict[str, set[int]]` — word → {chapter_idxs}
  where word appeared mid-sentence in title-case
- `noun_chapter_seen: set[str]` — per-chapter dedup for noun collection
- `rare_candidates: list[CandidateWord]` — every rare word occurrence
- `stem_counts: dict[str, Counter[str]]` — stem → {surface_form: count}

```python
@dataclass
class CandidateWord:
    word: str           # original surface form (e.g. "gossamer")
    lower: str          # lowered form
    stem: str           # snowball-stemmed form
    zipf: float         # wordfreq zipf_frequency score (0–8)
    chapter_idx: int    # which chapter it appeared in
    position: int       # character offset in un-escaped text
```

Methods:
- `new_chapter()` — resets per-chapter noun dedup, increments chapter idx
- `check_scene_signals(plain_text: str) -> list[str]`
- `collect_word(word, pos, full_text)` — records a CandidateWord if it
  passes basic filters (alpha, 4+ chars, not a contraction fragment)
- `_check_proper_noun(word, pos, text)` — records noun candidate if
  title-case mid-sentence, alpha, has vowel. No zipf ceiling.
- `annotate_text(text, escaped) -> str` — collects candidates only,
  returns escaped text **unchanged** (no inline insertion)
- `select_all(budget) -> tuple[dict, list]` — scores all candidates,
  returns (selected_dict, full_scored_list_for_printing)
- `heading_marker(title) -> str` — `#index(fmt: strong, [title])`

### Unified scoring

After all chapters are processed, `select_all(budget)`:

1. **Score rare words** (grouped by stem):
   ```
   rarity  = max(0, 4.0 − zipf_frequency(display_word, 'en'))
   spread  = number of distinct chapters containing this stem
   count   = total occurrences of this stem
   usedness = min(log2(count + 1), 3.0)   # caps at ~8 occurrences
   score   = rarity × usedness × (1 + 0.2 × min(spread, 5))
   ```

2. **Score proper nouns** (no stemming):
   ```
   rarity  = max(0, 5.0 − zipf_frequency(word, 'en'))
   spread  = number of distinct chapters where word appeared mid-sentence
   score   = rarity × (1 + 0.2 × min(spread, 5))
   ```
   The wider rarity range (5.0 vs 4.0) reflects that character names
   can have moderate zipf values (Phoenix=4.21, Kira=3.21) while still
   being interesting. Words with zipf ≥ 5.0 (War=5.46, King=5.17)
   score 0 and are excluded.

3. **Deduplicate**: if the same lowercase word appears in both pools,
   keep the entry with the higher score.

4. **Select top N**: Sort combined list by score descending, take
   top `budget` entries (configurable via `--index-size`, default 120).

5. **Print scored list**: Print ALL scored entries to stdout with
   a cutoff indicator showing which are selected vs excluded.

6. **Return**: `{lower_word: (DisplayForm, {chapter_indices})}` for
   the selected entries. Proper nouns are capped at 3 chapters each.

**Example scores:**

| Word      | Type | Zipf | Spread | Score | Selected? |
|-----------|------|------|--------|-------|-----------|
| Sorcha    | noun | 1.82 |     10 | 9.54  | ✅        |
| Gossamer  | word | 2.44 |      4 | 8.42  | ✅        |
| Kira      | noun | 3.21 |      5 | 3.58  | ✅        |
| Phoenix   | noun | 4.21 |      3 | 1.26  | maybe     |
| Goodbye   | noun | 4.30 |      2 | 0.98  | ❌        |
| War       | noun | 5.46 |      5 | 0.00  | ❌        |

### Post-processing Typst for selected entries

After `select_all()` returns the winners, scan each chapter's Typst
content. For each selected entry (noun or rare word), find its **first
occurrence** in that chapter using word-boundary regex and insert
`#index[Word]` after it. Only mark the first occurrence per chapter,
and only in chapters where the word actually appeared.

For proper nouns: cap at 3 chapters per noun (first 3 in reading
order). For rare words: mark in all chapters where seen.

The regex must avoid matching inside Typst commands, comments, or
already-inserted `#index[...]` markers. Pattern:

```python
# Match the word at a word boundary, not inside #index[...]
pattern = rf'(?<![#\[])(\b{re.escape(word)}\b)(?![^\[]*\])'
```

## What gets indexed

### Tier 1 — Proper nouns (two-pass, scored)

Capitalized words mid-sentence (not after `.!?:;—…` or start of para).
Almost always character names, place names, organizations.

- Collected during pass 1, scored and selected with rare words
- Min length: 3 characters (after cleaning — see Word cleaning above)
- Must be alphabetic (no internal apostrophes — filters C'mon)
- Must contain at least one vowel (filters Mmhmm, Pfft, Hmph)
- No hard zipf ceiling; scoring naturally excludes common words
- Cap: index a noun in at most **3 chapters** (applied during selection)

### Tier 2 — Rare/unusual words (two-pass)

Words that are **uncommon in general English** per `wordfreq`.

Collection filter (pass 1 — cheap, casts a wide net):
- Alphabetic only, 4+ characters (after cleaning)
- `zipf_frequency(word, 'en') < 4.0` (anything ≥ 4 is too common)
- Not a contraction fragment (see Noise filtering above)

Selection filter (pass 2 — after scoring):
- Combined with proper nouns, top N by score (--index-size)
- Display form: most frequent surface variant in the stem group

This catches: fantasy terminology, technical jargon, archaic words,
foreign phrases, invented words, unusual adjectives.

### Tier 3 — Scene/mood markers (single-pass, during generation)

Unchanged. Scan paragraphs for clusters of signal words.
When ≥3 hit within one paragraph → `#index("Scenes", "Intimate")`.

### Tier 4 — Chapter titles (single-pass, during generation)

Unchanged. `#index(fmt: strong, [Chapter Title])` after headings.

## Budget

Target: **≤ 2 index pages** (2-column, 8pt text).

| Category            | Budget     | Notes                           |
|--------------------|------------|----------------------------------|
| Scored entries      | 120 (configurable) | Nouns + rare words combined |
| Scenes              | ~10–30     | Only on high-signal paragraphs  |
| Chapters            | ~20–50     | One per chapter                 |
| **Total**           | ~150–200   | Fits comfortably in 2 pages     |

The `--index-size N` flag controls the scored entry budget (default 120).
Users can increase for comprehensive indices or decrease for minimal ones.

## in-dexter integration

Package: `in-dexter` v0.7.2.

```typst
#import "@preview/in-dexter:0.7.2": *
```

Inline markers:

```typst
Kira#index[Kira] walked through the Silverwood#index[Silverwood] forest.
```

Scene markers at paragraph start:

```typst
#index("Scenes", "Intimate")
His breath caught as she...
```

Index page at end:

```typst
#pagebreak()
= Index
#set text(size: 8pt)
#columns(2)[
  #make-index(title: none)
]
```

## Safety: avoiding broken Typst

`#index[word]` must NEVER be inserted where it would break Typst
syntax. Known failure modes:

1. **Inside email/URL**: `gmail#index[gmail].com` → Typst reads `.com`
   as field access. **Fix**: skip words adjacent to `.` `@` `/` in the
   source text.

2. **Inside existing Typst commands**: the post-processing regex must
   not match inside `#command[...]` blocks or `//` comments.

3. **Special characters in word**: if the display form contains `[`,
   `]`, `#`, etc., escape or skip it.

## Dependencies

Add `wordfreq` and `nltk` to the uv script metadata:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fonttools",
#     "lxml",
#     "nltk",
#     "pillow",
#     "pypdf",
#     "wordfreq",
# ]
# ///
```

- **wordfreq** (v3.1, ~30MB installed): `zipf_frequency(word, 'en')`
  returns 0–8 scale. Self-contained, no downloads needed. Replaces
  `common_words.py` entirely.
- **nltk** (SnowballStemmer only): `SnowballStemmer('english').stem(w)`.
  The stemmer is pure Python, built into the nltk package — no
  `nltk.download()` needed.

`common_words.py` can be deleted after migration.

## CLI

```
uv run epub2print.py mybook.epub --index
uv run epub2print.py mybook.epub --index --index-size 80    # smaller index
uv run epub2print.py mybook.epub --index --index-size 200   # larger index
```

### Printed scored list

When `--index` is used, the full scored list is printed to stdout
after scoring, showing every candidate with its score, type, zipf,
and chapter spread. A cutoff line shows which entries are selected.

```
Index: 227 candidates scored, selecting top 120
  Score  Cat   Word            Zipf  Chapters
   9.54  noun  Sorcha          1.82  10
   8.42  word  Gossamer        2.44  4
   3.58  noun  Kira            3.21  5
   ...
   1.50  word  Archaic         3.12  1
  ---- index-size cutoff (120) ----
   0.98  noun  Goodbye         4.30  2
   0.00  noun  War             5.46  5
   ...
```

This lets the user see exactly what's included/excluded and tune
`--index-size` accordingly.

## Constraints

- No LLM / API dependency — fully offline
- Must not break existing non-index workflow
- Index should add ≤ 2 pages to a typical novel
- Performance: < 2 seconds for a 100k-word book (wordfreq lookups are
  fast hash-table reads; stemmer is pure Python)
- Don't index inside footnotes

## Code structure

The indexing code lives in `epub2print.py` alongside the EPUB parser
and Typst generator. Key components:

- **`_clean_word(raw: str) -> str`** — module-level helper. Strips
  possessives, contractions, edge quotes. Used by both
  `_check_proper_noun` and `collect_word`.
- **`_CONTRACTION_ONLY_SUFFIXES`** — tuple of contraction endings
  (excluding possessive `'s`) used to detect fragments.
- **`CandidateWord`** — dataclass for pass-1 collection.
- **`IndexTracker`** — stateful class instantiated once per book.
  Collects both noun and rare word candidates during pass 1.
  Scores and selects via `select_all(budget)`.
- **`postprocess_index_markers()`** — module-level function for pass 2.
  Takes chapters + selected entries, modifies chapter content in place.
- **`print_index_scores()`** — prints the full scored list to stdout.

