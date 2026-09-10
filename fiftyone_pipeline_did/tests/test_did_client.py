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

import asyncio
import base64
import json
import os
import struct
import threading
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from unittest import mock

from owid import Crypto, Version

from fiftyone_pipeline_did import (
    DEFAULT_ENDPOINT,
    ContextResult,
    DidArgumentError,
    DidClient,
    DidClientError,
    DidNotSupportedError,
    FactorResult,
    FodId,
    FodIdParseStatus,
    OwidError,
    RedeemResult,
    SignatureReason,
    SignatureResult,
)
from fiftyone_pipeline_did.did_client import USER_AGENT, parse_iso8601
# The byte layout is not part of the package's public surface. These tests
# build payloads byte by byte, so they read it from the private module, as
# https://github.com/51Degrees/specifications/blob/main/did-specification/package-surface.md
# says the package's own tests may.
from fiftyone_pipeline_did._layout import (
    MATCH_KEY_LENGTH,
    MATCH_KEY_OFFSET,
    PAYLOAD_LENGTH,
)

from .envelope import (
    EPOCH,
    FakeTransport,
    FixedClock,
    KeySchedule,
    context_payload,
    envelope_bytes,
    form_of,
    probabilistic_payload,
    random_payload,
    signed_envelope,
    signed_fod_id,
)

RESOURCE = "AQAAAAAAAAA-resource"
LICENCE = "licence-key-value"
ENDPOINT = "https://cloud.example/api/v4/"


def run(coroutine):
    """Runs one client call to completion on a fresh event loop. The
    client's cloud-facing methods are coroutines, and these are plain
    unittest tests with no async runner, so each call is driven this way
    and an exception the call raises surfaces here, where the test
    expects it."""
    return asyncio.run(coroutine)


class FodIdBase64Tests(unittest.TestCase):
    """Section 1 of the run book: both alphabets, the URL-safe form and
    the date the envelope carries."""

    def setUp(self):
        self.crypto = Crypto.new()
        # A payload chosen so the base64 contains both + and / once
        # encoded: every three bytes of 0xFB encode to "+/v7" whatever
        # the alignment, and a 32 byte run holds several whole triples.
        payload = bytearray(probabilistic_payload())
        for i in range(MATCH_KEY_LENGTH):
            payload[MATCH_KEY_OFFSET + i] = 0xFB
        self.fod_id = signed_fod_id(self.crypto, bytes(payload))
        self.standard = self.fod_id.as_base64()
        self.assertTrue("+" in self.standard or "/" in self.standard,
                        "the fixture must exercise both alphabets")

    def test_standard_and_url_safe_forms_parse_to_the_same_envelope(self):
        url_safe = self.fod_id.as_base64_url()
        url_safe_padded = self.standard.replace("+", "-").replace("/", "_")
        self.assertNotEqual(self.standard, url_safe)
        self.assertFalse(url_safe.endswith("="))
        for form in (self.standard, url_safe, url_safe_padded,
                     self.standard.rstrip("=")):
            parsed = FodId.from_base64(form)
            self.assertEqual(self.fod_id.as_byte_array(),
                             parsed.as_byte_array(), form)

    def test_surrounding_whitespace_parses_to_the_same_value(self):
        # A value copied from a header, a form field or a text file
        # can arrive with a newline or a space around it.
        for form in (self.standard + "\n", " " + self.standard,
                     self.standard + " ",
                     " " + self.fod_id.as_base64_url() + "\n"):
            parsed = FodId.from_base64(form)
            self.assertEqual(self.fod_id.as_byte_array(),
                             parsed.as_byte_array(), repr(form))

    def test_as_base64_url_round_trips(self):
        again = FodId.from_base64(self.fod_id.as_base64_url())
        self.assertEqual(self.fod_id.as_base64_url(), again.as_base64_url())
        self.assertEqual(self.standard, again.as_base64())

    def test_helpers_invert_each_other(self):
        url_safe = FodId.to_base64_url(self.standard)
        self.assertNotIn("+", url_safe)
        self.assertNotIn("/", url_safe)
        self.assertNotIn("=", url_safe)
        self.assertEqual(self.standard, FodId.to_standard_base64(url_safe))
        self.assertEqual(self.standard,
                         FodId.to_standard_base64(self.standard))

    def test_date_is_the_envelope_field(self):
        # The envelope carries the date as a count of minutes since the
        # OWID epoch. The typed date is that count read back, so the same
        # fact is pinned through the accessor callers have.
        minutes = 3_456_789
        created = EPOCH + timedelta(minutes=minutes)
        fod_id = signed_fod_id(self.crypto, date=created)
        self.assertEqual(created, fod_id.date)
        # Read the four date bytes straight off the wire: version byte,
        # the domain and its terminator, then the little-endian minutes.
        raw = fod_id.as_byte_array()
        offset = 1 + len(fod_id.domain.encode("utf-8")) + 1
        self.assertEqual(
            minutes, struct.unpack("<I", raw[offset:offset + 4])[0])

    def test_date_of_the_epoch_is_the_epoch(self):
        self.assertEqual(EPOCH, signed_fod_id(self.crypto, date=EPOCH).date)


