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

import asyncio
import json
import os
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request

from fiftyone_pipeline_did import (
    ContextResult,
    DidClient,
    DidNotSupportedError,
    FodId,
    IdType,
    Usage,
)
from fiftyone_pipeline_did.did_client import USER_AGENT

RESOURCE_KEY = os.environ.get("resource_key") \
    or os.environ.get("_51DEGREES_RESOURCE_KEY")
LICENCE_KEY = os.environ.get("license_key") \
    or os.environ.get("_51DEGREES_LICENSE_KEY")


def run(coroutine):
    """Runs one client call to completion on a fresh event loop, as the
    client's cloud-facing methods are coroutines and these are plain
    unittest tests."""
    return asyncio.run(coroutine)


@unittest.skipUnless(
    RESOURCE_KEY,
    "set resource_key (or _51DEGREES_RESOURCE_KEY) to run the live tests")
class DidClientLiveTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = DidClient(RESOURCE_KEY, LICENCE_KEY)

    def create(self):
        """Creates a 51Did through the cloud ``json`` endpoint, the route
        the cloud request engine calls, for this test's own connection.

        ``id.usage`` is required. Without it the service takes the caller
        as not having asked for a 51Did at all and creates none.
        """
        url = "{0}{1}.json?id.usage=non-marketing".format(
            self.client.endpoint,
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
        self.assertIsNotNone(run(self.client.public_key_for(fod_id)))
        self.assertTrue(run(self.client.verify_signature(fod_id)))
        self.assertTrue(run(self.client.verify(fod_id)))
        # The URL-safe form a page would send round-trips through the
        # cloud as well.
        self.assertTrue(run(self.client.verify(fod_id.as_base64_url())))

    def test_garbage_result_redeems_as_unreadable(self):
        fod_id = self.create()
        try:
            result = run(self.client.redeem(fod_id, "not-base64url!!", "x"))
        except DidNotSupportedError as error:
            self.skipTest("the host does not offer the creator context: "
                          + str(error))
        self.assertEqual(200, result.status_code)
        self.assertEqual(ContextResult.UNREADABLE, result.context)


    # The versioned Model Terms for Marketing document a marketing 51Did is
    # created under. Written out here rather than read from the package,
    # because a test that asked the package what it expects would agree
    # with itself whatever the package said. The literal is what a receiver
    # has to be able to fetch.
    MODEL_TERMS_FOR_MARKETING_2 = "https://m4ow.uk/mtm/2.txt"

    def identifiers_for(self, name, value):
        """Asks the ``json`` endpoint for a 51Did with the given query
        parameter and returns every identifier it answered with. An empty
        list means the resource key is not entitled to that usage, which
        the caller reports rather than fails."""
        url = "{0}{1}.json?{2}&values=FODiD.IdProbGlobal" \
              "&values=FODiD.IdProbLic".format(
                  self.client.endpoint,
                  urllib.parse.quote(RESOURCE_KEY, safe=""),
                  urllib.parse.urlencode({name: value}))
        request = urllib.request.Request(
            url, data=b"", headers={"User-Agent": USER_AGENT},
            method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        fodid = body.get("fodid") or {}
        return [
            FodId.from_base64(fodid[field])
            for field in ("idprobglobal", "idproblic")
            if fodid.get(field)
        ]

    def assert_aligned(self, label, fod_id, usage, terms, indirect):
        """Asserts the terms and every field the flags byte carries, read
        through the accessors rather than by masking. The usage values are
        cumulative, being 001, 011 and 111, so a caller masking the byte
        for the non-marketing bit reads every marketing identifier as
        non-marketing."""
        self.assertEqual(usage, fod_id.usage, label + ": usage")
        self.assertEqual(
            indirect, fod_id.usage_is_indirect,
            label + ": whether the usage is indirect")
        self.assertEqual(terms, fod_id.terms, label + ": terms")
        self.assertEqual(
            IdType.PROBABILISTIC, fod_id.type,
            label + ": an idprob* value must be a probabilistic identifier")

    def test_every_usage_reads_back_the_terms_and_flags(self):
        """Every ``id.usage`` the service offers, read back through the
        package.

        A non-marketing identifier may not reach a demand source at all, so
        there is nothing for a receiver to agree to and it states no terms.
        The two marketing usages both carry the Model Terms for Marketing,
        and those are the rows that show the service wrote the byte,
        because an identifier from a service predating the Terms release
        ends at the match key and reads as no terms.
        """
        cases = [
            ("non-marketing", Usage.NON_MARKETING, None),
            ("standard", Usage.STANDARD, self.MODEL_TERMS_FOR_MARKETING_2),
            ("personalized", Usage.PERSONALIZED,
             self.MODEL_TERMS_FOR_MARKETING_2),
        ]

        checked = 0
        for name, usage, terms in cases:
            identifiers = self.identifiers_for("id.usage", name)
            if not identifiers:
                print("id.usage={0}: no identifier returned, so this key is "
                      "not entitled to that usage.".format(name),
                      file=sys.stderr)
                continue
            for index, fod_id in enumerate(identifiers):
                self.assert_aligned(
                    "{0}[{1}]".format(name, index), fod_id, usage, terms,
                    False)
            if terms is not None:
                checked += len(identifiers)

        # Reported as a skip rather than printed, because a runner shows
        # the counts and not the output, so a run that proved nothing would
        # otherwise look identical to one that proved everything.
        if checked == 0:
            self.skipTest(
                "this resource key returned no marketing 51Did, so no terms "
                "address was read and this run did not prove it; use a key "
                "entitled to the standard or personalized usage")

    def test_consent_string_sets_the_usage_is_indirect_bit(self):
        """A consent management platform sends an IAB TCF consent string
        and no usage of its own. The service decodes the string, decides
        the usage from the purposes it grants, and records in the
        identifier that the usage is indirect, which is bit 3 of the flags
        byte. A consent string is the only indirect signal today.

        This is the half a caller cannot state for itself. An identifier
        whose usage was stated in the request and one whose usage was
        decoded from a consent string are both legitimate, and they are
        different assertions about how the permission was obtained, so a
        receiver has to be able to tell them apart.

        The strings are the ones the cloud's own IabTcfElement tests use,
        repeated here rather than shared, for the same reason as the
        address above. The first grants all twelve purposes and the second
        the Appendix 1 standard set of 1, 2, 7, 8 and 11.
        """
        cases = [
            ("AAAAAAAAAAAAAAAAAAAAAAAAAP_w", Usage.PERSONALIZED),
            ("AAAAAAAAAAAAAAAAAAAAAAAAAMMg", Usage.STANDARD),
        ]

        proven = 0
        for tc_string, usage in cases:
            # No id.usage is sent. A stated usage wins over a consent
            # string, so sending one would leave the bit clear and this
            # would prove the opposite of what it says.
            identifiers = self.identifiers_for("tcstring", tc_string)
            if not identifiers:
                print("consent string granting {0}: no identifier returned, "
                      "so this key is not entitled to that marketing "
                      "usage.".format(usage), file=sys.stderr)
                continue
            for index, fod_id in enumerate(identifiers):
                # A consent string granting a marketing usage produces a
                # marketing identifier, so the terms travel with it too.
                self.assert_aligned(
                    "consent/{0}[{1}]".format(usage, index), fod_id, usage,
                    self.MODEL_TERMS_FOR_MARKETING_2, True)
            proven += len(identifiers)

        # Same reasoning as the usage test above.
        if proven == 0:
            self.skipTest(
                "this resource key returned no identifier for either consent "
                "string, so the usage is indirect bit was never read and "
                "this run did not prove it")

@unittest.skipUnless(
    RESOURCE_KEY,
    "set resource_key (or _51DEGREES_RESOURCE_KEY) to run the live tests")
class BrowserCreatorContextLiveTests(unittest.TestCase):
    """The whole browser path against the live service, as a page runs it.

    A page is told to run snippets and send what they collect, and only
    then does the service create a 51Did, so these tests present
    themselves as a browser and send those values. The context is then
    verified from the same browser, which redeems as verified, and from a
    different one, which redeems as a mismatch naming the factors that
    moved. The factor names are written out here because they are the
    service's contract with every one of these packages, and a name the
    service adds, drops or renames has to be seen here rather than by a
    customer.
    """

    # A browser the service will judge as a browser, and a second one
    # whose device and browser differ from the first.
    CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
              " (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    SAFARI = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
              " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4"
              " Safari/605.1.15")

    # What the 51Degrees client script collects and sends. The names are
    # the service's, and it lists them in the reason it gives when they
    # are missing.
    SNIPPETS = {
        "51D_ScreenPixelsHeight": "1080",
        "51D_ScreenPixelsWidth": "1920",
        "51D_PixelRatio": "1",
        "51D_GetHighEntropyValues": (
            "eyJicmFuZHMiOlt7ImJyYW5kIjoiQ2hyb21pdW0iLCJ2ZXJzaW9uIjoiMTQwIn1d"
            "LCJwbGF0Zm9ybSI6IldpbmRvd3MiLCJwbGF0Zm9ybVZlcnNpb24iOiIxNS4wLjAifQ"),
        "51D_ThirdPartyCookiesEnabled": "true",
    }

    FACTORS = (
        "transport", "device", "browserip", "connectionip", "asn",
        "platformname", "platformversion", "browsername", "browserversion")

    @classmethod
    def setUpClass(cls):
        cls.client = DidClient(RESOURCE_KEY, LICENCE_KEY)

    def get(self, url, user_agent):
        request = urllib.request.Request(
            url, headers={"User-Agent": user_agent}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8")

    def create(self, usage="standard"):
        """Creates a 51Did the way a page does, sending the snippet values
        with the request, and returns it."""

        query = dict(self.SNIPPETS)
        query["id.usage"] = usage
        url = "{0}{1}.json?{2}".format(
            self.client.endpoint, urllib.parse.quote(RESOURCE_KEY, safe=""),
            urllib.parse.urlencode(query))
        status, body = self.get(url, self.CHROME)
        self.assertEqual(200, status, body[:300])
        fodid = json.loads(body).get("fodid") or {}
        value = fodid.get("idproblic") or fodid.get("idprobglobal")
        if not value:
            self.skipTest(
                "this resource key returned no identifier for a browser "
                "shaped request: " + json.dumps(fodid)[:300])
        return FodId.from_base64(value)

    def verify_context(self, fod_id, user_agent):
        """Step one of the browser check, the call the page makes, which
        answers with a sealed result the page cannot read."""

        query = dict(self.SNIPPETS)
        query["51did"] = fod_id.as_base64()
        url = "{0}id/verify-context/{1}?{2}".format(
            self.client.endpoint, urllib.parse.quote(RESOURCE_KEY, safe=""),
            urllib.parse.urlencode(query))
        status, body = self.get(url, user_agent)
        if status == 404:
            self.skipTest("the host does not offer the creator context")
        self.assertEqual(200, status, body[:300])
        answer = json.loads(body)
        if "result" not in answer:
            self.skipTest(
                "this host holds no context secret, so it answered in the "
                "open with " + body[:200])
        return answer["result"]

    def test_a_page_creates_reads_back_verifies_and_redeems(self):
        fod_id = self.create()
        self.assertEqual(Usage.STANDARD, fod_id.usage)
        self.assertEqual(IdType.PROBABILISTIC, fod_id.type)
        self.assertTrue(run(self.client.verify_signature(fod_id)))
        self.assertTrue(run(self.client.verify(fod_id)))
        result = self.verify_context(fod_id, self.CHROME)
        redeemed = run(self.client.redeem(fod_id, result))
        if not self.client.has_licence_key:
            # Without a licence key the sealed result cannot be opened,
            # which the service reports as unreadable.
            self.assertEqual(ContextResult.UNREADABLE, redeemed.context)
            self.skipTest("set license_key to redeem a sealed result")
        self.assertEqual(ContextResult.VERIFIED, redeemed.context)
        self.assertEqual("verified", redeemed.signature.value)

    def test_another_browser_redeems_as_a_mismatch_naming_every_factor(self):
        if not LICENCE_KEY:
            self.skipTest("set license_key to redeem a sealed result")
        fod_id = self.create()
        result = self.verify_context(fod_id, self.SAFARI)
        redeemed = run(self.client.redeem(fod_id, result))
        self.assertEqual(ContextResult.MISMATCH, redeemed.context)
        self.assertEqual("verified", redeemed.signature.value,
                         "the identifier is genuine whichever browser "
                         "presents it")
        self.assertIsNotNone(redeemed.factors,
                             "a mismatch says which factors moved")
        self.assertEqual(sorted(self.FACTORS), sorted(redeemed.factors),
                         "the service reported a different set of factors "
                         "from the one this package documents")
        for name in ("browsername", "browserversion"):
            self.assertEqual("mismatch", redeemed.factors[name].value,
                             name + " must differ between the two browsers")


if __name__ == "__main__":
    unittest.main()
