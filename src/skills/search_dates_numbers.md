# Searching Dates and Numbers

### Dates

The syntax for searching for dates is:

- `pubdate:>2000-1` Will find all books published after Jan, 2000
- `date:<=2000-1-3` Will find all books added to calibre before 3 Jan, 2000
- `pubdate:=2009` Will find all books published in 2009

If the date is ambiguous then the current locale is used for date comparison. For example, in an mm/dd/yyyy locale 2/1/2009 is interpreted as 1 Feb 2009. In a dd/mm/yyyy locale it is interpreted as 2 Jan 2009. Some special date strings are available. The string `_today` translates to today’s date, whatever it is. The strings `_yesterday` and `_thismonth` also work. In addition, the string `_daysago` can be used to compare to a date some number of days ago. For example:

- `date:>10_daysago`
- `date:<=45_daysago`

### Searching dates and numeric values with relational comparisons

Dates and numeric fields support the relational operators `=` (equals), `>` (greater than), `>=` (greater than or equal to), `<` (less than), `<=` (less than or equal to), and `!=` (not equal to). Rating fields are considered to be numeric. For example, the search `rating:>=3` will find all books rated 3 or higher.

You can search for books that have a format of a certain size like this:

- `size:>1.1M` will find books with a format larger than 1.1MB
- `size:<=1K` will find books with a format smaller than or equal to 1KB

You can search for the number of items in multiple-valued fields such as tags using the character `#` then using the same syntax as numeric fields. For example, to find all books with more than 4 tags use `tags:#>4`. To find all books with exactly 10 tags use `tags:#=10`.