class ClientConstructionTests(unittest.TestCase):

    def test_resource_key_is_required(self):
        with self.assertRaises(ValueError):
            DidClient("")
        with self.assertRaises(ValueError):
            DidClient(None)

    def test_endpoint_defaults_to_the_public_cloud(self):
        saved = os.environ.pop("FOD_CLOUD_API_URL", None)
        try:
            self.assertEqual(DEFAULT_ENDPOINT, DidClient(RESOURCE).endpoint)
        finally:
            if saved is not None:
                os.environ["FOD_CLOUD_API_URL"] = saved

    def test_endpoint_read_from_the_environment(self):
        saved = os.environ.get("FOD_CLOUD_API_URL")
        os.environ["FOD_CLOUD_API_URL"] = "https://private.example/api/v4"
        try:
            self.assertEqual("https://private.example/api/v4/",
                             DidClient(RESOURCE).endpoint)
        finally:
            if saved is None:
                del os.environ["FOD_CLOUD_API_URL"]
            else:
                os.environ["FOD_CLOUD_API_URL"] = saved

    def test_endpoint_argument_wins_and_is_normalised(self):
        self.assertEqual(ENDPOINT, DidClient(
            RESOURCE, endpoint="https://cloud.example/api/v4").endpoint)
        self.assertEqual(ENDPOINT, DidClient(
            RESOURCE, endpoint="https://cloud.example/api/v4//").endpoint)


class PublicKeyTests(unittest.TestCase):
    """Section 2.1: the key list, its cache and the refetch rules."""

    def setUp(self):
        self.schedule = KeySchedule()
        self.clock = FixedClock(self.schedule.start(1)
                                + timedelta(days=2))
        self.transport = FakeTransport({"id/key/": (200, self.schedule.json())})
        self.client = DidClient(RESOURCE, endpoint=ENDPOINT,
                                transport=self.transport, now=self.clock)

    def test_starts_at_is_read_and_the_list_is_sorted_oldest_first(self):
        keys = run(self.client.public_keys())
        self.assertEqual([self.schedule.start(i) for i in range(4)],
                         [k.starts_at for k in keys])
        self.assertEqual(self.schedule.crypto(0).public_key_pem(),
                         keys[0].public_key)

    def test_request_is_a_get_to_the_key_route_with_user_agent(self):
        run(self.client.public_keys())
        request = self.transport.last()
        self.assertEqual("GET", request.get_method())
        self.assertEqual(ENDPOINT + "id/key/" + RESOURCE, request.full_url)
        self.assertEqual(USER_AGENT, request.get_header("User-agent"))
        self.assertTrue(USER_AGENT.startswith("fiftyone_pipeline_did/"))

    def test_created_is_read_where_starts_at_is_absent(self):
        self.transport.answers["id/key/"] = (
            200, self.schedule.json(start_field="created"))
        keys = run(self.client.public_keys())
        self.assertEqual([self.schedule.start(i) for i in range(4)],
                         [k.starts_at for k in keys])

    def test_second_call_is_a_cache_hit(self):
        run(self.client.public_keys())
        run(self.client.public_keys())
        self.assertEqual(1, self.transport.count("id/key/"))

    def test_key_for_a_covered_date_does_not_refetch(self):
        fod_id = signed_fod_id(self.schedule.crypto(1),
                               date=self.schedule.start(1)
                               + timedelta(days=3))
        key = run(self.client.public_key_for(fod_id))
        run(self.client.public_key_for(fod_id))
        self.assertEqual(self.schedule.start(1), key.starts_at)
        self.assertEqual(1, self.transport.count("id/key/"))

    def test_date_later_than_the_newest_start_refetches_once(self):
        run(self.client.public_keys())
        fod_id = signed_fod_id(self.schedule.crypto(3),
                               date=self.schedule.start(3)
                               + timedelta(days=1))
        key = run(self.client.public_key_for(fod_id))
        # Held from the warm-up, then fetched again because the date is
        # past the newest start held, and not a third time.
        self.assertEqual(2, self.transport.count("id/key/"))
        self.assertEqual(self.schedule.start(3), key.starts_at)
        run(self.client.public_key_for(fod_id))
        self.assertEqual(3, self.transport.count("id/key/"))

    def test_date_past_the_newest_start_on_a_fresh_list_is_not_fetched_twice(
            self):
        # A list fetched for this very call is not fetched again, because
        # nothing newer could have been published in between.
        fod_id = signed_fod_id(self.schedule.crypto(3),
                               date=self.schedule.start(3)
                               + timedelta(days=1))
        self.assertEqual(self.schedule.start(3),
                         run(self.client.public_key_for(fod_id)).starts_at)
        self.assertEqual(1, self.transport.count("id/key/"))

    def test_date_before_the_schedule_refetches_once_and_answers_none(self):
        run(self.client.public_keys())
        fod_id = signed_fod_id(self.schedule.crypto(0),
                               date=self.schedule.start(0)
                               - timedelta(days=1))
        self.assertIsNone(run(self.client.public_key_for(fod_id)))
        self.assertEqual(2, self.transport.count("id/key/"))

    def test_list_older_than_a_day_is_refetched(self):
        run(self.client.public_keys())
        self.clock.advance(timedelta(hours=23))
        run(self.client.public_keys())
        self.assertEqual(1, self.transport.count("id/key/"))
        self.clock.advance(timedelta(hours=2))
        run(self.client.public_keys())
        self.assertEqual(2, self.transport.count("id/key/"))

    def test_non_200_raises_with_status_and_body(self):
        self.transport.answers["id/key/"] = (401, '{"errors":["bad key"]}')
        with self.assertRaises(DidClientError) as raised:
            run(self.client.public_keys())
        self.assertEqual(401, raised.exception.status_code)
        self.assertIn("bad key", raised.exception.body)

    def test_body_that_is_not_a_list_raises(self):
        self.transport.answers["id/key/"] = (200, '{"not":"a list"}')
        with self.assertRaises(DidClientError):
            run(self.client.public_keys())

    def test_iso_8601_forms_the_cloud_writes(self):
        self.assertEqual(
            datetime(2026, 8, 24, tzinfo=timezone.utc),
            parse_iso8601("2026-08-24T00:00:00.0000000Z"))
        self.assertEqual(
            datetime(2026, 8, 7, 9, 15, 32, tzinfo=timezone.utc),
            parse_iso8601("2026-08-07T09:15:32Z"))
        self.assertEqual(
            datetime(2026, 8, 7, 8, 15, 32, tzinfo=timezone.utc),
            parse_iso8601("2026-08-07T09:15:32+01:00"))
        with self.assertRaises(ValueError):
            parse_iso8601("yesterday")


