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

import base64
import unittest
from datetime import datetime, timezone

from owid import Owid, Crypto, Creator, OwidError

from fiftyone_pipeline_did import FodId, IdType

TEST_DOMAIN = "51degrees.com"
# 0xA5: usage bits plus the HashedEmail type tag in bits 6-7.
CANONICAL_FLAGS = 0xA5
CANONICAL_LICENSE_ID = 0x12345678
CANONICAL_HASH = bytes((0x20 + i) for i in range(FodId.HASH_LENGTH))


def _write_license_id(payload):
    # Little-endian: low byte first (0x12345678 -> 78 56 34 12).
    payload[FodId.LICENSE_ID_OFFSET] = 0x78
    payload[FodId.LICENSE_ID_OFFSET + 1] = 0x56
    payload[FodId.LICENSE_ID_OFFSET + 2] = 0x34
    payload[FodId.LICENSE_ID_OFFSET + 3] = 0x12


def canonical_payload():
    payload = bytearray(FodId.PAYLOAD_LENGTH)
    payload[FodId.FLAGS_OFFSET] = CANONICAL_FLAGS
    _write_license_id(payload)
    payload[FodId.HASH_OFFSET:FodId.HASH_OFFSET + FodId.HASH_LENGTH] = \
        CANONICAL_HASH
    return bytearray(payload)


def canonical_random_payload():
    payload = bytearray(FodId.RANDOM_PAYLOAD_LENGTH)
    payload[FodId.FLAGS_OFFSET] = (1 << 6) | 0b001  # Random tag + usage bits
    _write_license_id(payload)
    for i in range(FodId.GUID_LENGTH):
        payload[FodId.HASH_OFFSET + i] = 0x40 + i
    return bytearray(payload)


class FodIdTestFactory:
    """Generates a fresh ECDSA P-256 key pair and signs real OWID envelopes."""

    def __init__(self):
        crypto = Crypto.new()
        self.public_pem = crypto.public_key_pem()
        self._creator = Creator(TEST_DOMAIN, crypto)

    def signed_owid(self, payload):
        owid = Owid(domain=TEST_DOMAIN, payload=bytes(payload))
        self._creator.sign(owid)
        return owid

    def signed_owid_base64(self, payload):
        return self.signed_owid(payload).as_base64()


