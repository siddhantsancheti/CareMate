"""
Doubly Linked List
------------------
Used for: each patient's REPORTS LIBRARY.

Why a linked list?
  * Reports are added often (new upload goes to the head -> newest first) : O(1)
  * Reports can be deleted from anywhere in the list once found           : O(1) unlink
  * We traverse the whole list to display it                               : O(n)
"""


class _Node:
    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None


class DoublyLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self._size = 0

    # ---------- insertion ----------
    def add_first(self, data):
        """Insert at head. O(1)"""
        node = _Node(data)
        if self.head is None:
            self.head = self.tail = node
        else:
            node.next = self.head
            self.head.prev = node
            self.head = node
        self._size += 1

    def add_last(self, data):
        """Insert at tail. O(1)"""
        node = _Node(data)
        if self.tail is None:
            self.head = self.tail = node
        else:
            node.prev = self.tail
            self.tail.next = node
            self.tail = node
        self._size += 1

    # ---------- search / delete ----------
    def find(self, predicate):
        """Linear search: return first data where predicate(data) is True. O(n)"""
        cur = self.head
        while cur:
            if predicate(cur.data):
                return cur.data
            cur = cur.next
        return None

    def remove(self, predicate):
        """Remove first node matching predicate. O(n) to find + O(1) to unlink."""
        cur = self.head
        while cur:
            if predicate(cur.data):
                if cur.prev:
                    cur.prev.next = cur.next
                else:
                    self.head = cur.next
                if cur.next:
                    cur.next.prev = cur.prev
                else:
                    self.tail = cur.prev
                self._size -= 1
                return cur.data
            cur = cur.next
        return None

    # ---------- traversal ----------
    def to_list(self):
        """Forward traversal into a Python list. O(n)"""
        out, cur = [], self.head
        while cur:
            out.append(cur.data)
            cur = cur.next
        return out

    def __iter__(self):
        cur = self.head
        while cur:
            yield cur.data
            cur = cur.next

    def __len__(self):
        return self._size