class ConcurrentKeyFetchTests(unittest.TestCase):
    """Concurrent awaits for the key list share one fetch. The scripted
    answer yields to the event loop before answering, so the second call
    really does start while the first fetch is in flight, rather than
    finding the cache already filled."""

    def setUp(self):
        self.schedule = KeySchedule()
        self.transport = FakeTransport({"id/key/": self.slow_answer})
        self.client = DidClient(RESOURCE, endpoint=ENDPOINT,
                                transport=self.transport)

    async def slow_answer(self, request):
        await asyncio.sleep(0.01)
        return 200, self.schedule.json()

    def test_two_concurrent_key_list_requests_make_one_http_call(self):
        async def both():
            return await asyncio.gather(self.client.public_keys(),
                                        self.client.public_keys())
        first, second = asyncio.run(both())
        self.assertEqual(1, self.transport.count("id/key/"))
        self.assertEqual([self.schedule.start(i) for i in range(4)],
                         [k.starts_at for k in first])
        self.assertEqual(first, second)

    def test_concurrent_selections_past_the_newest_start_share_one_fetch(
            self):
        # Each call on its own would fetch again for a date past the
        # newest start held, unless the list was fetched for that very
        # call. A fetch that completes while a call waits is that call's
        # own, so the two share it rather than fetching in turn.
        fod_id = signed_fod_id(self.schedule.crypto(3),
                               date=self.schedule.start(3)
                               + timedelta(days=1))

        async def both():
            return await asyncio.gather(self.client.public_key_for(fod_id),
                                        self.client.public_key_for(fod_id))
        first, second = asyncio.run(both())
        self.assertEqual(1, self.transport.count("id/key/"))
        self.assertEqual(self.schedule.start(3), first.starts_at)
        self.assertEqual(first, second)

    def test_a_later_sequential_call_is_still_a_cache_hit(self):
        run(self.client.public_keys())
        run(self.client.public_keys())
        self.assertEqual(1, self.transport.count("id/key/"))


class KeySelectionTests(unittest.TestCase):
    """Section 2.2 step 3: the key in force and its neighbours within the
    boundary tolerance, checked through the offline verification, which
    is what the selection is for.

    The dates below sit a long way either side of the allowance rather
    than close to it, because these tests are here to prove which key is
    tried and must not record how wide the allowance is."""

    def setUp(self):
        self.schedule = KeySchedule()
        self.transport = FakeTransport({"id/key/": (200, self.schedule.json())})
        self.client = DidClient(RESOURCE, endpoint=ENDPOINT,
                                transport=self.transport)

    def signed_by(self, index, date):
        return signed_fod_id(self.schedule.crypto(index), date=date)

    def test_key_in_force_is_the_latest_start_on_or_before_the_date(self):
        mid_week = self.schedule.start(2) + timedelta(days=3)
        self.assertEqual(self.schedule.start(2),
                         run(self.client.public_key_for(
                             self.signed_by(2, mid_week))).starts_at)
        self.assertEqual(self.schedule.start(2),
                         run(self.client.public_key_for(
                             self.signed_by(2, self.schedule.start(2))))
                         .starts_at)

    def test_earlier_neighbour_within_the_tolerance_after_a_boundary(self):
        # Comfortably inside the allowance, so both keys are tried.
        just_after = self.schedule.start(2) + timedelta(minutes=1)
        self.assertTrue(run(self.client.verify_signature(
            self.signed_by(1, just_after))))
        self.assertTrue(run(self.client.verify_signature(
            self.signed_by(2, just_after))))

    def test_earlier_neighbour_not_tried_beyond_the_tolerance(self):
        # Far enough past the boundary to be outside any allowance.
        later = self.schedule.start(2) + timedelta(hours=1)
        self.assertFalse(run(self.client.verify_signature(
            self.signed_by(1, later))))
        self.assertTrue(run(self.client.verify_signature(
            self.signed_by(2, later))))

    def test_later_neighbour_within_the_tolerance_before_a_boundary(self):
        # Comfortably inside the allowance, so both keys are tried.
        just_before = self.schedule.start(2) - timedelta(minutes=1)
        self.assertTrue(run(self.client.verify_signature(
            self.signed_by(2, just_before))))
        self.assertTrue(run(self.client.verify_signature(
            self.signed_by(1, just_before))))

    def test_later_neighbour_not_tried_beyond_the_tolerance(self):
        # Far enough before the boundary to be outside any allowance.
        earlier = self.schedule.start(2) - timedelta(hours=1)
        self.assertFalse(run(self.client.verify_signature(
            self.signed_by(2, earlier))))

    def test_no_candidate_before_the_schedule(self):
        before = self.schedule.start(0) - timedelta(hours=1)
        check = run(self.client.verify_signature_detailed(
            self.signed_by(0, before)))
        self.assertFalse(check.valid)
        self.assertEqual(SignatureReason.NO_KEY, check.reason)

    def test_key_from_a_much_earlier_period_is_never_tried(self):
        # The key for the first week must not sign something dated in the
        # fourth, which is the rule that makes a leak bounded.
        fourth_week = self.schedule.start(3) + timedelta(days=2)
        check = run(self.client.verify_signature_detailed(
            self.signed_by(0, fourth_week)))
        self.assertFalse(check.valid)
        self.assertEqual(SignatureReason.SIGNATURE, check.reason)


