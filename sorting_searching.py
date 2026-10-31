def merge_sort(items, key=lambda x: x, reverse=False):
    if len(items) <= 1:
        return list(items)
    mid = len(items) // 2
    left = merge_sort(items[:mid], key, reverse)
    right = merge_sort(items[mid:], key, reverse)
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = key(left[i]), key(right[j])
        if (a >= b) if reverse else (a <= b):
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def quick_sort(items, key=lambda x: x):
    if len(items) <= 1:
        return list(items)
    pivot = key(items[len(items) // 2])
    smaller = [x for x in items if key(x) < pivot]
    equal = [x for x in items if key(x) == pivot]
    bigger = [x for x in items if key(x) > pivot]
    return quick_sort(smaller, key) + equal + quick_sort(bigger, key)


def binary_search(sorted_items, target, key=lambda x: x):
    low, high, found = 0, len(sorted_items) - 1, -1
    while low <= high:
        mid = (low + high) // 2
        k = key(sorted_items[mid])
        if k == target:
            found = mid
            high = mid - 1
        elif k < target:
            low = mid + 1
        else:
            high = mid - 1
    return found


def linear_search(items, query, fields):
    q = query.lower().strip()
    if not q:
        return list(items)
    return [it for it in items if any(q in str(it.get(f, "")).lower() for f in fields)]
