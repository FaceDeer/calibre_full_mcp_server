# Search Structure & Syntax

## Search Expression Syntax

A search expression is a sequence of search terms optionally separated by the operators `and` and `or`. If two search terms occur without a separating operator, `and` is assumed. The `and` operator has priority over the `or` operator; for example the expression `a or b and c` is the same as `a or (b and c)`. You can use parenthesis to change the priority; for example `(a or b) and c` to make the `or` evaluate before the `and`. You can use the operator `not` to negate (invert) the result of evaluating a search expression. Examples:

- `not tag:foo` finds all books that don’t contain the tag `foo`
- `not (author:Asimov or author:Weber)` finds all books not written by either Asimov or Weber.

The above examples show examples of search terms. A basic search term is a sequence of characters not including spaces, quotes (`"`), backslashes (`\`), or parentheses (`( )`). It can be optionally preceded by a field name specifier: the lookup name of a field followed by a colon (`:`), for example `author:Asimov`. If a search term must contain a space then the entire term must be enclosed in quotes, as in `title:"The Ring"`. If the search term must contain quotes then they must be escaped with backslashes. For example, to search for a series named *The “Ball” and The “Chain”*, use: `series:"The \"Ball\" and The \"Chain\"`

If you need an actual backslash, something that happens frequently in regular expression searches, use two of them (`\\`).

It is sometimes hard to get all the escapes right so the result is what you want, especially in regular expression and template searches. In these cases use the super-quote: `"""sequence of characters"""`. Super-quoted characters are used unchanged: no escape processing is done.

### More information

To search for a string that begins with an equals, tilde, or caret; prefix the string with a backslash.

Enclose search strings with quotes (”) if the string contains parenthesis or spaces. For example, to find books with the tag `Science Fiction` you must search for `tag:"=science fiction"`. If you search for `tag:=science fiction` you will find all books with the tag `science` and the word `fiction` in any metadata.

Available fields for searching are: `tag`, `title`, `author`, `publisher`, `series`, `series_index`, `rating`, `cover`, `comments`, `format`, `identifiers`, `date`, `pubdate`, `search`, `size`, `vl` and any custom fields (fields beginning with `#`).
