import unittest
from datetime import date

from kangji import check

TODAY = date(2026, 11, 25)

ITEMS = [
    {"name": "泰诺林", "qty": 1, "expire": "2027-03-01", "place": "客厅"},
    {"name": "999感冒灵", "qty": 2, "expire": "2026-12-20", "place": "客厅"},
    {"name": "氯雷他定", "qty": 1, "expire": "2026-11-10", "place": "卧室"},
    {"name": "头孢克肟", "qty": 1, "expire": "2027-09-01", "place": "药箱"},
    {"name": "藿香正气水", "qty": 1, "expire": "2027-06-01", "place": "厨房"},
    {"name": "维生素C", "qty": 0, "expire": "2027-02-01", "place": "厨房"},
    {"name": "板蓝根颗粒", "qty": 2, "expire": "2027-01-01", "place": "厨房"},
]


class ParseDateTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(check.parse_date("2027-03-01"), date(2027, 3, 1))
        self.assertEqual(check.parse_date("2027/03/01"), date(2027, 3, 1))
        self.assertEqual(check.parse_date("20270301"), date(2027, 3, 1))
        self.assertEqual(check.parse_date("2027-03").day, 1)

    def test_empty(self):
        self.assertIsNone(check.parse_date(""))
        self.assertIsNone(check.parse_date(None))

    def test_garbage(self):
        self.assertIsNone(check.parse_date("明年三月"))


class CheckTest(unittest.TestCase):
    def test_expired(self):
        r = check.check(ITEMS, today=TODAY)
        self.assertEqual([e["name"] for e in r["expired"]], ["氯雷他定"])
        self.assertEqual(r["expired"][0]["days_ago"], 15)

    def test_expiring_within_60_days(self):
        r = check.check(ITEMS, today=TODAY)
        self.assertEqual([e["name"] for e in r["expiring"]], ["999感冒灵"])
        self.assertEqual(r["expiring"][0]["days_left"], 25)

    def test_duplicate_ingredient(self):
        r = check.check(ITEMS, today=TODAY)
        self.assertEqual(len(r["duplicates"]), 1)
        self.assertEqual(r["duplicates"][0]["ingredient"], "对乙酰氨基酚")
        self.assertEqual(sorted(r["duplicates"][0]["names"]), ["999感冒灵", "泰诺林"])

    def test_double_nsaid_conflict(self):
        items = [
            {"name": "布洛芬", "qty": 1},
            {"name": "扶他林", "qty": 1},
        ]
        r = check.check(items, today=TODAY)
        self.assertTrue(any("非甾体" in c["why"] for c in r["conflicts"]))
        self.assertEqual(r["level"], "high")

    def test_alcohol_conflict_is_high(self):
        r = check.check(ITEMS, today=TODAY)
        pair = [c for c in r["conflicts"] if "头孢克肟" in c["a"] or "头孢克肟" in c["b"]]
        self.assertTrue(pair)
        self.assertEqual(pair[0]["level"], "high")
        self.assertIn("双硫仑", pair[0]["why"])

    def test_same_drug_twice_is_not_conflict(self):
        items = [{"name": "头孢克肟", "qty": 1}, {"name": "头孢克肟", "qty": 2, "expire": "2028-01"}]
        r = check.check(items, today=TODAY)
        self.assertEqual([c for c in r["conflicts"] if "头孢" in c["a"]], [])

    def test_unknown_listed_not_judged(self):
        r = check.check(ITEMS, today=TODAY)
        self.assertEqual(r["unknown"], ["板蓝根颗粒"])

    def test_zero_stock_is_low(self):
        r = check.check(ITEMS, today=TODAY)
        self.assertEqual([s["name"] for s in r["low_stock"]], ["维生素C"])

    def test_qty_one_is_not_noise(self):
        # 默认阈值 0：家里每盒只剩 1 片不该被报成「快用完」
        r = check.check(ITEMS, today=TODAY)
        self.assertNotIn("泰诺林", [s["name"] for s in r["low_stock"]])

    def test_low_stock_threshold_adjustable(self):
        r = check.check(ITEMS, today=TODAY, low_stock=1)
        self.assertIn("泰诺林", [s["name"] for s in r["low_stock"]])

    def test_level_high_when_conflict(self):
        self.assertEqual(check.check(ITEMS, today=TODAY)["level"], "high")

    def test_level_ok_for_clean_shelf(self):
        r = check.check([{"name": "蒙脱石散", "qty": 5, "expire": "2028-01-01"}], today=TODAY)
        self.assertEqual(r["level"], "ok")

    def test_level_medium_for_expiring_only(self):
        r = check.check([{"name": "蒙脱石散", "qty": 5, "expire": "2026-12-31"}], today=TODAY)
        self.assertEqual(r["level"], "medium")

    def test_no_expire_not_flagged(self):
        r = check.check([{"name": "创可贴", "qty": 10}], today=TODAY)
        self.assertEqual(r["expired"], [])
        self.assertEqual(r["expiring"], [])

    def test_empty_shelf(self):
        r = check.check([], today=TODAY)
        self.assertEqual(r["checked"], 0)
        self.assertEqual(r["level"], "ok")


class RenderTest(unittest.TestCase):
    def test_sections(self):
        text = check.render_text(check.check(ITEMS, today=TODAY))
        self.assertIn("过期了", text)
        self.assertIn("不宜同用", text)
        self.assertIn("同一成分", text)

    def test_summary_line(self):
        r = check.check(ITEMS, today=TODAY)
        self.assertIn("过期 1 个", check.summary_line(r))

    def test_clean_summary(self):
        r = check.check([{"name": "蒙脱石散", "qty": 3}], today=TODAY)
        self.assertIn("没查出问题", check.summary_line(r))

    def test_generic_not_duplicated(self):
        r = check.check([{"name": "氯雷他定", "qty": 1, "expire": "2026-01-01"}], today=TODAY)
        text = check.render_text(r)
        self.assertNotIn("氯雷他定（氯雷他定）", text)


if __name__ == "__main__":
    unittest.main()
