import json
import unittest
from unittest.mock import patch

from kangji import advice

RESULT = {
    "expired": [{"name": "氯雷他定", "generic": "氯雷他定", "expire": "2026-11-10", "days_ago": 15}],
    "expiring": [{"name": "999感冒灵", "generic": "复方感冒药", "expire": "2026-06-01", "days_left": 25}],
    "duplicates": [{"ingredient": "对乙酰氨基酚", "names": ["999感冒灵", "泰诺林"]}],
    "conflicts": [{"a": "头孢克肟", "b": "藿香正气水", "level": "high", "why": "双硫仑样反应"}],
    "low_stock": [{"name": "维生素C", "qty": 0}],
    "unknown": ["板蓝根颗粒"],
    "checked": 7,
    "level": "high",
    "as_of": "2026-01-01",
}

ITEMS = [
    {"name": "泰诺林", "qty": 1, "expire": "2027-03-01"},
    {"name": "999感冒灵", "qty": 2, "expire": "2026-06-01"},
]


def fake_chat_factory(reply):
    def _chat(messages, config=None, **kwargs):
        return reply
    return _chat


def advise_with(reply):
    with patch.object(advice.llm, "chat", fake_chat_factory(reply)):
        return advice.advise(RESULT, ITEMS, config={"api_key": "x"})


class ForeignMedTest(unittest.TestCase):
    ALLOWED = {"对乙酰氨基酚", "复方感冒药"}

    def test_catches_new_drug(self):
        self.assertEqual(advice.find_foreign_meds("另外可以配合布洛芬一起吃。", self.ALLOWED), ["布洛芬"])

    def test_allows_drugs_on_shelf(self):
        text = "泰诺林和999感冒灵都含对乙酰氨基酚，先只留一盒。"
        self.assertEqual(advice.find_foreign_meds(text, self.ALLOWED), [])

    def test_catches_brand_alias(self):
        self.assertEqual(advice.find_foreign_meds("实在不行就吃芬必得。", self.ALLOWED), ["芬必得"])

    def test_dedup_per_med(self):
        self.assertEqual(advice.find_foreign_meds("布洛芬，或者布洛芬缓释胶囊。", self.ALLOWED), ["布洛芬"])

    def test_empty(self):
        self.assertEqual(advice.find_foreign_meds("", self.ALLOWED), [])
        self.assertEqual(advice.find_foreign_meds(None, self.ALLOWED), [])

    def test_ingredient_mention_when_shelf_has_generic(self):
        # 药箱记的是商品名，模型说成分名不算新增药
        self.assertEqual(advice.find_foreign_meds("对乙酰氨基酚别重复", {"对乙酰氨基酚"}), [])


class PromptTest(unittest.TestCase):
    def test_system_forbids_diagnosis_and_dose(self):
        self.assertIn("不诊断", advice.SYSTEM)
        self.assertIn("不给剂量", advice.SYSTEM)
        self.assertIn("不推荐新增什么药", advice.SYSTEM)

    def test_payload_lists_unrecognized_item(self):
        result = dict(RESULT, unknown=["板蓝根颗粒"])
        payload, _ = advice.build_prompt(result, [{"name": "板蓝根颗粒", "qty": 2}])
        self.assertIn("板蓝根颗粒", payload)

    def test_allowed_set_is_generic_names(self):
        _, allowed = advice.build_prompt(RESULT, ITEMS)
        self.assertEqual(allowed, {"对乙酰氨基酚", "复方感冒药"})


class AdviseTest(unittest.TestCase):
    def test_numbers_are_renumbered(self):
        reply = json.dumps({"actions": [
            {"n": 3, "thing": "扔掉氯雷他定", "why": "过期 15 天"},
            {"thing": "合并感冒药", "why": "同成分"},
        ]}, ensure_ascii=False)
        out = advise_with(reply)
        self.assertEqual([a["n"] for a in out["actions"]], [1, 2])

    def test_max_five_actions(self):
        actions = [{"n": i, "thing": f"第{i}条", "why": "d"} for i in range(9)]
        out = advise_with(json.dumps({"actions": actions}, ensure_ascii=False))
        self.assertEqual(len(out["actions"]), advice.MAX_ACTIONS)

    def test_skips_blank_thing(self):
        reply = json.dumps({"actions": [{"thing": "  ", "why": "x"},
                                       {"thing": "有用的一条", "why": ""}]}, ensure_ascii=False)
        out = advise_with(reply)
        self.assertEqual(len(out["actions"]), 1)

    def test_foreign_flagged_and_deduped(self):
        reply = json.dumps({
            "actions": [{"n": 1, "thing": "可以配点布洛芬", "why": "退烧"}],
            "summary": "另外布洛芬也行",
        }, ensure_ascii=False)
        out = advise_with(reply)
        self.assertEqual(out["foreign"], ["布洛芬"])

    def test_error_does_not_raise(self):
        with patch.object(advice.llm, "chat", side_effect=advice.llm.LLMError("连不上")):
            out = advice.advise(RESULT, ITEMS, config={"api_key": "x"})
        self.assertEqual(out["actions"], [])
        self.assertIn("连不上", out["error"])

    def test_bad_json_is_error(self):
        out = advise_with("我觉得应该扔掉过期的那盒")
        self.assertEqual(out["actions"], [])
        self.assertTrue(out["error"])

    def test_render(self):
        out = {"actions": [{"n": 1, "thing": "扔掉氯雷他定", "why": "过期 15 天", "foreign": []}],
               "summary": "先处理过期的", "error": "", "foreign": []}
        text = advice.render_text(out)
        self.assertIn("1. 扔掉氯雷他定", text)
        self.assertIn("先处理过期的", text)

    def test_render_warns_foreign(self):
        out = {"actions": [], "summary": "", "error": "", "foreign": ["布洛芬"]}
        self.assertIn("布洛芬", advice.render_text(out))


if __name__ == "__main__":
    unittest.main()
