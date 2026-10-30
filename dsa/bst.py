"""
Binary Search Tree
------------------
Used for: indexing a patient's reports by DATE so we can answer
"show me all reports between 01-Jan and 31-Mar" (a range query).

  insert       : O(h)  (h = height; O(log n) when balanced, O(n) worst case)
  range query  : O(h + k)  where k = number of results
  inorder walk : O(n)  -> gives reports in sorted date order for free
"""


class _BSTNode:
    def __init__(self, key, value):
        self.key = key
        self.values = [value]   # several reports can share the same date
        self.left = None
        self.right = None


class BST:
    def __init__(self):
        self.root = None
        self._size = 0

    def insert(self, key, value):
        self._size += 1
        if self.root is None:
            self.root = _BSTNode(key, value)
            return
        cur = self.root
        while True:
            if key == cur.key:
                cur.values.append(value)
                return
            if key < cur.key:
                if cur.left is None:
                    cur.left = _BSTNode(key, value)
                    return
                cur = cur.left
            else:
                if cur.right is None:
                    cur.right = _BSTNode(key, value)
                    return
                cur = cur.right

    def remove_value(self, key, predicate):
        """Remove one value stored under `key` (keeps the node for simplicity
        if other values remain; removes the node when it becomes empty)."""
        node = self._find(key)
        if node is None:
            return
        for i, v in enumerate(node.values):
            if predicate(v):
                node.values.pop(i)
                self._size -= 1
                break
        if not node.values:
            self.root = self._delete(self.root, key)

    def _find(self, key):
        cur = self.root
        while cur and cur.key != key:
            cur = cur.left if key < cur.key else cur.right
        return cur

    def _delete(self, node, key):
        """Standard BST delete (3 cases: leaf, one child, two children)."""
        if node is None:
            return None
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            # two children: replace with inorder successor
            succ = node.right
            while succ.left:
                succ = succ.left
            node.key, node.values = succ.key, succ.values
            node.right = self._delete(node.right, succ.key)
        return node

    def range_query(self, low, high):
        """All values with low <= key <= high, in sorted order."""
        out = []
        self._range(self.root, low, high, out)
        return out

    def _range(self, node, low, high, out):
        if node is None:
            return
        if low < node.key:             # left subtree may contain keys >= low
            self._range(node.left, low, high, out)
        if low <= node.key <= high:
            out.extend(node.values)
        if node.key < high:            # right subtree may contain keys <= high
            self._range(node.right, low, high, out)

    def inorder(self):
        out = []
        self._inorder(self.root, out)
        return out

    def _inorder(self, node, out):
        if node:
            self._inorder(node.left, out)
            out.extend(node.values)
            self._inorder(node.right, out)

    def height(self):
        def h(n):
            return 0 if n is None else 1 + max(h(n.left), h(n.right))
        return h(self.root)

    def __len__(self):
        return self._size
