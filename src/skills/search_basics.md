# Basic Search Queries

You can search all book metadata by entering search terms in the `search_books` query parameter. For example:

- `Asimov Foundation format:lrf`

This will match all books that have `Asimov` and `Foundation` in their metadata and are available in the `LRF` format. Some more examples:

- `author:Asimov and not series:Foundation`
- `title:"The Ring" or "This book is about a ring"`
- `format:epub publisher:feedbooks.com`

## Search kinds

There are four search kinds: *contains,* *equality*, *regular expression*, and *character variant*. You choose the search kind with a prefix character.

### ‘Contains’ searches

Searches with no prefix character are contains and are case insensitive. An item matches if the search string appears anywhere in the indicated metadata. A character will match all its variants (e.g., e matches é, è, ê, and ë) and all punctuation and whitespace are ignored. For example, given the two book titles:

1. `Big, Bothéred, and Bad`
2. `Big Bummer`

then these searches find:

- `title:"er"` matches both (‘e’ matches both ‘é’ and ‘e’).
- `title:"g "` matches both because spaces are ignored.
- `title:"g,"` matches both because the comma is ignored.
- `title:"gb"` matches both because ‘, ‘ is ignored in book 1 and spaces are ignored in book 2.
- `title:"g b"` matches both because comma and space are ignored.
- `title:"db"` matches #1 because the space in ‘and Bad’ is ignored.
- `title:","` matches both (it actually matches all books) because commas are ignored.
