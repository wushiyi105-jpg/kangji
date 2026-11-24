import unittest

from kangji import drugs


class LookupTest(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(drugs.lookup("布洛芬")["name"], "布洛芬")
        self.assertEqual(drugs.lookup("布洛芬")["matched"], "exact")

    def test_alias_brand(self):
        hit = drugs.lookup("芬必得")
        self.assertEqual(hit["name"], "布洛芬")
        self.assertEqual(hit["matched"], "alias")

    def test_compound_cold_medicine(self):
        # 商品名五花八门，成分却是同一个
        for brand in ("999感冒灵", "白加黑", "新康泰克", "感康"):
            self.assertEqual(drugs.lookup(brand)["name"], "复方感冒药", brand)

    def test_instructions_suffix(self):
        self.assertEqual(drugs.lookup("布洛芬缓释胶囊")["name"], "布洛芬")

    def test_fuzzy(self):
        self.assertEqual(drugs.lookup("头孢克肟分散片")["name"], "头孢类")

    def test_alcohol_med(self):
        self.assertIn("含酒精", drugs.lookup("藿香正气水")["tags"])

    def test_unknown(self):
        self.assertIsNone(drugs.lookup("板蓝根颗粒"))

    def test_empty(self):
        self.assertIsNone(drugs.lookup(""))
        self.assertIsNone(drugs.lookup(None))

    def test_lookup_does_not_mutate_table(self):
        drugs.lookup("泰诺林")
        self.assertNotIn("matched", drugs.MEDS[0])


class IngredientsTest(unittest.TestCase):
    def test_compound_has_paracetamol(self):
        med = drugs.lookup("999感冒灵")
        self.assertIn("对乙酰氨基酚", drugs.all_ingredients(med))

    def test_external_has_none(self):
        self.assertEqual(drugs.all_ingredients(drugs.lookup("创可贴")), [])

    def test_describe(self):
        text = drugs.describe("泰诺林")
        self.assertIn("对乙酰氨基酚", text)

    def test_describe_unknown(self):
        self.assertIn("库里没有", drugs.describe("板蓝根"))


class TableShapeTest(unittest.TestCase):
    def test_every_med_has_fields(self):
        for med in drugs.MEDS:
            for key in ("name", "aliases", "ingredients", "kind", "tags"):
                self.assertIn(key, med)

    def test_no_duplicate_generic_names(self):
        names = [m["name"] for m in drugs.MEDS]
        self.assertEqual(len(names), len(set(names)))

    def test_conflict_rules_reference_existing_names(self):
        known = {m["name"] for m in drugs.MEDS}
        tags = {t for m in drugs.MEDS for t in m["tags"]}
        for rule in drugs.CONFLICTS:
            for name in rule["a"]:
                self.assertIn(name, known)
            for name in rule.get("b") or []:
                self.assertIn(name, known)
            for tag in rule.get("b_tags") or []:
                self.assertIn(tag, tags)


if __name__ == "__main__":
    unittest.main()
