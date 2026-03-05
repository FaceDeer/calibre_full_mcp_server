Each field in a Calibre library will have a datatype defined for the value that can be stored in it. The possible types are:

# text

A `string`.

If a text field has a `separator` character defined in its schema entry then it will be treated as a `list` of strings, with the string being split on the separator character and each list element stripped of terminal whitespace. When updating such a list an agent should use a "merge" strategy rather than a "replace" strategy unless the goal is to purge old data.

# series

Series fields are a `string`, but they always have a companion field whose name is the series field's name with an `_index` suffix appended to it. eg, `#fanfic_series` would have `#fanfic_series_index`. The index is a `float`, allowing for "half-books" or prequels (e.g., 1.5, 0.5).

# rating

An `integer` from 0-10. These are displayed to the user in increments of half a star, so for example a "five star" rating has a value of 10 and a "three and a half star" rating has a value of 7. A value of 0 is typically interpreted as "unrated" or null.

# datetime

Internally Calibre manages dates with a high degree of precision but for most library operations only the year, month, and day are significant. When an agent writes a publication date it should ideally use an ISO 8601 formatted string.

# int

An integer number

# float

A floating-point number

# composite

Composite fields are read-only fields that are built by combining values from other fields using a predefined template.

# enumeration

A `string` whose value is limited to the list of values in the `allowed_values` of its schema entry. The empty string is always an allowed value.

# comments

A multi-line `text` field that often contains markdown or HTML formatting.

# bool

In Calibre bool is ternary, it can be True, False or None. May be displayed to the user in  number of different ways, for example as a checkbox or as Yes/No text.
