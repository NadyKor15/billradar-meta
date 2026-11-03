# Word lists used by `billradar/open_lines.py`

The covering step opens a printed line only when its shape belongs to an allowed class. These lists tell it
which words a service line, a label or a sentence may hold, and which words are people.

| File | What it is | Source |
|---|---|---|
| `first_names.txt` | given names | `propernames` from the BSD `dict` word list |
| `surnames.txt` | the 8,000 most common US surnames | US Census Bureau, 2010 surnames, public domain |
| `service_words.txt` | words seen in hospital service descriptions, minus the names above | machine-readable standard charges published by two hospitals (45 CFR Part 180) |
| `english.txt.gz` | lower-case English words | `web2` from the BSD `dict` word list (Webster's Second, public domain) |

`english.txt.gz` is never used alone: a line of ordinary words does not open by itself.
