"""
Sorting & Searching algorithms (implemented by hand)
----------------------------------------------------
merge_sort     -> sort reports by date / title / type          O(n log n), stable
quick_sort     -> sort medical stores by distance              O(n log n) average
binary_search  -> find a report by exact date in a sorted list O(log n)
linear_search  -> keyword search across report titles / notes  O(n)
"""


def merge_sort(items, key=lambda x: x, reverse=False):
    if len(items) <= 1:
        return list(items)
    mid = len(items) // 2
    left = merge_sort(items[:mid], key, reverse)
    right = merge_sort(items[mid:], key, reverse)
    return _merge(left, right, key, reverse)


def _merge(left, right, key, reverse):
    out, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = key(left[i]), key(right[j])
        take_left = (a >= b) if reverse else (a <= b)
        if take_left:
            out.append(left[i]); i += 1
        else:
            out.append(right[j]); j += 1
    out.extend(left[i:])
    out.extend(right[j:])
    return out


def quick_sort(items, key=lambda x: x):
    """Quick sort with middle-element pivot (3-way partition handles duplicates)."""
    if len(items) <= 1:
        return list(items)
    pivot = key(items[len(items) // 2])
    less = [x for x in items if key(x) < pivot]
    equal = [x for x in items if key(x) == pivot]
    greater = [x for x in items if key(x) > pivot]
    return quick_sort(less, key) + equal + quick_sort(greater, key)


def binary_search(sorted_items, target, key=lambda x: x):
    """Return index of the FIRST item whose key == target, else -1."""
    lo, hi, found = 0, len(sorted_items) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        k = key(sorted_items[mid])
        if k == target:
            found = mid
            hi = mid - 1          # keep looking left for the first match
        elif k < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return found


def linear_search(items, query, fields):
    q = query.lower().strip()
    if not q:
        return list(items)
    return [it for it in items if any(q in str(it.get(f, "")).lower() for f in fields)]
