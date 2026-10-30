"""
Hash Table (separate chaining)
------------------------------
Used for: storing PATIENTS, DOCTORS, MEDICAL STORES and MEDICINES by their id,
so any record can be looked up in average O(1) time.

Collisions are handled by "chaining": every bucket is a Python list of
(key, value) pairs. When the load factor (size / capacity) goes above 0.75
the table doubles its capacity and re-hashes every entry.
"""


class HashTable:
    def __init__(self, capacity=8):
        self._capacity = capacity
        self._size = 0
        self._buckets = [[] for _ in range(capacity)]

    def _hash(self, key):
        """Polynomial rolling hash on the string form of the key."""
        h = 0
        for ch in str(key):
            h = (h * 31 + ord(ch)) % 1_000_000_007
        return h % self._capacity

    def put(self, key, value):
        """Insert or update. Average O(1)"""
        bucket = self._buckets[self._hash(key)]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)
                return
        bucket.append((key, value))
        self._size += 1
        if self._size / self._capacity > 0.75:
            self._resize()

    def get(self, key, default=None):
        """Lookup. Average O(1)"""
        for k, v in self._buckets[self._hash(key)]:
            if k == key:
                return v
        return default

    def remove(self, key):
        bucket = self._buckets[self._hash(key)]
        for i, (k, v) in enumerate(bucket):
            if k == key:
                bucket.pop(i)
                self._size -= 1
                return v
        return None

    def contains(self, key):
        return self.get(key, _MISSING) is not _MISSING

    def _resize(self):
        old = self._buckets
        self._capacity *= 2
        self._buckets = [[] for _ in range(self._capacity)]
        self._size = 0
        for bucket in old:
            for k, v in bucket:
                self.put(k, v)

    def keys(self):
        return [k for b in self._buckets for k, _ in b]

    def values(self):
        return [v for b in self._buckets for _, v in b]

    def items(self):
        return [(k, v) for b in self._buckets for k, v in b]

    def __len__(self):
        return self._size

    def __contains__(self, key):
        return self.contains(key)

    def stats(self):
        """Used on the 'Under the hood' page."""
        longest = max((len(b) for b in self._buckets), default=0)
        return {
            "size": self._size,
            "capacity": self._capacity,
            "load_factor": round(self._size / self._capacity, 2),
            "longest_chain": longest,
        }


_MISSING = object()
