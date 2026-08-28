# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2026 51 Degrees Mobile Experts Limited, Davidson House,
# Forbury Square, Reading, Berkshire, United Kingdom RG1 3EU.
#
# This Original Work is licensed under the European Union Public Licence
# (EUPL) v.1.2 and is subject to its terms as set out below.
#
# If a copy of the EUPL was not distributed with this file, You can obtain
# one at https://opensource.org/licenses/EUPL-1.2.
#
# The 'Compatible Licences' set out in the Appendix to the EUPL (as may be
# amended by the European Commission) shall be deemed incompatible for
# the purposes of the Work and the provisions of the compatibility
# clause in Article 5 of the EUPL shall not apply.
#
# If using the Work as, or as part of, a network application, by
# including the attribution notice(s) required under Article 5 of the EUPL
# in the end user terms of the application under an appropriate heading,
# such notice(s) shall fulfill the requirements of that article.
# *********************************************************************

"""The creator context example's ``/redeem`` route, driven over a real
socket against a ``DidClient`` whose transport is a stand-in, so the route
is tested as the page sees it and the cloud is never called."""

import importlib.util
import json
import os
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from http.server import HTTPServer
from pathlib import Path

from fiftyone_pipeline_did import DidClient

from .envelope import FakeTransport, KeySchedule, signed_fod_id

SERVER_PY = Path(__file__).resolve().parents[1] / "examples" \
    / "creator_context_web" / "server.py"

REDEEMED = json.dumps({
    "signature": "verified",
    "context": "verified",
    "verifiedAt": "2026-08-07T09:15:32Z",
    "secondsSinceVerified": 2,
})


def load_server():
    """Imports server.py by path. The module reads its environment at
    import, so a resource key is set first, and the value is never used
    here because the route under test takes its client from the class."""
    os.environ.setdefault("_51DEGREES_RESOURCE_KEY", "test-resource-key")
    spec = importlib.util.spec_from_file_location(
        "creator_context_server", SERVER_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CreatorContextServerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_module = load_server()
        cls.schedule = KeySchedule()
        cls.transport = FakeTransport({
            "id/key/": (200, cls.schedule.json()),
            "id/redeem": (200, REDEEMED),
        })

        class QuietDemo(cls.server_module.Demo):
            def log_message(self, *args):
                pass

        QuietDemo.client = DidClient(
            "test-resource-key", "test-licence-key",
            "https://cloud.example/api/v4/", transport=cls.transport)
        cls.http = HTTPServer(("127.0.0.1", 0), QuietDemo)
        cls.thread = threading.Thread(target=cls.http.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:{0}".format(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def setUp(self):
        self.transport.answers["id/redeem"] = (200, REDEEMED)
        self.fod_id = signed_fod_id(
            self.schedule.crypto(1),
            date=self.schedule.start(1) + timedelta(days=1))

    def get(self, fifty_one_did, result="sealed", challenge="abc"):
        url = "{0}/redeem?51did={1}&result={2}&challenge={3}".format(
            self.base, fifty_one_did, urllib.parse.quote(result, safe=""),
            challenge)
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return (response.status,
                        response.headers.get("Content-Type"),
                        response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8")
            error.close()
            return error.code, error.headers.get("Content-Type"), body

    def test_answers_in_the_cloud_shape_with_server_signature_added(self):
        status, content_type, body = self.get(self.fod_id.as_base64_url())
        self.assertEqual(200, status)
        self.assertEqual("application/json", content_type)
        expected = json.loads(REDEEMED)
        expected["serverSignature"] = "verified"
        self.assertEqual(expected, json.loads(body))
        # The redeem the route made carried what the page sent, and the
        # licence key the page never sees, all in the POST body.
        redeem = [r for r in self.transport.requests
                  if r.full_url.endswith("id/redeem")][-1]
        self.assertEqual("POST", redeem.get_method())
        form = {k: v[0] for k, v in urllib.parse.parse_qs(
            redeem.data.decode("ascii")).items()}
        self.assertEqual("sealed", form["result"])
        self.assertEqual("abc", form["challenge"])
        self.assertEqual("test-licence-key", form["license"])
        self.assertEqual(self.fod_id.as_base64_url(), form["51did"])

    def test_forged_envelope_is_named_invalid_by_the_server(self):
        from owid import Crypto
        forged = signed_fod_id(
            Crypto.new(), date=self.schedule.start(1) + timedelta(days=1))
        status, _, body = self.get(forged.as_base64_url())
        self.assertEqual(200, status)
        self.assertEqual("invalid", json.loads(body)["serverSignature"])

    def test_unparseable_identifier_is_a_400_with_errors(self):
        status, content_type, body = self.get("not-a-51did")
        self.assertEqual(400, status)
        self.assertEqual("application/json", content_type)
        self.assertIn("errors", json.loads(body))

    def test_host_without_the_creator_context_answers_404_text(self):
        self.transport.answers["id/redeem"] = (404, "Not Found")
        status, content_type, body = self.get(self.fod_id.as_base64_url())
        self.assertEqual(404, status)
        self.assertTrue(content_type.startswith("text/plain"))
        self.assertEqual("Not Found", body)

    def test_503_unconfirmed_is_relayed_with_the_status(self):
        self.transport.answers["id/redeem"] = (
            503, '{"context":"unconfirmed"}')
        status, _, body = self.get(self.fod_id.as_base64_url())
        self.assertEqual(503, status)
        self.assertEqual("unconfirmed", json.loads(body)["context"])

    def test_cloud_400_is_relayed_as_the_cloud_said_it(self):
        self.transport.answers["id/redeem"] = (
            400, '{"errors":["bad identifier"]}')
        status, content_type, body = self.get(self.fod_id.as_base64_url())
        self.assertEqual(400, status)
        self.assertEqual("application/json", content_type)
        self.assertEqual(["bad identifier"], json.loads(body)["errors"])

    def test_unreachable_cloud_answers_502_with_an_error(self):
        self.transport.answers["id/redeem"] = urllib.error.URLError(
            "connection refused")
        status, content_type, body = self.get(self.fod_id.as_base64_url())
        self.assertEqual(502, status)
        self.assertEqual("application/json", content_type)
        self.assertIn("connection refused", json.loads(body)["error"])


if __name__ == "__main__":
    unittest.main()
