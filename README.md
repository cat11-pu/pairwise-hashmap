# pairwise-hashmap

An open addressing hash table over `int` and `str` keys, written with the
Python standard library only. `hashmap/core.py` holds the kernel: keys land in
a home slot computed from a self-contained hash function, a probe walks the
slot array one step at a time, deleted slots keep a tombstone so the probe
chains behind them survive, and the table grows to `2 * capacity + 1` (always
odd, never a power of two) once the non-empty slots would pass half of the
capacity.

## Layout

    hashmap/__init__.py
    hashmap/core.py        open addressing kernel
    tests/__init__.py
    tests/test_core.py     9 unittest cases

## Requirements

Python 3.8 or newer, nothing else. No third-party packages and no network
access are needed to build or test this project.

## Running the tests

From the project root:

    python3 -m unittest discover -s tests -v

On Windows with the default installation:

    py -3 -m unittest discover -s tests -v

A single case can be run with:

    python3 -m unittest tests.test_core.HashMapTest.test_02_put_and_get_mixed_keys -v

## Usage

    from hashmap.core import HashMap

    table = HashMap()
    table.put("alpha", 1)
    table.put("beta", 2)
    table.get("alpha")          # 1
    table.get("gamma", 0)       # 0
    "beta" in table             # True
    table.delete("beta")        # True
    len(table)                  # 1
    list(table)                 # [("alpha", 1)]

Keys must be `int` or `str`; `True`/`False`, floats, `None` and every other
type raise `TypeError`. Values may be anything, including `None`. The default
capacity is `MIN_CAPACITY` (11) and a table accepts any positive `int`
capacity at construction time.

`len(table)` is the number of stored keys, `table.capacity` is the size of the
slot array, `table.used` is the number of non-empty slots (live keys plus
tombstones) and `table.slots` is a snapshot of the slot array where every
entry is either `None`, `TOMBSTONE` or a `(key, value)` tuple. Iteration -
`list(table)`, `table.items()`, `table.keys()` and `table.values()` - walks the
slots from index 0 upwards.
