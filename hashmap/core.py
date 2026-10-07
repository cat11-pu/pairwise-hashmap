"""Open addressing hash table core.

Layout notes
------------
* Every key owns a home slot, hash_key(key) % capacity; a probe walks the slot
  array one step at a time and wraps around at the end of the table.
* A slot holds EMPTY, TOMBSTONE or a live key, and the value of a live key
  sits in the parallel value array at the same index. delete() leaves a
  tombstone behind so that the probe chains of the keys after it stay intact.
* The capacity starts at MIN_CAPACITY and grows to 2 * capacity + 1, so it is
  always odd and never a power of two; slot indices are reduced with % and
  never with a bit mask.
* Non-empty slots (live keys plus tombstones) may take up at most half of the
  table. A put that would pass that mark grows the table first and re-inserts
  every live key, which also drops the tombstones.
* Iteration walks the slot array from index 0 upwards and yields the live
  entries in slot order.

Only the Python standard library is used, and hash_key() never falls back to
the builtin hash(), so the table behaves the same way in every process.
"""

EMPTY = None

MIN_CAPACITY = 11


class _Tombstone(object):
    """Marker that delete() leaves in the slot a key used to occupy."""

    __slots__ = ()

    def __repr__(self):
        return "TOMBSTONE"


TOMBSTONE = _Tombstone()


def hash_key(key):
    """Return an unsigned 32 bit hash for an int or a str key."""
    if isinstance(key, str):
        value = 0x811C9DC5
        for char in key:
            value ^= ord(char)
            value = (value * 0x01000193) & 0xFFFFFFFF
        return value
    value = (key & 0xFFFFFFFF) * 0x9E3779B1
    value &= 0xFFFFFFFF
    value ^= value >> 15
    value = (value * 0x85EBCA6B) & 0xFFFFFFFF
    value ^= value >> 13
    return value


class HashMap(object):
    """Open addressing table over int and str keys."""

    def __init__(self, capacity=MIN_CAPACITY):
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("capacity must be an int")
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._keys = [EMPTY] * capacity
        self._values = [None] * capacity
        self._size = 0
        self._used = 0

    # ------------------------------------------------------------------
    # introspection
    # ------------------------------------------------------------------
    @property
    def capacity(self):
        """Number of slots in the table."""
        return self._capacity

    @property
    def used(self):
        """Number of slots that are not empty (live keys plus tombstones)."""
        return self._used

    @property
    def slots(self):
        """Snapshot of the slot array: EMPTY, TOMBSTONE or (key, value)."""
        view = []
        for index in range(self._capacity):
            key = self._keys[index]
            if key is EMPTY:
                view.append(EMPTY)
            elif key is TOMBSTONE:
                view.append(TOMBSTONE)
            else:
                view.append((key, self._values[index]))
        return view

    def __len__(self):
        return self._size

    def __contains__(self, key):
        self._check_key(key)
        index, found = self._lookup(key)
        return found

    # ------------------------------------------------------------------
    # probing
    # ------------------------------------------------------------------
    @staticmethod
    def _check_key(key):
        if isinstance(key, bool) or not isinstance(key, (int, str)):
            raise TypeError("key must be an int or a str")

    def _lookup(self, key):
        """Return (index, True) when key is stored, otherwise (-1, False)."""
        index = hash_key(key) % self._capacity
        for _ in range(self._capacity):
            slot = self._keys[index]
            if slot is EMPTY:
                return -1, False
            if slot is not TOMBSTONE and slot == key:
                return index, True
            index = (index + 1) % self._capacity
        return -1, False

    def _locate(self, key):
        """Return (index, found) for a put: where the key is, or where it goes."""
        index = hash_key(key) % self._capacity
        reusable = -1
        for _ in range(self._capacity):
            slot = self._keys[index]
            if slot is EMPTY:
                if reusable >= 0:
                    return reusable, False
                return index, False
            if slot is TOMBSTONE:
                if reusable < 0:
                    reusable = index
            elif slot == key:
                return index, True
            index = (index + 1) % self._capacity
        return reusable, False

    # ------------------------------------------------------------------
    # lookups
    # ------------------------------------------------------------------
    def get(self, key, default=None):
        """Return the value stored under key, or default when it is absent."""
        self._check_key(key)
        index, found = self._lookup(key)
        if not found:
            return default
        return self._values[index]

    # ------------------------------------------------------------------
    # mutation
    # ------------------------------------------------------------------
    def put(self, key, value):
        """Store value under key; an existing key keeps the slot it owns."""
        self._check_key(key)
        index, found = self._locate(key)
        if found:
            self._values[index] = value
            return
        if self._needs_growth():
            self._resize()
            index, _ = self._locate(key)
        self._store(index, key, value)

    def delete(self, key):
        """Remove key and report whether it was stored."""
        self._check_key(key)
        index, found = self._lookup(key)
        if not found:
            return False
        self._keys[index] = TOMBSTONE
        self._values[index] = None
        self._size -= 1
        return True

    def _store(self, index, key, value):
        """Write a key that is not in the table yet into a free slot."""
        if self._keys[index] is EMPTY:
            self._used += 1
        self._keys[index] = key
        self._values[index] = value
        self._size += 1

    def _needs_growth(self):
        """True when the next key would push the table past half full."""
        return (self._used + 1) * 2 > self._capacity

    def _resize(self):
        """Grow to 2 * capacity + 1 and re-insert every live key."""
        old_keys = self._keys
        old_values = self._values
        new_capacity = self._capacity * 2 + 1
        self._capacity = new_capacity
        self._keys = [EMPTY] * new_capacity
        self._values = [None] * new_capacity
        self._used = 0
        self._size = 0
        for index in range(len(old_keys)):
            key = old_keys[index]
            if key is EMPTY or key is TOMBSTONE:
                continue
            target, _ = self._locate(key)
            if self._keys[target] is EMPTY:
                self._used += 1
            self._keys[target] = key
            self._values[target] = old_values[index]
            self._size += 1

    # ------------------------------------------------------------------
    # iteration
    # ------------------------------------------------------------------
    def __iter__(self):
        for index in range(self._capacity):
            key = self._keys[index]
            if key is EMPTY:
                continue
            if key is not TOMBSTONE:
                yield key, self._values[index]

    def keys(self):
        return [key for key, _ in self]

    def values(self):
        return [value for _, value in self]

    def items(self):
        return [(key, value) for key, value in self]
