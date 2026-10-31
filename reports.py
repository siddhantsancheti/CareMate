import data
from appointments import has_access
from sorting_searching import binary_search, linear_search, merge_sort

REPORT_TYPES = ["Blood Test", "X-Ray", "MRI / CT Scan", "ECG", "Urine Test", "Discharge Summary", "Other"]


class ListNode:
    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None


class DoublyLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0

    def add_first(self, item):
        node = ListNode(item)
        node.next = self.head
        if self.head:
            self.head.prev = node
        else:
            self.tail = node
        self.head = node
        self.size += 1

    def add_last(self, item):
        node = ListNode(item)
        node.prev = self.tail
        if self.tail:
            self.tail.next = node
        else:
            self.head = node
        self.tail = node
        self.size += 1

    def remove(self, match):
        node = self.head
        while node:
            if match(node.data):
                if node.prev:
                    node.prev.next = node.next
                else:
                    self.head = node.next
                if node.next:
                    node.next.prev = node.prev
                else:
                    self.tail = node.prev
                self.size -= 1
                return node.data
            node = node.next
        return None

    def to_list(self):
        items, node = [], self.head
        while node:
            items.append(node.data)
            node = node.next
        return items

    def __len__(self):
        return self.size


class TreeNode:
    def __init__(self, date, report):
        self.date = date
        self.reports = [report]
        self.left = None
        self.right = None


class BST:
    def __init__(self):
        self.root = None

    def insert(self, date, report):
        if not self.root:
            self.root = TreeNode(date, report)
            return
        node = self.root
        while True:
            if date == node.date:
                node.reports.append(report)
                return
            if date < node.date:
                if node.left is None:
                    node.left = TreeNode(date, report)
                    return
                node = node.left
            else:
                if node.right is None:
                    node.right = TreeNode(date, report)
                    return
                node = node.right

    def remove(self, date, report_id):
        node = self.root
        while node and node.date != date:
            node = node.left if date < node.date else node.right
        if node:
            node.reports = [r for r in node.reports if r["id"] != report_id]

    def between(self, low, high):
        result = []
        self._between(self.root, low, high, result)
        return result

    def _between(self, node, low, high, result):
        if node is None:
            return
        if low < node.date:
            self._between(node.left, low, high, result)
        if low <= node.date <= high:
            result.extend(node.reports)
        if node.date < high:
            self._between(node.right, low, high, result)

    def in_order(self):
        return self.between("0000-00-00", "9999-12-31")


def add_report(patient_id, title, rtype, rdate, doctor, notes, filename=None, uploaded_by=None):
    rid = data.new_id("R")
    report = dict(id=rid, patient_id=patient_id, title=title, type=rtype, date=rdate,
                  doctor=doctor, notes=notes, filename=filename, uploaded_by=uploaded_by)
    data.reports[patient_id].add_first(report)
    data.report_dates[patient_id].insert(rdate, report)
    data.report_by_id[rid] = report
    who = data.doctors[uploaded_by]["name"] if uploaded_by else "you"
    data.log(f"Report '{title}' added by {who}", patient_id, uploaded_by)
    return rid


def delete_report(report):
    data.reports[report["patient_id"]].remove(lambda r: r["id"] == report["id"])
    data.report_dates[report["patient_id"]].remove(report["date"], report["id"])
    del data.report_by_id[report["id"]]
    data.log(f"Report '{report['title']}' deleted", report["patient_id"])


def can_view(role, user_id, report):
    if not report:
        return False
    if role == "patient":
        return report["patient_id"] == user_id
    return role == "doctor" and has_access(user_id, report["patient_id"])


def can_change_file(role, user_id, report):
    if not can_view(role, user_id, report):
        return False
    if not report["filename"]:
        return True
    return report["uploaded_by"] == (user_id if role == "doctor" else None)


def list_reports(patient_id, query="", rtype="", sort_by="date", order="desc", date_from="", date_to=""):
    if date_from or date_to:
        items = data.report_dates[patient_id].between(date_from or "0000-00-00", date_to or "9999-12-31")
    else:
        items = data.reports[patient_id].to_list()
    items = linear_search(items, query, ["title", "notes", "doctor", "type"])
    if rtype:
        items = [r for r in items if r["type"] == rtype]
    key = {"title": lambda r: r["title"].lower(), "type": lambda r: r["type"]}.get(sort_by, lambda r: r["date"])
    return merge_sort(items, key=key, reverse=(order == "desc"))


def reports_on_date(patient_id, day):
    in_order = data.report_dates[patient_id].in_order()
    i = binary_search(in_order, day, key=lambda r: r["date"])
    found = []
    while i != -1 and i < len(in_order) and in_order[i]["date"] == day:
        found.append(in_order[i])
        i += 1
    return found
