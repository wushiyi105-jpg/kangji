import json
import os
import tempfile
import unittest
from unittest.mock import patch

from kangji import advice, cli, store


class CliTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._out = []

    def tearDown(self):
        os.unlink(self.path)

    def run_cli(self, argv):
        """跑一次 CLI，返回 (退出码, 输出)。"""
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["--db", self.path] + argv)
        return code, buf.getvalue()

    def test_add_known_med(self):
        code, out = self.run_cli(["add", "泰诺林", "--expire", "2027-03", "--place", "客厅"])
        self.assertEqual(code, 0)
        self.assertIn("对乙酰氨基酚", out)

    def test_add_unknown_med_is_fine(self):
        code, out = self.run_cli(["add", "板蓝根颗粒"])
        self.assertEqual(code, 0)
        self.assertIn("没这个名字", out)

    def test_add_bad_date(self):
        code, out = self.run_cli(["add", "布洛芬", "--expire", "明年"])
        self.assertEqual(code, 1)
        self.assertIn("看不懂", out)

    def test_list_empty(self):
        code, out = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("药箱是空的", out)

    def test_check_json(self):
        self.run_cli(["add", "氯雷他定", "--expire", "2026-01-01"])
        code, out = self.run_cli(["check", "--today", "2026-02-01", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["expired"][0]["name"], "氯雷他定")

    def test_check_text(self):
        self.run_cli(["add", "999感冒灵", "--expire", "2026-01-10"])
        self.run_cli(["add", "泰诺林", "--expire", "2027-01-01"])
        code, out = self.run_cli(["check", "--today", "2026-01-01"])
        self.assertEqual(code, 0)
        self.assertIn("不宜同用", out)
        self.assertIn("对乙酰氨基酚", out)

    def test_check_empty_shelf(self):
        code, out = self.run_cli(["check"])
        self.assertEqual(code, 0)
        self.assertIn("没什么可查", out)

    def test_use(self):
        self.run_cli(["add", "布洛芬", "--qty", "3"])
        code, out = self.run_cli(["use", "1", "--n", "2"])
        self.assertEqual(code, 0)
        self.assertIn("剩 1", out)

    def test_use_missing(self):
        code, out = self.run_cli(["use", "999"])
        self.assertEqual(code, 1)
        self.assertIn("没有 id=999", out)

    def test_show_and_rm(self):
        self.run_cli(["add", "头孢克肟", "--expire", "2027-09", "--note", "医生开的"])
        code, out = self.run_cli(["show", "1"])
        self.assertEqual(code, 0)
        self.assertIn("医生开的", out)
        self.assertIn("处方", out)
        code, out = self.run_cli(["rm", "1"])
        self.assertEqual(code, 0)
        self.assertIn("已删除", out)
        self.assertEqual(self.run_cli(["list"])[1].count("头孢克肟"), 0)

    def test_show_missing(self):
        self.assertEqual(self.run_cli(["show", "42"])[0], 1)

    def test_stats(self):
        self.run_cli(["add", "布洛芬"])
        code, out = self.run_cli(["stats"])
        self.assertEqual(code, 0)
        self.assertIn("total", out)

    def test_import_csv(self):
        samples = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "药箱.csv")
        code, out = self.run_cli(["import", samples])
        self.assertEqual(code, 0)
        self.assertIn("导入 10 条", out)
        conn = store.connect(self.path)
        try:
            self.assertEqual(len(store.list_meds(conn)), 10)
        finally:
            conn.close()

    def test_import_missing_file(self):
        self.assertEqual(self.run_cli(["import", "no-such.csv"])[0], 1)

    def test_advice_calls_model_and_saves(self):
        self.run_cli(["add", "氯雷他定", "--expire", "2026-01-01"])
        reply = json.dumps({"actions": [{"n": 1, "thing": "扔掉过期的", "why": "别吃"}],
                            "summary": "先清一遍"}, ensure_ascii=False)
        with patch.object(advice.llm, "chat", return_value=reply):
            code, out = self.run_cli(["advice", "--today", "2026-02-01"])
        self.assertEqual(code, 0)
        self.assertIn("扔掉过期的", out)
        conn = store.connect(self.path)
        try:
            self.assertIsNotNone(store.last_advice(conn))
        finally:
            conn.close()

    def test_advice_model_down(self):
        self.run_cli(["add", "布洛芬"])
        with patch.object(advice.llm, "chat", side_effect=advice.llm.LLMError("连不上")):
            code, out = self.run_cli(["advice"])
        self.assertEqual(code, 0)
        self.assertIn("连不上", out)

    def test_advice_empty_shelf(self):
        code, out = self.run_cli(["advice"])
        self.assertEqual(code, 0)
        self.assertIn("药箱是空的", out)


if __name__ == "__main__":
    unittest.main()
