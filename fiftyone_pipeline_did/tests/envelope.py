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

"""Shared builders for the client tests: signed envelopes with a chosen
date and version, a key schedule as the cloud publishes one, and a
transport stand-in that records requests and answers from a script, so no
test touches the network."""

import json
import urllib.parse
from datetime import datetime, timedelta, timezone

from owid import Crypto, Owid, Version

from fiftyone_pipeline_did import FodId

TEST_DOMAIN = "51degrees.com"

#: The OWID epoch, the moment the envelope date counts minutes from.
EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


def probabilistic_payload():
    """A 37 byte payload of the Probabilistic type with recognisable
    bytes."""
    payload = bytearray(FodId.PAYLOAD_LENGTH)
    payload[FodId.FLAGS_OFFSET] = 0b0000_0101
    payload[FodId.LICENSE_ID_OFFSET:FodId.LICENSE_ID_OFFSET + 4] = \
        bytes([0x78, 0x56, 0x34, 0x12])
    for i in range(FodId.HASH_LENGTH):
        payload[FodId.HASH_OFFSET + i] = 0x20 + i
    return bytes(payload)


def random_payload():
    """A 21 byte payload of the Random type."""
    payload = bytearray(FodId.RANDOM_PAYLOAD_LENGTH)
    payload[FodId.FLAGS_OFFSET] = (1 << 6) | 0b001
    for i in range(FodId.GUID_LENGTH):
        payload[FodId.HASH_OFFSET + i] = 0x40 + i
    return bytes(payload)


def context_payload():
    """A Probabilistic payload followed by a 19 byte creator context
    section, the length a version 0 section has on the cloud."""
    return probabilistic_payload() + bytes([0]) + bytes(range(1, 19))


def signed_envelope(crypto, payload, date=None, version=Version.VERSION3,
                    domain=TEST_DOMAIN):
    """An OWID over the payload, signed with the key pair, dated as given
    (to the minute, as the wire format stores it) and stamped with the
    version. The Creator class always writes version 3 and the current
    time, so the fields are set and signed by hand here."""
    if date is None:
        date = datetime.now(timezone.utc)
    owid = Owid(version=version, domain=domain,
                date=date.replace(second=0, microsecond=0),
                payload=bytes(payload))
    owid.signature = crypto.sign_byte_array(owid.data_for_crypto([]))
    return owid


def signed_fod_id(crypto, payload=None, date=None,
                  version=Version.VERSION3):
    """A FodId over a signed envelope, Probabilistic unless a payload is
    given."""
    if payload is None:
        payload = probabilistic_payload()
    return FodId.from_owid(signed_envelope(crypto, payload, date, version))


def iso_round_trip(moment):
    """The moment as the cloud's ``o`` format writes it, with seven
    fractional digits, which is what the key endpoint emits."""
    return moment.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f0Z")


class KeySchedule:
    """Four weekly keys, Monday 00:00 UTC starts, each with its own key
    pair, published the way the cloud publishes them."""

    FIRST_START = datetime(2026, 8, 3, tzinfo=timezone.utc)

    def __init__(self, count=4, spacing=timedelta(days=7)):
        self.entries = []
        for i in range(count):
            crypto = Crypto.new()
            self.entries.append((self.FIRST_START + spacing * i, crypto))

    def start(self, index):
        return self.entries[index][0]

    def crypto(self, index):
        return self.entries[index][1]

    def json(self, start_field="startsAt"):
        """The key list body. ``start_field`` is ``startsAt`` as the
        creator context release emits, or ``created`` as the endpoint
        before it emitted (with the generation time as the only date)."""
        keys = []
        for starts_at, crypto in self.entries:
            entry = {"publicKey": crypto.public_key_pem()}
            if start_field == "startsAt":
                entry["startsAt"] = iso_round_trip(starts_at)
                entry["weekStart"] = iso_round_trip(starts_at)
                entry["created"] = iso_round_trip(
                    starts_at - timedelta(days=90))
            else:
                entry["created"] = iso_round_trip(starts_at)
            keys.append(entry)
        # Newest first, to prove the client sorts rather than trusts the
        # order it was given.
        keys.reverse()
        return json.dumps(keys)


class FakeTransport:
    """A transport that records every request and answers from a script
    keyed on the path segment after the API base. Each answer is a
    ``(status, body)`` pair, or a callable taking the request and returning
    one, or an exception instance to raise."""

    def __init__(self, answers=None):
        self.answers = dict(answers or {})
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        path = urllib.parse.urlparse(request.full_url).path
        for key, answer in self.answers.items():
            if key in path:
                if isinstance(answer, BaseException):
                    raise answer
                if callable(answer):
                    return answer(request)
                status, body = answer
                if isinstance(body, str):
                    body = body.encode("utf-8")
                return status, body
        return 404, b"no answer scripted for " + path.encode("utf-8")

    def count(self, segment):
        """How many recorded requests carry the segment in their path."""
        return sum(1 for r in self.requests
                   if segment in urllib.parse.urlparse(r.full_url).path)

    def last(self):
        return self.requests[-1]


def form_of(request):
    """The form fields of a recorded POST, as a dict of single values."""
    data = request.data.decode("ascii") if request.data else ""
    return {k: v[0] for k, v in urllib.parse.parse_qs(
        data, keep_blank_values=True).items()}


class FixedClock:
    """A clock the tests move by hand."""

    def __init__(self, start):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, delta):
        self.now = self.now + delta
