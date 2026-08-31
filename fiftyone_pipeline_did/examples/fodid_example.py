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

"""Offline example for the 51Did (``FodId``) reader.

The 51Degrees Cloud service issues real 51Dids. To keep this example
self-contained and offline, it builds a sample 51Did in process - generate an
ECDSA P-256 key pair, sign a canonical 37-byte payload - then parses it back
and prints the three payload fields. It also shows the headline use case: a
51Did is re-issued fresh on every call (the envelope, hence the base64,
changes), but the match key is stable. Compare match keys, never
envelopes.
"""

from owid import Crypto, Creator

from fiftyone_pipeline_did import FodId

DOMAIN = "51degrees.com"


def sample_payload():
    """A canonical 37-byte Probabilistic payload: flags 0x00, License Id
    0x12345678 (little-endian) and a 32-byte match key 0x20..0x3F."""
    payload = bytearray(FodId.PAYLOAD_LENGTH)
    payload[FodId.FLAGS_OFFSET] = 0x00
    payload[FodId.LICENSE_ID_OFFSET:FodId.LICENSE_ID_OFFSET + 4] = \
        bytes([0x78, 0x56, 0x34, 0x12])
    for i in range(FodId.HASH_LENGTH):
        payload[FodId.HASH_OFFSET + i] = 0x20 + i
    return bytes(payload)


def issue(creator, payload):
    """Issues (signs) a 51Did over the payload and returns it as base64.

    The creator is the only way a new envelope comes into being, because an
    OWID is worth nothing unsigned, so the payload goes in and a signed
    envelope comes out with no unsigned step in between."""
    return creator.create(payload).as_base64()


def run():
    crypto = Crypto.new()
    creator = Creator(DOMAIN, crypto)
    payload = sample_payload()

    fod_id = FodId.from_base64(issue(creator, payload))

    print("51Did parsed from base64:")
    print("  Domain    :", fod_id.domain)
    print("  Type      :", fod_id.type.name)
    print("  Flags     : 0x{:02x}".format(fod_id.flags))
    print("  LicenseId :", fod_id.license_id)
    print("  Match key :", fod_id.match_key.hex())
    print("  Verifies  :", fod_id.verify(crypto.public_key_pem()))

    reissued = FodId.from_base64(issue(creator, payload))
    same_envelope = fod_id.as_base64() == reissued.as_base64()
    same_match_key = fod_id.match_key == reissued.match_key

    print()
    print("Same payload, re-issued:")
    print("  Same envelope (base64) :", same_envelope)
    print("  Same match key         :", same_match_key)

    if same_envelope or not same_match_key:
        raise AssertionError(
            "Expected a different envelope but the same match key across "
            "reissues.")


if __name__ == "__main__":
    run()
