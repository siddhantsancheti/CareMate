"""
Trie (prefix tree)
------------------
Used for: MEDICINE NAME AUTOCOMPLETE when a doctor writes a prescription.
Typing "par" instantly suggests "Paracetamol 500mg", "Pantoprazole 40mg" ...

  insert          : O(L)        L = length of word
  prefix search   : O(P + K)    P = prefix length, K = characters in results
"""

from .algorithms import merge_sort


class _TrieNode:
    __slots__ = ("children", "word")

    def __init__(self):
        self.children = {}
        self.word = None    # full original word stored at the end node


class Trie:
    def __init__(self):
        self.root = _TrieNode()
        self._size = 0

    def insert(self, word):
        node = self.root
        for ch in word.lower():
            node = node.children.setdefault(ch, _TrieNode())
        if node.word is None:
            self._size += 1
        node.word = word

    def contains(self, word):
        node = self._walk(word.lower())
        return node is not None and node.word is not None

    def starts_with(self, prefix, limit=10):
        node = self._walk(prefix.lower())
        if node is None:
            return []
        out = []
        self._collect(node, out, limit)
        return out

    def _walk(self, s):
        node = self.root
        for ch in s:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def _collect(self, node, out, limit):
        """DFS in alphabetical order."""
        if len(out) >= limit:
            return
        if node.word is not None:
            out.append(node.word)
        for ch in merge_sort(list(node.children)):   # our own sort, alphabetical
            self._collect(node.children[ch], out, limit)
            if len(out) >= limit:
                return

    def __len__(self):
        return self._size