class OfflineVerificationTests(unittest.TestCase):
    """Section 2.2: version, length and signature."""

    def setUp(self):
        self.schedule = KeySchedule()
        self.transport = FakeTransport({"id/key/": (200, self.schedule.json())})
        self.client = DidClient(RESOURCE, endpoint=ENDPOINT,
                                transport=self.transport)
        self.date = self.schedule.start(1) + timedelta(days=2)
        self.crypto = self.schedule.crypto(1)

    def test_true_with_the_real_key(self):
        check = run(self.client.verify_signature_detailed(
            signed_fod_id(self.crypto, date=self.date)))
        self.assertTrue(check.valid)
        self.assertEqual(SignatureReason.VERIFIED, check.reason)

    def test_accepts_the_base64_string_form(self):
        fod_id = signed_fod_id(self.crypto, date=self.date)
        self.assertTrue(run(
            self.client.verify_signature(fod_id.as_base64_url())))

    def test_false_with_the_wrong_key(self):
        check = run(self.client.verify_signature_detailed(
            signed_fod_id(Crypto.new(), date=self.date)))
        self.assertFalse(check.valid)
        self.assertEqual(SignatureReason.SIGNATURE, check.reason)

    def test_false_for_version_2(self):
        fod_id = signed_fod_id(self.crypto, date=self.date,
                               version=Version.VERSION2)
        check = run(self.client.verify_signature_detailed(fod_id))
        self.assertFalse(check.valid)
        self.assertEqual(SignatureReason.VERSION, check.reason)
        # Not a network failure: no key was needed to refuse it.
        self.assertEqual(0, self.transport.count("id/key/"))

    def test_false_for_a_payload_shorter_than_the_base(self):
        # The reader keeps a header-only Reserved payload, so that is the
        # one short shape that reaches the verifier.
        payload = bytes([0b1100_0000, 0, 0, 0, 0])
        fod_id = signed_fod_id(self.crypto, payload=payload, date=self.date)
        check = run(self.client.verify_signature_detailed(fod_id))
        self.assertFalse(check.valid)
        self.assertEqual(SignatureReason.LENGTH, check.reason)

    def test_random_type_base_is_twenty_one_bytes(self):
        fod_id = signed_fod_id(self.crypto, payload=random_payload(),
                               date=self.date)
        self.assertTrue(run(self.client.verify_signature(fod_id)))

    def test_true_for_a_payload_longer_than_the_base(self):
        fod_id = signed_fod_id(self.crypto, payload=context_payload(),
                               date=self.date)
        self.assertGreater(len(fod_id.payload), PAYLOAD_LENGTH)
        self.assertTrue(run(self.client.verify_signature(fod_id)))

    def test_true_for_a_payload_far_longer_than_the_base(self):
        # A context section of a version this package does not know
        # about may be any length, so no upper bound is applied here.
        fod_id = signed_fod_id(
            self.crypto, payload=context_payload() + bytes(200),
            date=self.date)
        self.assertTrue(run(self.client.verify_signature(fod_id)))

    def test_true_for_a_long_creator_domain(self):
        # The creator domain is a deployment parameter, so a
        # self-hosted container may sign with a long one.
        fod_id = signed_fod_id(
            self.crypto, payload=context_payload(), date=self.date,
            domain="identifiers." + ("a" * 120) + ".example")
        self.assertTrue(run(self.client.verify_signature(fod_id)))

    def test_verify_signature_refuses_far_too_long_text(self):
        # Obviously malformed input is refused before it is decoded
        # and before any key is fetched.
        with self.assertRaises(ValueError):
            run(self.client.verify_signature("A" * 5000))
        self.assertEqual(0, self.transport.count("id/key/"))

    def test_public_key_for_refuses_far_too_long_text(self):
        with self.assertRaises(ValueError):
            run(self.client.public_key_for("A" * 5000))
        self.assertEqual(0, self.transport.count("id/key/"))


