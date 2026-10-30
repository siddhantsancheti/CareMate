"""
Queue (FIFO) and Stack (LIFO)
-----------------------------
Queue  -> appointment WAITING LIST. When a doctor has no free slot the
          patient joins the queue; when someone cancels, the patient at the
          FRONT of the queue automatically gets that slot (first come, first served).
Stack  -> PRESCRIPTION HISTORY. The newest prescription is on top, and
          "Undo last prescription" is simply a pop().

Both are built on a singly linked list so every operation is O(1).
"""


class _Node:
    __slots__ = ("data", "next")

    def __init__(self, data, nxt=None):
        self.data = data
        self.next = nxt


class Queue:
    def __init__(self):
        self._front = None
        self._rear = None
        self._size = 0

    def enqueue(self, data):          # O(1)
        node = _Node(data)
        if self._rear is None:
            self._front = self._rear = node
        else:
            self._rear.next = node
            self._rear = node
        self._size += 1

    def dequeue(self):                # O(1)
        if self._front is None:
            return None
        node = self._front
        self._front = node.next
        if self._front is None:
            self._rear = None
        self._size -= 1
        return node.data

    def peek(self):
        return self._front.data if self._front else None

    def is_empty(self):
        return self._size == 0

    def to_list(self):
        out, cur = [], self._front
        while cur:
            out.append(cur.data)
            cur = cur.next
        return out

    def __len__(self):
        return self._size


class Stack:
    def __init__(self):
        self._top = None
        self._size = 0

    def push(self, data):             # O(1)
        self._top = _Node(data, self._top)
        self._size += 1

    def pop(self):                    # O(1)
        if self._top is None:
            return None
        node = self._top
        self._top = node.next
        self._size -= 1
        return node.data

    def peek(self):
        return self._top.data if self._top else None

    def is_empty(self):
        return self._size == 0

    def to_list(self):
        """Top first."""
        out, cur = [], self._top
        while cur:
            out.append(cur.data)
            cur = cur.next
        return out

    def __len__(self):
        return self._size
