import tempfile
import unittest
from datetime import date

from kangji import check, drugs, store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = store.connect(self.tmp.name)

    def tearDown(self):
        self.conn.close()

    def test_add_and_list(self):
        store.add_med(self.conn, "布洛芬", "布洛芬", 1, "2027-06-01", "卧室", "痛经用")
        rows = store.list_meds(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["place"], "卧室")

    def test_same_name_different_batch_kept_apart(self):
        store.add_med(self.conn, "布洛芬", "布洛芬", 1, "2027-06-01")
        store.add_med(self.conn, "布洛芬", "布洛芬", 2, "2028-01-01")
        self.assertEqual(len(store.list_meds(self.conn)), 2)

    def test_duplicate_same_batch_merges_qty(self):
        store.add_med(self.conn, "布洛芬", "布洛芬", 1, "2027-06-01")
        store.add_med(self.conn, "布洛芬", "布洛芬", 2, "2027-06-01")
        rows = store.list_meds(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["qty"], 3)

    def test_use_reduces_qty(self):
        mid = store.add_med(self.conn, "布洛芬", "布洛芬", 3, "2027-06-01")
        self.assertEqual(store.use_med(self.conn, mid, 2), 1)

    def test_use_never_negative(self):
        mid = store.add_med(self.conn, "布洛芬", "布洛芬", 1, "2027-06-01")
        self.assertEqual(store.use_med(self.conn, mid, 5), 0)

    def test_use_unknown_id(self):
        self.assertIsNone(store.use_med(self.conn, 999, 1))

    def test_delete(self):
        mid = store.add_med(self.conn, "布洛芬", "布洛芬", 1, "")
        store.delete_med(self.conn, mid)
        self.assertEqual(store.list_meds(self.conn), [])

    def test_advice_roundtrip(self):
        actions = [{"n": 1, "thing": "扔掉过期的", "why": "安全风险", "foreign": ["布洛芬"]}]
        store.save_advice(self.conn, actions, "先清过期的", ["布洛芬"])
        last = store.last_advice(self.conn)
        self.assertEqual(last["summary"], "先清过期的")
        self.assertEqual(last["actions"][0]["thing"], "扔掉过期的")
        # 库里列名叫 outsiders（foreign 是 SQLite 保留字），读出来映射回 foreign
        self.assertEqual(last["foreign"], ["布洛芬"])
        self.assertNotIn("outsiders", last)

    def test_last_advice_empty(self):
        self.assertIsNone(store.last_advice(self.conn))

    def test_stats(self):
        store.add_med(self.conn, "布洛芬", "布洛芬", 1, "2027-06-01")
        store.add_med(self.conn, "板蓝根颗粒", "", 2, "")
        s = store.stats(self.conn)
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["unrecognized"], 1)

    def test_empty_expire_no_crash(self):
        store.add_med(self.conn, "创可贴", "创可贴", 10, "")
        row = store.get_med(self.conn, store.list_meds(self.conn)[0]["id"])
        self.assertEqual(row["expire"], "")


class SampleCsvTest(unittest.TestCase):
    """样例文件就是文档的一部分，别让它悄悄坏掉。"""

    def test_sample_loads_and_checks(self):
        import csv
        import os

        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "药箱.csv")
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertGreaterEqual(len(rows), 8)
        items = []
        for r in rows:
            expire = check.parse_date((r.get("有效期") or "").strip())
            items.append({
                "name": (r.get("名称") or "").strip(),
                "qty": float((r.get("数量") or 1) or 1),
                "expire": expire.isoformat() if expire else "",
            })
        result = check.check(items, today=date(2026, 11, 25))
        self.assertTrue(result["expired"])
        self.assertTrue(result["expiring"])
        self.assertTrue(result["duplicates"])
        self.assertTrue(result["conflicts"])
        self.assertTrue(result["unknown"])


if __name__ == "__main__":
    unittest.main()
