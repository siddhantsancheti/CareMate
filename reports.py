"""
Reports: upload, search, sort and delete a patient's medical reports.

Data structures used here:
    DoublyLinkedList -> each patient's report library (newest report first)
    BST              -> the same reports indexed by date, for "reports between two dates"
"""

from sorting_searching import binary_search, linear_search, merge_sort

REPORT_TYPES = ["Blood Test", "X-Ray", "MRI / CT Scan", "ECG", "Urine Test", "Discharge Summary", "Other"]


# =====================================================================
# Doubly Linked List
# Each node points to the node before it and the node after it.
# Adding at the front or back is O(1). Finding a node is O(n).
# =====================================================================
class Node:
    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None


class DoublyLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0

    def add_first(self, data):
        node = Node(data)
        if self.head is None:          # empty list
            self.head = node
            self.tail = node
        else:
            node.next = self.head
            self.head.prev = node
            self.head = node
        self.size += 1

    def add_last(self, data):
        node = Node(data)
        if self.tail is None:          # empty list
            self.head = node
            self.tail = node
        else:
            node.prev = self.tail
            self.tail.next = node
            self.tail = node
        self.size += 1

    def remove(self, match):
        """Remove the first item for which match(item) is True, and return it."""
        current = self.head
        while current is not None:
            if match(current.data):
                if current.prev is not None:
                    current.prev.next = current.next
                else:
                    self.head = current.next
                if current.next is not None:
                    current.next.prev = current.prev
                else:
                    self.tail = current.prev
                self.size -= 1
                return current.data
            current = current.next
        return None

    def to_list(self):
        items = []
        current = self.head
        while current is not None:
            items.append(current.data)
            current = current.next
        return items

    def __len__(self):
        return self.size


# =====================================================================
# Binary Search Tree
# Smaller keys go to the left, bigger keys to the right.
# Here the key is a report date, so an inorder walk gives reports in date order.
# =====================================================================
class TreeNode:
    def __init__(self, key, value):
        self.key = key
        self.values = [value]          # many reports can have the same date
        self.left = None
        self.right = None


class BST:
    def __init__(self):
        self.root = None

    def insert(self, key, value):
        if self.root is None:
            self.root = TreeNode(key, value)
            return
        current = self.root
        while True:
            if key == current.key:
                current.values.append(value)
                return
            if key < current.key:
                if current.left is None:
                    current.left = TreeNode(key, value)
                    return
                current = current.left
            else:
                if current.right is None:
                    current.right = TreeNode(key, value)
                    return
                current = current.right

    def remove_value(self, key, match):
        """Remove one value stored under key. The node is deleted when it has no values left."""
        node = self.root
        while node is not None and node.key != key:
            node = node.left if key < node.key else node.right
        if node is None:
            return
        for i in range(len(node.values)):
            if match(node.values[i]):
                node.values.pop(i)
                break
        if not node.values:
            self.root = self._delete(self.root, key)

    def _delete(self, node, key):
        """Usual BST delete: a leaf, a node with one child, or a node with two children."""
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
            successor = node.right               # smallest key in the right subtree
            while successor.left is not None:
                successor = successor.left
            node.key, node.values = successor.key, successor.values
            node.right = self._delete(node.right, successor.key)
        return node

    def range_query(self, low, high):
        """All values with low <= key <= high, in sorted order."""
        result = []
        self._range(self.root, low, high, result)
        return result

    def _range(self, node, low, high, result):
        if node is None:
            return
        if low < node.key:
            self._range(node.left, low, high, result)
        if low <= node.key <= high:
            result.extend(node.values)
        if node.key < high:
            self._range(node.right, low, high, result)

    def inorder(self):
        result = []
        self._inorder(self.root, result)
        return result

    def _inorder(self, node, result):
        if node is not None:
            self._inorder(node.left, result)
            result.extend(node.values)
            self._inorder(node.right, result)


# =====================================================================
# The reports part of CareMate
# =====================================================================
class Reports:
    def add_report(self, patient_id, title, rtype, rdate, doctor="", notes="", filename=None,
                   uploaded_by=None, rid=None):
        rid = rid or self._next_id("R")
        report = dict(id=rid, patient_id=patient_id, title=title, type=rtype, date=rdate,
                      doctor=doctor, notes=notes, filename=filename, uploaded_by=uploaded_by)
        self.reports.get(patient_id).add_first(report)           # O(1) newest first
        self.report_index.get(patient_id).insert(rdate, report)   # BST by date
        self.report_by_id[rid] = report
        self._save("reports", **report)
        who = self.doctors.get(uploaded_by)["name"] if uploaded_by else "you"
        self.log(f"Report '{title}' added by {who}", patient_id, uploaded_by)
        return rid

    def attach_file(self, report_id, filename):
        """Attach (or replace) the file of an existing report."""
        report = self.report_by_id.get(report_id)
        if report and filename:
            report["filename"] = filename
            self._update("reports", dict(filename=filename), id=report_id)
        return report

    def can_view_report(self, role, uid, report):
        """The patient who owns it, or a doctor whose booking with that patient was accepted."""
        return bool(report) and ((role == "patient" and report["patient_id"] == uid) or
                                 (role == "doctor" and self.has_access(uid, report["patient_id"])))

    def can_change_file(self, role, uid, report):
        """Attach a file if there is none; only the uploader may REPLACE an existing one."""
        if not self.can_view_report(role, uid, report):
            return False
        if not report["filename"]:
            return True
        uploader = report["uploaded_by"]            # None = the patient uploaded it
        return uploader == uid if role == "doctor" else uploader is None

    def delete_report(self, patient_id, report_id):
        report = self.reports.get(patient_id).remove(lambda r: r["id"] == report_id)
        if report:
            self.report_index.get(patient_id).remove_value(report["date"], lambda r: r["id"] == report_id)
            self.report_by_id.pop(report_id, None)
            self._delete("reports", id=report_id)
            self.log(f"Report '{report['title']}' deleted", patient_id)
        return report

    def list_reports(self, patient_id, query="", rtype="", sort_by="date",
                     order="desc", date_from="", date_to=""):
        # 1) Range query on the BST if a date range is given, else full linked-list traversal
        if date_from or date_to:
            items = self.report_index.get(patient_id).range_query(date_from or "0000-00-00",
                                                                  date_to or "9999-12-31")
        else:
            items = self.reports.get(patient_id).to_list()
        # 2) Linear search on keyword + filter on type
        items = linear_search(items, query, ["title", "notes", "doctor", "type"])
        if rtype:
            items = [r for r in items if r["type"] == rtype]
        # 3) Merge sort
        key = {"date": lambda r: r["date"], "title": lambda r: r["title"].lower(),
               "type": lambda r: r["type"]}.get(sort_by, lambda r: r["date"])
        return merge_sort(items, key=key, reverse=(order == "desc"))

    def find_report_on_date(self, patient_id, on_date):
        """Binary search on reports sorted by date (BST inorder already sorted)."""
        sorted_reports = self.report_index.get(patient_id).inorder()
        idx = binary_search(sorted_reports, on_date, key=lambda r: r["date"])
        if idx == -1:
            return []
        out = []
        while idx < len(sorted_reports) and sorted_reports[idx]["date"] == on_date:
            out.append(sorted_reports[idx]); idx += 1
        return out
