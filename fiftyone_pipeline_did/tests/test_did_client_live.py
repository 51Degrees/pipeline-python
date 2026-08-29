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

"""Live tests against the cloud, run only when a resource key is set.

The key is read from ``resource_key``, the variable the repository's other
live tests and its CI use, or from ``_51DEGREES_RESOURCE_KEY`` as the
example reads it. Without either the tests are skipped, not failed. An
optional licence key is read from ``license_key`` or
``_51DEGREES_LICENSE_KEY``, and the endpoint from ``FOD_CLOUD_API_URL`` as
everywhere else. Every test here costs uses against the resource key.
"""

import json
import os
import unittest
import urllib.parse
import urllib.request

from fiftyone_pipeline_did import (
    ContextResult,
    DidClient,
    DidNotSupportedError,
    FodId,
)
from fiftyone_pipeline_did.did_client import USER_AGENT

RESOURCE_KEY = os.environ.get("resource_key") \
    or os.environ.get("_51DEGREES_RESOURCE_KEY")
LICENCE_KEY = os.environ.get("license_key") \
    or os.environ.get("_51DEGREES_LICENSE_KEY")


@unittest.skipUnless(
    RESOURCE_KEY,
    "set resource_key (or _51DEGREES_RESOURCE_KEY) to run the live tests")
class DidClientLiveTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = DidClient(RESOURCE_KEY, LICENCE_KEY)

    def create(self):
        """Creates a 51Did through the cloud ``json`` endpoint, the route
        the cloud request engine calls, for this test's own connection."""
        url = "{0}{1}.json".format(self.client.endpoint,
                                   urllib.parse.quote(RESOURCE_KEY, safe=""))
        request = urllib.request.Request(
            url, data=b"", headers={"User-Agent": USER_AGENT},
            method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        fodid = body.get("fodid") or {}
        value = fodid.get("idproblic") or fodid.get("idprobglobal")
        self.assertTrue(
            value, "the resource key must include a 51Did property "
                   "(idprobglobal or idproblic); the json answer was: "
                   + json.dumps(body)[:300])
        return FodId.from_base64(value)

    def test_created_identifier_verifies_offline_and_through_the_cloud(self):
        fod_id = self.create()
        self.assertIsNotNone(self.client.public_key_for(fod_id))
        self.assertTrue(self.client.verify_signature(fod_id))
        self.assertTrue(self.client.verify(fod_id))
        # The URL-safe form a page would send round-trips through the
        # cloud as well.
        self.assertTrue(self.client.verify(fod_id.as_base64_url()))

    def test_garbage_result_redeems_as_unreadable(self):
        fod_id = self.create()
        try:
            result = self.client.redeem(fod_id, "not-base64url!!", "x")
        except DidNotSupportedError as error:
            self.skipTest("the host does not offer the creator context: "
                          + str(error))
        self.assertEqual(200, result.status_code)
        self.assertEqual(ContextResult.UNREADABLE, result.context)


if __name__ == "__main__":
    unittest.main()