class FodIdTests(unittest.TestCase):

    def setUp(self):
        self.factory = FodIdTestFactory()

    # ----- Current .NET coverage -----

    def test_constants_are_internally_consistent(self):
        self.assertEqual(FodId.HASH_OFFSET + FodId.HASH_LENGTH,
                         FodId.PAYLOAD_LENGTH)
        self.assertEqual(FodId.LICENSE_ID_OFFSET + FodId.LICENSE_ID_LENGTH,
                         FodId.HASH_OFFSET)
        self.assertEqual(FodId.HASH_OFFSET + FodId.GUID_LENGTH,
                         FodId.RANDOM_PAYLOAD_LENGTH)
        self.assertEqual(136, FodId.MAXIMUM_BYTE_LENGTH)

    def test_exposes_owid_level_fields(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        # OWID-level concerns are delegated to the wrapped envelope.
        self.assertEqual(TEST_DOMAIN, fod.domain)
        self.assertIsNotNone(fod.version)

    def test_from_base64_unpacks_all_three_fields(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(TEST_DOMAIN, fod.domain)

    def test_from_byte_array_unpacks_all_three_fields(self):
        buffer = self.factory.signed_owid(canonical_payload()).as_byte_array()
        fod = FodId.from_byte_array(buffer)
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(TEST_DOMAIN, fod.domain)

    def test_from_owid_unpacks_all_three_fields(self):
        owid = self.factory.signed_owid(canonical_payload())
        fod = FodId.from_owid(owid)
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(owid.domain, fod.domain)
        self.assertEqual(owid.date, fod.date)
        self.assertEqual(owid.version, fod.version)
        self.assertEqual(owid.payload, fod.payload)
        self.assertEqual(owid.signature, fod.signature)

    def test_none_owid_raises(self):
        with self.assertRaises(TypeError):
            FodId.from_owid(None)

    def test_license_id_is_little_endian(self):
        payload = canonical_payload()
        payload[FodId.LICENSE_ID_OFFSET:FodId.LICENSE_ID_OFFSET + 4] = \
            bytes([0x01, 0x00, 0x00, 0x00])
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(1, fod.license_id)

    def test_license_id_max_value(self):
        payload = canonical_payload()
        payload[FodId.LICENSE_ID_OFFSET:FodId.LICENSE_ID_OFFSET + 4] = \
            bytes([0xFF, 0xFF, 0xFF, 0xFF])
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(4294967295, fod.license_id)

    def test_license_id_high_bit_stays_unsigned(self):
        payload = canonical_payload()
        payload[FodId.LICENSE_ID_OFFSET:FodId.LICENSE_ID_OFFSET + 4] = \
            bytes([0x00, 0x00, 0x00, 0x80])
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(0x80000000, fod.license_id)

    def test_flags_zero_value_exposed(self):
        payload = canonical_payload()
        payload[FodId.FLAGS_OFFSET] = 0x00
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(0, fod.flags)

    def test_flags_all_bits_set_exposed(self):
        payload = canonical_payload()
        payload[FodId.FLAGS_OFFSET] = 0xFF
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(255, fod.flags)

    def test_hash_is_immutable_value(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertIsInstance(fod.hash, bytes)
        # bytes is immutable, so the value cannot be used to mutate the OWID.
        with self.assertRaises(TypeError):
            fod.hash[0] = 0x00

    def test_payload_one_byte_short_raises(self):
        base64 = self.factory.signed_owid_base64(
            bytearray(FodId.PAYLOAD_LENGTH - 1))
        with self.assertRaises(ValueError):
            FodId.from_base64(base64)

    def test_payload_empty_raises(self):
        base64 = self.factory.signed_owid_base64(bytearray(0))
        with self.assertRaises(ValueError):
            FodId.from_base64(base64)

    def test_none_base64_raises(self):
        with self.assertRaises(TypeError):
            FodId.from_base64(None)

    def test_none_buffer_raises(self):
        with self.assertRaises(TypeError):
            FodId.from_byte_array(None)

    def test_invalid_base64_raises(self):
        with self.assertRaises(OwidError):
            FodId.from_base64("This is not valid Base64!@#$")

    def test_maximum_length_uses_first_37_payload_bytes(self):
        payload = bytearray(56)
        payload[0:FodId.PAYLOAD_LENGTH] = canonical_payload()
        for i in range(FodId.PAYLOAD_LENGTH, len(payload)):
            payload[i] = 0xCC
        owid = Owid(
            domain="51d.es", payload=bytes(payload), signature=bytes(64))
        wire = owid.as_byte_array()
        self.assertEqual(FodId.MAXIMUM_BYTE_LENGTH, len(wire))
        fod = FodId.from_byte_array(wire)
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(FodId.HASH_LENGTH, len(fod.hash))

    def test_one_byte_beyond_maximum_raises_for_every_input(self):
        payload = bytearray(57)
        payload[0:FodId.PAYLOAD_LENGTH] = canonical_payload()
        owid = Owid(
            domain="51d.es", payload=bytes(payload), signature=bytes(64))
        wire = owid.as_byte_array()
        encoded = owid.as_base64()
        self.assertEqual(FodId.MAXIMUM_BYTE_LENGTH + 1, len(wire))

        with self.assertRaises(ValueError):
            FodId.from_base64(encoded)
        with self.assertRaises(ValueError):
            FodId.from_byte_array(wire)
        with self.assertRaises(ValueError):
            FodId.from_owid(owid)

    def test_oversized_payload_in_short_envelope_explains_payload(self):
        payload = bytearray(57)
        payload[0:FodId.PAYLOAD_LENGTH] = canonical_payload()
        owid = Owid(domain="x", payload=bytes(payload), signature=bytes(64))
        wire = owid.as_byte_array()
        encoded = owid.as_base64()
        self.assertLessEqual(len(wire), FodId.MAXIMUM_BYTE_LENGTH)

        for construct in (
            lambda: FodId.from_base64(encoded),
            lambda: FodId.from_byte_array(wire),
            lambda: FodId.from_owid(owid),
        ):
            with self.assertRaisesRegex(
                    ValueError, r"payload must not exceed 56 bytes"):
                construct()

    def test_is_cryptographically_verifiable(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        self.assertTrue(fod.verify(self.factory.public_pem))

    def test_base64_roundtrip_preserves_all_fields(self):
        fod1 = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        fod2 = FodId.from_base64(fod1.as_base64())
        self.assertEqual(fod1.flags, fod2.flags)
        self.assertEqual(fod1.license_id, fod2.license_id)
        self.assertEqual(fod1.hash, fod2.hash)
        self.assertEqual(fod1.domain, fod2.domain)

    # ----- Type model -----

    def test_type_decoded_from_top_two_flag_bits(self):
        self.assertEqual(IdType.PROBABILISTIC, self._type_for(0b0000_0101))
        self.assertEqual(IdType.HASHED_EMAIL, self._type_for(0b1000_0101))
        self.assertEqual(IdType.RESERVED, self._type_for(0b1100_0101))

    def _type_for(self, flags):
        payload = canonical_payload()
        payload[FodId.FLAGS_OFFSET] = flags
        return FodId.from_base64(
            self.factory.signed_owid_base64(payload)).type

    def test_type_random_when_bits_01(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_random_payload()))
        self.assertEqual(IdType.RANDOM, fod.type)

    def test_random_payload_21_bytes_parses(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_random_payload()))
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(FodId.GUID_LENGTH, len(fod.hash))
        self.assertEqual(bytes((0x40 + i) for i in range(FodId.GUID_LENGTH)),
                         fod.hash)

    def test_random_payload_one_byte_short_raises(self):
        payload = canonical_random_payload()[:FodId.RANDOM_PAYLOAD_LENGTH - 1]
        base64 = self.factory.signed_owid_base64(payload)
        with self.assertRaises(ValueError):
            FodId.from_base64(base64)

    def test_random_payload_larger_than_spec_uses_first_16_value_bytes(self):
        payload = bytearray(FodId.PAYLOAD_LENGTH)
        payload[0:FodId.RANDOM_PAYLOAD_LENGTH] = canonical_random_payload()
        for i in range(FodId.RANDOM_PAYLOAD_LENGTH, len(payload)):
            payload[i] = 0xCC
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(IdType.RANDOM, fod.type)
        self.assertEqual(FodId.GUID_LENGTH, len(fod.hash))

    def test_hashed_email_payload_one_byte_short_raises(self):
        payload = canonical_payload()[:FodId.PAYLOAD_LENGTH - 1]
        base64 = self.factory.signed_owid_base64(payload)
        with self.assertRaises(ValueError):
            FodId.from_base64(base64)

    def test_reserved_header_only_parses(self):
        payload = bytearray(FodId.HASH_OFFSET)
        payload[FodId.FLAGS_OFFSET] = 0b1100_0000
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(IdType.RESERVED, fod.type)
        self.assertEqual(0, len(fod.hash))

    # ----- Gap tests (runbook section 6b) -----

    def test_compare_two_51dids_same_payload(self):
        payload = canonical_payload()
        a = self.factory.signed_owid(payload)
        b = self.factory.signed_owid(payload)
        # sign() stamps "now" to the minute, so set distinct dates to
        # represent two reissues at different times.
        a.date = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        b.date = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)

        fa = FodId.from_base64(a.as_base64())
        fb = FodId.from_base64(b.as_base64())

        self.assertEqual(fa.hash, fb.hash)            # value is stable
        self.assertNotEqual(fa.date, fb.date)         # envelope differs
        self.assertNotEqual(fa.signature, fb.signature)
        self.assertNotEqual(a.as_base64(), b.as_base64())

    def test_construction_does_not_verify(self):
        # An OWID with a present but tampered (invalid) signature still
        # constructs and exposes all three fields - construction must not
        # verify.
        raw = bytearray(base64.b64decode(
            self.factory.signed_owid_base64(canonical_payload())))
        raw[-1] ^= 0xFF  # corrupt the signature
        tampered = Owid.from_byte_array(bytes(raw))
        fod = FodId.from_owid(tampered)
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)

    def test_from_owid_is_decoupled_from_source_owid(self):
        # Mutating the source OWID after construction must not affect the
        # FodId (it holds an independent copy).
        owid = self.factory.signed_owid(canonical_payload())
        fod = FodId.from_owid(owid)
        owid.payload = bytes(FodId.PAYLOAD_LENGTH)  # mutate the source
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(0x20, fod.payload[FodId.HASH_OFFSET])

    def test_constructor_is_decoupled_from_source_owid(self):
        # The constructor must copy the OWID too, not just from_owid -
        # mutating the source afterwards must not affect the FodId.
        owid = self.factory.signed_owid(canonical_payload())
        fod = FodId(owid)
        owid.payload = bytes(FodId.PAYLOAD_LENGTH)  # mutate the source
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(0x20, fod.payload[FodId.HASH_OFFSET])

    def test_verify_with_wrong_key_returns_false(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        other_public_pem = Crypto.new().public_key_pem()
        self.assertFalse(fod.verify(other_public_pem))

    def test_roundtrip_through_bytes_constructor_preserves_all_fields(self):
        fod1 = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        fod2 = FodId.from_byte_array(fod1.as_byte_array())
        self.assertEqual(fod1.flags, fod2.flags)
        self.assertEqual(fod1.license_id, fod2.license_id)
        self.assertEqual(fod1.hash, fod2.hash)
        self.assertEqual(fod1.domain, fod2.domain)


if __name__ == "__main__":
    unittest.main()