class CloudVerifyTests(unittest.TestCase):
    """Section 2.3: the verify endpoint."""

    def setUp(self):
        self.transport = FakeTransport()
        self.client = DidClient(RESOURCE, LICENCE, ENDPOINT,
                                transport=self.transport)
        self.fod_id = signed_fod_id(Crypto.new())

    def test_200_valid(self):
        self.transport.answers["id/verify/"] = (200, '{"valid":true}')
        self.assertTrue(run(self.client.verify(self.fod_id)))
        request = self.transport.last()
        self.assertEqual("GET", request.get_method())
        parsed = urllib.parse.urlparse(request.full_url)
        self.assertEqual("/api/v4/id/verify/" + RESOURCE, parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        # Under both names so hosts that read either parameter can verify it.
        self.assertEqual([self.fod_id.as_base64_url()], query["51did"])
        self.assertEqual([self.fod_id.as_base64_url()], query["owid"])
        self.assertEqual({"51did", "owid"}, set(query))
        self.assertNotIn(LICENCE, request.full_url)
        self.assertEqual(USER_AGENT, request.get_header("User-agent"))

    def test_400_invalid(self):
        self.transport.answers["id/verify/"] = (400, '{"valid":false}')
        self.assertFalse(run(self.client.verify(self.fod_id)))

    def test_400_errors_from_the_cloud_raises_the_argument_error(self):
        # A string that parses here can still be refused by the cloud, for
        # example one from a creator the cloud does not know, and the
        # cloud's own message is what the error then carries.
        self.transport.answers["id/verify/"] = (
            400, '{"errors":["Value for 51did is not a 51Did this service '
                 'issued."]}')
        with self.assertRaises(DidArgumentError) as raised:
            run(self.client.verify(self.fod_id.as_base64_url()))
        self.assertIsInstance(raised.exception, ValueError)
        self.assertIn("not a 51Did this service issued",
                      str(raised.exception))
        self.assertEqual(400, raised.exception.status_code)

    def test_string_form_is_sent_as_given_and_encoded(self):
        # A payload of 0xFB bytes encodes to "+/v7" whatever the alignment,
        # so the standard form carries both characters that need encoding.
        payload = bytearray(probabilistic_payload())
        for i in range(MATCH_KEY_LENGTH):
            payload[MATCH_KEY_OFFSET + i] = 0xFB
        standard = signed_fod_id(Crypto.new(), bytes(payload)).as_base64()
        self.assertIn("+", standard)
        self.assertIn("/", standard)
        self.transport.answers["id/verify/"] = (200, '{"valid":true}')
        run(self.client.verify(standard))
        encoded = urllib.parse.quote(standard, safe="")
        self.assertIn("51did=" + encoded, self.transport.last().full_url)
        self.assertIn("owid=" + encoded, self.transport.last().full_url)

    def test_padded_and_unpadded_forms_are_both_accepted(self):
        fod_id = signed_fod_id(Crypto.new(), payload=context_payload())
        self.transport.answers["id/verify/"] = (200, '{"valid":true}')
        self.assertTrue(run(self.client.verify(fod_id.as_base64())))
        self.assertTrue(run(self.client.verify(fod_id.as_base64_url())))
        self.assertEqual(2, self.transport.count("id/verify/"))

    def test_verify_refuses_far_too_long_text_before_transport(self):
        with self.assertRaises(ValueError):
            run(self.client.verify("A" * 5000))
        self.assertEqual(0, len(self.transport.requests))

    def test_other_status_raises_the_client_error(self):
        self.transport.answers["id/verify/"] = (500, "boom")
        with self.assertRaises(DidClientError) as raised:
            run(self.client.verify(self.fod_id))
        self.assertEqual(500, raised.exception.status_code)
        self.assertEqual("boom", raised.exception.body)

    def test_transport_failure_propagates_as_the_io_error(self):
        self.transport.answers["id/verify/"] = urllib.error.URLError(
            "no route to host")
        with self.assertRaises(OSError):
            run(self.client.verify(self.fod_id))


REDEEMED_WITH_FACTORS = json.dumps({
    "signature": "verified",
    "context": "mismatch",
    "factors": {"transport": "verified", "device": "mismatch",
                "browserip": "verified", "connectionip": "verified",
                "asn": None, "browser": "verified"},
    "verifiedAt": "2026-08-07T09:15:32Z",
    "secondsSinceVerified": 2,
})

REDEEMED_WITHOUT_FACTORS = json.dumps({
    "signature": "verified",
    "context": "verified",
    "verifiedAt": "2026-08-07T09:15:32Z",
    "secondsSinceVerified": 1,
})


class RedeemTests(unittest.TestCase):
    """Section 2.4: every redeem outcome and the shape of the request."""

    def setUp(self):
        self.transport = FakeTransport()
        self.client = DidClient(RESOURCE, LICENCE, ENDPOINT,
                                transport=self.transport)
        self.fod_id = signed_fod_id(Crypto.new())

    def redeem(self, status, body, challenge="abc123"):
        self.transport.answers["id/redeem"] = (status, body)
        return run(self.client.redeem(self.fod_id, "sealed-result", challenge))

    def test_request_is_a_post_with_every_field_in_the_body(self):
        self.redeem(200, REDEEMED_WITHOUT_FACTORS)
        request = self.transport.last()
        self.assertEqual("POST", request.get_method())
        self.assertEqual(ENDPOINT + "id/redeem", request.full_url)
        self.assertEqual("application/x-www-form-urlencoded",
                         request.get_header("Content-type"))
        self.assertEqual(USER_AGENT, request.get_header("User-agent"))
        form = form_of(request)
        self.assertEqual({
            "resource": RESOURCE,
            "51did": self.fod_id.as_base64_url(),
            "result": "sealed-result",
            "challenge": "abc123",
            "license": LICENCE,
        }, form)
        # No credential in the URL, because a query string is written to
        # access logs.
        self.assertNotIn(LICENCE, request.full_url)
        self.assertNotIn(RESOURCE, request.full_url)
        self.assertNotIn("?", request.full_url)

    def test_licence_is_omitted_when_none_was_given(self):
        client = DidClient(RESOURCE, endpoint=ENDPOINT,
                           transport=self.transport)
        self.transport.answers["id/redeem"] = (200, REDEEMED_WITHOUT_FACTORS)
        run(client.redeem(self.fod_id, "sealed-result", "abc123"))
        form = form_of(self.transport.last())
        self.assertNotIn("license", form)
        self.assertEqual(RESOURCE, form["resource"])

    def test_redeemed_with_factors(self):
        result = self.redeem(200, REDEEMED_WITH_FACTORS)
        self.assertEqual(200, result.status_code)
        self.assertEqual(ContextResult.MISMATCH, result.context)
        self.assertEqual("mismatch", result.context_raw)
        self.assertEqual(SignatureResult.VERIFIED, result.signature)
        self.assertEqual({
            "transport": FactorResult.VERIFIED,
            "device": FactorResult.MISMATCH,
            "browserip": FactorResult.VERIFIED,
            "connectionip": FactorResult.VERIFIED,
            "asn": None,
            "browser": FactorResult.VERIFIED,
        }, result.factors)
        self.assertEqual(datetime(2026, 8, 7, 9, 15, 32,
                                  tzinfo=timezone.utc), result.verified_at)
        self.assertEqual(2, result.seconds_since_verified)
        self.assertEqual(REDEEMED_WITH_FACTORS, result.raw)

    def test_redeemed_without_factors(self):
        result = self.redeem(200, REDEEMED_WITHOUT_FACTORS)
        self.assertEqual(ContextResult.VERIFIED, result.context)
        self.assertIsNone(result.factors)
        self.assertEqual(1, result.seconds_since_verified)

    def test_to_dict_is_the_cloud_shape(self):
        self.assertEqual(json.loads(REDEEMED_WITH_FACTORS),
                         self.redeem(200, REDEEMED_WITH_FACTORS).to_dict())
        self.assertEqual(json.loads(REDEEMED_WITHOUT_FACTORS),
                         self.redeem(200, REDEEMED_WITHOUT_FACTORS).to_dict())

    def test_expired(self):
        result = self.redeem(200, '{"context":"expired","verifiedAt":'
                                  '"2026-08-07T09:15:32Z",'
                                  '"secondsSinceVerified":14}')
        self.assertEqual(ContextResult.EXPIRED, result.context)
        self.assertEqual(SignatureResult.UNKNOWN, result.signature)
        self.assertEqual(14, result.seconds_since_verified)
        self.assertIsNotNone(result.verified_at)
        self.assertEqual({"context": "expired",
                          "verifiedAt": "2026-08-07T09:15:32Z",
                          "secondsSinceVerified": 14}, result.to_dict())

    def test_replayed(self):
        result = self.redeem(200, '{"context":"replayed"}')
        self.assertEqual(ContextResult.REPLAYED, result.context)
        self.assertIsNone(result.verified_at)
        self.assertIsNone(result.seconds_since_verified)
        self.assertEqual({"context": "replayed"}, result.to_dict())

    def test_unreadable(self):
        result = self.redeem(200, '{"context":"unreadable"}')
        self.assertEqual(ContextResult.UNREADABLE, result.context)

    def test_nocontext_and_notcheckable(self):
        self.assertEqual(ContextResult.NO_CONTEXT, self.redeem(
            200, '{"signature":"verified","context":"nocontext",'
                 '"verifiedAt":"2026-08-07T09:15:32Z",'
                 '"secondsSinceVerified":0}').context)
        self.assertEqual(ContextResult.NOT_CHECKABLE, self.redeem(
            200, '{"signature":"invalid","context":"notcheckable",'
                 '"verifiedAt":"2026-08-07T09:15:32Z",'
                 '"secondsSinceVerified":0}').context)

    def test_503_unconfirmed_is_a_result(self):
        result = self.redeem(503, '{"context":"unconfirmed"}')
        self.assertEqual(503, result.status_code)
        self.assertEqual(ContextResult.UNCONFIRMED, result.context)

    def test_unknown_context_string_maps_to_unreadable_and_keeps_raw(self):
        result = self.redeem(200, '{"context":"somethingnew"}')
        self.assertEqual(ContextResult.UNREADABLE, result.context)
        self.assertEqual("somethingnew", result.context_raw)
        self.assertEqual("unreadable", result.to_dict()["context"])

    def test_400_errors_raises_the_argument_error(self):
        with self.assertRaises(DidArgumentError) as raised:
            self.redeem(400, '{"errors":["\'zzz\' is not a valid '
                             'Base64-encoded 51Did."]}')
        self.assertIn("not a valid Base64-encoded 51Did",
                      str(raised.exception))
        self.assertEqual(400, raised.exception.status_code)

    def test_404_raises_not_supported(self):
        with self.assertRaises(DidNotSupportedError) as raised:
            self.redeem(404, "Not Found")
        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual("Not Found", raised.exception.body)

    def test_other_status_raises_the_client_error(self):
        with self.assertRaises(DidClientError) as raised:
            self.redeem(500, "boom")
        self.assertEqual(500, raised.exception.status_code)
        self.assertNotIsInstance(raised.exception, DidNotSupportedError)
        self.assertNotIsInstance(raised.exception, DidArgumentError)

    def test_200_that_is_not_a_json_object_raises(self):
        with self.assertRaises(DidClientError):
            self.redeem(200, "<html>")

    def test_transport_failure_propagates_as_the_io_error(self):
        self.transport.answers["id/redeem"] = urllib.error.URLError(
            "connection refused")
        with self.assertRaises(OSError):
            run(self.client.redeem(self.fod_id, "sealed-result", "abc123"))

    def test_string_identifier_is_sent_as_given(self):
        # The padded standard form goes as given rather than being
        # converted to the URL-safe form a parsed identifier is sent in.
        text = self.fod_id.as_base64()
        self.assertTrue(text.endswith("="))
        self.transport.answers["id/redeem"] = (200, '{"context":"unreadable"}')
        run(self.client.redeem(text, "sealed-result", None))
        form = form_of(self.transport.last())
        self.assertEqual(text, form["51did"])
        self.assertEqual("", form["challenge"])

    def test_redeem_refuses_far_too_long_text_before_the_form(self):
        with self.assertRaises(ValueError):
            run(self.client.redeem("A" * 5000, "sealed-result"))
        self.assertEqual(0, len(self.transport.requests))

    def test_result_class_can_be_built_from_a_response_directly(self):
        result = RedeemResult.from_response(200, REDEEMED_WITHOUT_FACTORS)
        self.assertEqual(ContextResult.VERIFIED, result.context)


class OpenerTransportTests(unittest.TestCase):
    """An urllib opener is accepted as the transport, with a non-2xx
    answer read from the HTTPError rather than raised."""

    def test_opener_answers_are_read_whatever_the_status(self):
        class Response:
            def __init__(self, status, body):
                self.status = status
                self._body = body

            def read(self):
                return self._body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class Opener:
            def __init__(self):
                self.calls = []

            def open(self, request, timeout=None):
                self.calls.append(request)
                if "id/verify/" in request.full_url:
                    raise urllib.error.HTTPError(
                        request.full_url, 400, "Bad Request", {},
                        _Bytes(b'{"valid":false}'))
                return Response(200, b'{"valid":true}')

        class _Bytes:
            def __init__(self, data):
                self._data = data

            def read(self):
                return self._data

            def close(self):
                pass

        opener = Opener()
        client = DidClient(RESOURCE, endpoint=ENDPOINT, transport=opener)
        self.assertFalse(run(client.verify(
            signed_fod_id(Crypto.new()).as_base64_url())))
        self.assertEqual(1, len(opener.calls))


class TransportContractTests(unittest.TestCase):
    """An injected callable must be an async one. A plain callable that
    answers a tuple is refused by name, so the mistake is named rather
    than failing on the await."""

    def test_plain_callable_transport_is_refused(self):
        def blocking_transport(request):
            return 200, b'{"valid":true}'

        client = DidClient(RESOURCE, endpoint=ENDPOINT,
                           transport=blocking_transport)
        with self.assertRaises(TypeError) as raised:
            run(client.verify(signed_fod_id(Crypto.new())))
        self.assertIn("async callable", str(raised.exception))


class DefaultTransportTests(unittest.TestCase):
    """With no transport injected the client opens the request with
    urllib on a worker thread, passing the timeout it was given. urlopen
    is replaced for the test so nothing leaves the machine."""

    def test_default_transport_is_urlopen_with_the_timeout(self):
        class Response:
            status = 200

            def read(self):
                return b'{"valid":true}'

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append((request, timeout, threading.current_thread()))
            return Response()

        client = DidClient(RESOURCE, endpoint=ENDPOINT, timeout=7.5)
        # asyncio.run drives the loop on the calling thread, so this is
        # the loop's thread.
        loop_thread = threading.current_thread()
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            self.assertTrue(run(client.verify(signed_fod_id(Crypto.new()))))
        self.assertEqual(1, len(calls))
        request, timeout, thread = calls[0]
        self.assertEqual("GET", request.get_method())
        self.assertTrue(request.full_url.startswith(ENDPOINT + "id/verify/"))
        self.assertEqual(7.5, timeout)
        # Blocking I/O kept off the event loop's thread.
        self.assertIsNot(loop_thread, thread)


class MalformedIdentifierTests(unittest.TestCase):
    """A malformed identifier is refused by the offline surfaces before
    any key is fetched, and the parser's answer is separate from the
    client's guard on obviously oversized text."""

    def setUp(self):
        self.schedule = KeySchedule()
        self.transport = FakeTransport({"id/key/": (200, self.schedule.json())})
        self.client = DidClient(RESOURCE, LICENCE, ENDPOINT,
                                transport=self.transport)
        self.date = self.schedule.start(1) + timedelta(days=2)
        self.crypto = self.schedule.crypto(1)

    def malformed(self):
        """Text the parser refuses, one case per kind of refusal: not
        base64, an absent envelope marker, a truncated envelope, and an
        envelope whose payload is too short for its type."""
        raw = signed_fod_id(self.crypto, date=self.date).as_byte_array()
        short = envelope_bytes(
            self.crypto, random_payload()[:-1], date=self.date)
        return (
            "not-a-51did!!",
            "AA",
            FodId.to_base64_url(base64.b64encode(raw[:6]).decode()),
            FodId.to_base64_url(base64.b64encode(short).decode()),
        )

    def test_offline_surfaces_refuse_malformed_text_before_any_key_fetch(
            self):
        for text in self.malformed():
            for call in (self.client.verify_signature,
                         self.client.verify_signature_detailed,
                         self.client.public_key_for):
                with self.assertRaises((OwidError, ValueError), msg=text):
                    run(call(text))
        self.assertEqual(0, len(self.transport.requests))

    def test_parser_names_the_reason_before_the_client_is_asked(self):
        expected = (FodIdParseStatus.INVALID_BASE64,
                    FodIdParseStatus.ABSENT_NODE,
                    FodIdParseStatus.UNEXPECTED_END,
                    FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)
        for text, status in zip(self.malformed(), expected):
            result = FodId.try_from_base64(text)
            self.assertFalse(result.ok, text)
            self.assertIsNone(result.value)
            self.assertIs(status, result.status)
        self.assertEqual(0, len(self.transport.requests))

    def test_cloud_surfaces_refuse_malformed_text_before_any_transport(
            self):
        for text in self.malformed():
            with self.assertRaises(DidArgumentError, msg=text) as raised:
                run(self.client.verify(text))
            self.assertIsInstance(raised.exception, ValueError)
            # Refused here, so there is no cloud status to carry.
            self.assertIsNone(raised.exception.status_code)
            with self.assertRaises(DidArgumentError, msg=text):
                run(self.client.redeem(text, "sealed-result", "abc"))
        self.assertEqual(0, len(self.transport.requests))

    def test_cloud_surface_refusal_names_the_parse_status(self):
        expected = (FodIdParseStatus.INVALID_BASE64,
                    FodIdParseStatus.ABSENT_NODE,
                    FodIdParseStatus.UNEXPECTED_END,
                    FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)
        for text, status in zip(self.malformed(), expected):
            with self.assertRaises(DidArgumentError) as raised:
                run(self.client.redeem(text, "sealed-result", "abc"))
            self.assertIn(status.value, str(raised.exception))
        self.assertEqual(0, len(self.transport.requests))

    def test_tampered_signature_parses_then_verifies_as_signature(self):
        raw = bytearray(
            signed_fod_id(self.crypto, date=self.date).as_byte_array())
        raw[-1] ^= 0xFF
        result = FodId.try_from_byte_array(bytes(raw))
        self.assertTrue(result.ok)
        check = run(self.client.verify_signature_detailed(result.value))
        self.assertFalse(check.valid)
        self.assertEqual(SignatureReason.SIGNATURE, check.reason)

    def test_no_key_for_the_date_is_not_reported_as_a_bad_signature(self):
        before = self.schedule.start(0) - timedelta(days=30)
        check = run(self.client.verify_signature_detailed(
            signed_fod_id(self.crypto, date=before)))
        self.assertFalse(check.valid)
        self.assertEqual(SignatureReason.NO_KEY, check.reason)
        self.assertNotEqual(SignatureReason.SIGNATURE, check.reason)

    def test_key_fetch_failure_is_an_error_not_a_verdict(self):
        self.transport.answers["id/key/"] = urllib.error.URLError(
            "no route to host")
        with self.assertRaises(OSError):
            run(self.client.verify_signature(
                signed_fod_id(self.crypto, date=self.date)))
        self.transport.answers["id/key/"] = (500, "boom")
        with self.assertRaises(DidClientError):
            run(self.client.verify_signature_detailed(
                signed_fod_id(self.crypto, date=self.date)))

    def test_oversized_text_is_the_client_guard_not_a_parse_status(self):
        # The parser has no size limit of its own and answers the oversized
        # text with an ordinary result, whilst the client refuses the same
        # text as an argument failure before parsing it or fetching a key.
        text = "A" * 5000
        result = FodId.try_from_base64(text)
        self.assertFalse(result.ok)
        self.assertIsInstance(result.status, FodIdParseStatus)
        with self.assertRaises(ValueError):
            run(self.client.verify_signature(text))
        self.assertEqual(0, len(self.transport.requests))


if __name__ == "__main__":
    unittest.main()
