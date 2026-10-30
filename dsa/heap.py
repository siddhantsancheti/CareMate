"""
Min-Heap Priority Queue
-----------------------
Used for: the doctor's APPOINTMENT / TRIAGE queue.
Each booked appointment gets a priority:
    1 = Emergency, 2 = Urgent, 3 = Routine
The key is (day, priority, time): patients on earlier days come first; within
a day the most urgent patient is seen first, then by appointment time, then by
booking order (so it is fair / stable).

  push : O(log n)   (sift up)
  pop  : O(log n)   (sift down)
  peek : O(1)
The heap is stored in a plain array: children of index i are 2i+1 and 2i+2.
"""


class MinHeap:
    def __init__(self):
        self._a = []
        self._counter = 0  # insertion order -> stable tie-break

    def push(self, priority, item):
        entry = (priority, self._counter, item)
        self._counter += 1
        self._a.append(entry)
        self._sift_up(len(self._a) - 1)

    def pop(self):
        if not self._a:
            return None
        self._swap(0, len(self._a) - 1)
        priority, _, item = self._a.pop()
        if self._a:
            self._sift_down(0)
        return item

    def peek(self):
        return self._a[0][2] if self._a else None

    def remove(self, predicate):
        """Remove an arbitrary item (e.g. a cancelled appointment). O(n)"""
        for i, (_, _, item) in enumerate(self._a):
            if predicate(item):
                last = len(self._a) - 1
                self._swap(i, last)
                removed = self._a.pop()[2]
                if i < len(self._a):
                    self._sift_down(i)
                    self._sift_up(i)
                return removed
        return None

    def sorted_items(self):
        """Items in the order they would be popped (does not modify heap)."""
        copy = MinHeap()
        copy._a = list(self._a)
        out = []
        while len(copy):
            out.append(copy.pop())
        return out

    def _less(self, i, j):
        return self._a[i][:2] < self._a[j][:2]

    def _swap(self, i, j):
        self._a[i], self._a[j] = self._a[j], self._a[i]

    def _sift_up(self, i):
        while i > 0:
            parent = (i - 1) // 2
            if self._less(i, parent):
                self._swap(i, parent)
                i = parent
            else:
                break

    def _sift_down(self, i):
        n = len(self._a)
        while True:
            smallest, l, r = i, 2 * i + 1, 2 * i + 2
            if l < n and self._less(l, smallest):
                smallest = l
            if r < n and self._less(r, smallest):
                smallest = r
            if smallest == i:
                break
            self._swap(i, smallest)
            i = smallest

    def __len__(self):
        return len(self._a)


def top_k(pairs, k):
    """The k (key, count) pairs with the biggest counts, biggest first.
    Keeps a min-heap of size k: the smallest of the current top-k sits at the
    root, so a bigger count just pops it out.   O(n log k)
    Used for the admin's "most booked doctors" and "most prescribed medicines"."""
    heap = MinHeap()
    for key, c in pairs:
        heap.push(c, (key, c))
        if len(heap) > k:
            heap.pop()
    out = []
    while len(heap):
        out.append(heap.pop())
    return out[::-1]
