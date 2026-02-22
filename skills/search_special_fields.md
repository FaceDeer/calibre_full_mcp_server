# Special Fields and Identifiers

### Whether a field has a value

You can search for the absence or presence of a value for a field using `true` and `false`. For example:

- `cover:false` finds all books without a cover
- `series:true` finds all books that are in a series
- `series:false` finds all books that are not in a series
- `comments:false` finds all books with an empty comment
- `formats:false` finds all books with no book files (empty records)

### Yes/no custom fields

Searching Yes/no custom fields for `false` will find all books with undefined values in the field. Searching for `true` will find all books that do not have undefined values in the field. Searching for `_yes`  will find all books with `Yes` in the field. Searching for `_no` will find all books with `No` in the field.

### Identifiers

Identifiers (e.g., ISBN, DOI, LCCN, etc.) use an extended syntax. An identifier has the form `type:value`, as in `isbn:123456789`.  The extended syntax permits you to specify independently the type and value to search for. Both the type and the value parts of the query can use any of the search kinds. Examples:

- `identifiers:true` will find books with any identifier.
- `identifiers:false` will find books with no identifier.
- `identifiers:123` will search for books with any type having a value containing 123.
- `identifiers:=123456789` will search for books with any type having a value equal to 123456789.
- `identifiers:=isbn:` and `identifiers:isbn:true` will find books with a type equal to ISBN having any value
- `identifiers:=isbn:false` will find books with no type equal to ISBN.
- `identifiers:=isbn:123` will find books with a type equal to ISBN having a value containing 123.
- `identifiers:=isbn:=123456789` will find books with a type equal to ISBN having a value equal to 123456789.
- `identifiers:i:1` will find books with a type containing an i having a value containing a 1.

### Series indices

Series indices are searchable. For the standard series, the search name is `series_index`. For custom series fields, use the field search name followed by _index. For example, to search the indices for a custom series field named `#my_series`, you would use the search name `#my_series_index`. Series indices are numbers, so you can use the relational operators described above.
