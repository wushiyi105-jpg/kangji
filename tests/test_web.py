import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from kangji import advice, store, web


class WebTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = store.connect(self.path)
        self.httpd = web.make_server(self.conn, port=0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.conn.close()
        os.unlink(self.path)

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def post(self, path, payload=None):
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_page(self):
        status, html = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("康记", html)
        self.assertIn("/api/check", html)

    def test_meds_empty(self):
        status, body = self.get("/api/meds")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["items"], [])

    def test_add_then_list(self):
        status, d = self.post("/api/add", {"name": "泰诺林", "qty": 2, "expire": "2027-03"})
        self.assertEqual(status, 200)
        self.assertEqual(d["generic"], "对乙酰氨基酚")
        _, body = self.get("/api/meds")
        self.assertEqual(len(json.loads(body)["items"]), 1)

    def test_add_requires_name(self):
        status, d = self.post("/api/add", {"name": "  "})
        self.assertEqual(status, 400)

    def test_add_bad_date(self):
        status, d = self.post("/api/add", {"name": "布洛芬", "expire": "明年"})
        self.assertEqual(status, 400)

    def test_check_endpoint(self):
        self.post("/api/add", {"name": "氯雷他定", "expire": "2026-01-01"})
        _, body = self.get("/api/check?today=2026-02-01")
        d = json.loads(body)
        self.assertEqual(d["expired"][0]["name"], "氯雷他定")

    def test_check_default_today(self):
        self.post("/api/add", {"name": "布洛芬", "expire": "2030-01-01"})
        _, body = self.get("/api/check")
        self.assertEqual(json.loads(body)["expired"], [])

    def test_advice_requires_meds(self):
        status, d = self.post("/api/advice")
        self.assertEqual(status, 400)

    def test_advice_success(self):
        self.post("/api/add", {"name": "氯雷他定", "expire": "2026-01-01"})
        reply = json.dumps({"actions": [{"n": 1, "thing": "扔掉它", "why": "过期"}],
                            "summary": "先清"}, ensure_ascii=False)
        with patch.object(advice.llm, "chat", return_value=reply):
            status, d = self.post("/api/advice")
        self.assertEqual(status, 200)
        self.assertEqual(d["actions"][0]["thing"], "扔掉它")
        self.assertIsNotNone(store.last_advice(self.conn))

    def test_advice_model_down(self):
        self.post("/api/add", {"name": "布洛芬"})
        with patch.object(advice.llm, "chat", side_effect=advice.llm.LLMError("连不上")):
            status, d = self.post("/api/advice")
        self.assertEqual(status, 502)

    def test_404(self):
        status, d = self.post("/api/nope")
        self.assertEqual(status, 404)

    def test_404_get(self):
        status, body = self.get("/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
