## Search kinds (Advanced)

### ‘Equality’ searches

Equality searches are indicated by prefixing the search string with an equals sign (=). For example, the query `tag:"=science"` will match `science`, but not `science fiction` or `hard science`. Character variants are significant: `é` doesn’t match `e`.

Two variants of equality searches are used for hierarchical items (e.g., A.B.C): hierarchical prefix searches and hierarchical component searches. The first, indicated by a single period after the equals (`=.`) matches the initial parts of a hierarchical item. The second, indicated by two periods after the equals (`=..`) matches an internal name in the hierarchical item. Examples, using the tag `History.Military.WWII` as the value:

- `tags:"=.History"` : True. `History` is a prefix of the tag.
- `tags:"=.History.Military"` : True. `History.Military` is a prefix of the tag.
- `tags:"=.History.Military.WWII"` : True. `History.Military.WWII` is a prefix of the tag, albeit an improper one.
- `tags:"=.Military"` : False. `Military` is not a prefix of the tag.
- `tags:"=.WWII"` : False. `WWII` is not a prefix of the tag.
- `tags:"=..History"` : True. The hierarchy contains the value `History`.
- `tags:"=..Military"` : True. The hierarchy contains the value `Military`.
- `tags:"=..WWII"` : True. The hierarchy contains the value `WWII`.
- `tags:"=..Military.WWII"` : False. The `..` search looks for single values.

### ‘Regular expression’ searches

Regular expression searches are indicated by prefixing the search string with a tilde (~). Any [Python-compatible regular expression](https://docs.python.org/library/re.html) can be used. Backslashes used to escape special characters in regular expressions must be doubled because single backslashes will be removed during query parsing. For example, to match a literal parenthesis you must enter `\\(` or alternatively use super-quotes to avoid character escaping entrely (`"""like (this)"""`). Regular expression searches are ‘contains’ searches unless  the expression is anchored. Character variants are significant: `~e` doesn’t match `é`.

### ‘Character variant’ searches

Character variant searches are indicated by prefixing the search string with a caret (^). This search is similar to the basic "contains" search except that punctuation and whitespace are always significant.

The following compares this search to a "contains" search given the same two book titles:

1. `Big, Bothéred, and Bad`
2. `Big Bummer`

then these character variant searches find:

- `title:"^er"` matches both (‘e’ matches both ‘é’ and ‘e’)
- `title:"^g"` matches both
- `title:"^g "` matches #2 because the space is significant
- `title:"^g,"` matches #1 because the comma is significant
- `title:"^gb"` matches nothing because space and comma are significant
- `title:"^g b"` matches #2 because the comma is significant
- `title:"^db"` matches nothing
- `title:"^,"` matches #1 (instead of all books) because the comma is significant