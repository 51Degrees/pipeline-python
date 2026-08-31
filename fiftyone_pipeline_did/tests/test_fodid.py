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
import struct
import unittest
from datetime import datetime, timezone

from owid import Crypto, Creator, Owid, ParseStatus

from fiftyone_pipeline_did import (
    FodId,
    FodIdParseResult,
    FodIdParseStatus,
    IdType,
    OwidError,
    SignatureStatus,
)

from .envelope import envelope_bytes, signed_envelope

TEST_DOMAIN = "51degrees.com"
# 0xA5: usage bits plus the HashedEmail type tag in bits 6-7.
CANONICAL_FLAGS = 0xA5
CANONICAL_LICENSE_ID = 0x12345678
CANONICAL_HASH = bytes((0x20 + i) for i in range(FodId.HASH_LENGTH))

#: A creator domain longer than the one the cloud signs with, as a
#: self-hosted container may be configured to use.
LONG_DOMAIN = "identifiers." + ("a" * 120) + ".example"


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
    """Generates a fresh ECDSA P-256 key pair and signs real OWID
    envelopes. A Creator is the only way the OWID library brings a new
    envelope into being, so the payload goes in and a signed envelope comes
    out with no unsigned step in between."""

    def __init__(self):
        self.crypto = Crypto.new()
        self.public_pem = self.crypto.public_key_pem()
        self._creator = Creator(TEST_DOMAIN, self.crypto)

    def signed_owid(self, payload):
        return self._creator.create(bytes(payload))

    def signed_owid_base64(self, payload):
        return self.signed_owid(payload).as_base64()

    def signed_bytes(self, payload):
        return self.signed_owid(payload).as_byte_array()


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
        buffer = self.factory.signed_bytes(canonical_payload())
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

    def test_payload_larger_than_spec_uses_first_37_bytes(self):
        payload = bytearray(64)
        payload[0:FodId.PAYLOAD_LENGTH] = canonical_payload()
        for i in range(FodId.PAYLOAD_LENGTH, len(payload)):
            payload[i] = 0xCC
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(FodId.HASH_LENGTH, len(fod.hash))

    def test_long_envelope_parses_and_keeps_the_header_fields(self):
        # No upper bound belongs in the reader: a creator domain is a
        # deployment parameter and a context section of a version this
        # package does not know about may be any length. The signature is
        # all zeros, which parses because parsing never verifies.
        payload = bytearray(canonical_payload()) + bytearray(200)
        raw = envelope_bytes(self.factory.crypto, payload,
                             domain=LONG_DOMAIN, signature=bytes(64))
        fod = FodId.from_byte_array(raw)
        self.assertEqual(LONG_DOMAIN, fod.domain)
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(FodId.HASH_LENGTH, len(fod.hash))

    def test_is_cryptographically_verifiable(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        self.assertTrue(fod.verify(self.factory.public_pem))
        self.assertIs(SignatureStatus.SIGNATURE_VALID,
                      fod.signature_status(self.factory.public_pem))

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
        # Two reissues of the same value at different times: the envelope
        # differs and the value inside is the same.
        payload = canonical_payload()
        a = signed_envelope(
            self.factory.crypto, payload,
            date=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))
        b = signed_envelope(
            self.factory.crypto, payload,
            date=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))

        fa = FodId.from_base64(a.as_base64())
        fb = FodId.from_base64(b.as_base64())

        self.assertEqual(fa.hash, fb.hash)            # value is stable
        self.assertNotEqual(fa.date, fb.date)         # envelope differs
        self.assertNotEqual(fa.signature, fb.signature)
        self.assertNotEqual(a.as_base64(), b.as_base64())

    def test_construction_does_not_verify(self):
        # An OWID with a present but tampered (invalid) signature still
        # constructs and exposes all three fields, because construction
        # never verifies.
        raw = bytearray(self.factory.signed_bytes(canonical_payload()))
        raw[-1] ^= 0xFF  # corrupt the signature
        fod = FodId.from_byte_array(bytes(raw))
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertFalse(fod.verify(self.factory.public_pem))

    def test_source_envelope_cannot_be_changed_after_construction(self):
        # The FodId used to copy the OWID it was given so a later change to
        # the source could not reach it. The OWID library now hands out an
        # envelope that cannot be changed at all, which is what makes the
        # copy unnecessary, so that is the fact this test pins.
        owid = self.factory.signed_owid(canonical_payload())
        fod = FodId.from_owid(owid)
        with self.assertRaises(AttributeError):
            owid.payload = bytes(FodId.PAYLOAD_LENGTH)
        with self.assertRaises(AttributeError):
            owid.signature = bytes(64)
        self.assertEqual(CANONICAL_HASH, fod.hash)
        self.assertEqual(0x20, fod.payload[FodId.HASH_OFFSET])

    def test_constructor_reads_the_envelope_back_through_the_parser(self):
        # The envelope handed in is written out and read back, so the FodId
        # holds the same bytes whatever object the caller passed.
        owid = self.factory.signed_owid(canonical_payload())
        fod = FodId(owid)
        self.assertEqual(owid.as_byte_array(), fod.as_byte_array())
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_HASH, fod.hash)

    def test_verify_with_wrong_key_returns_false(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        other_public_pem = Crypto.new().public_key_pem()
        self.assertFalse(fod.verify(other_public_pem))
        self.assertIs(SignatureStatus.SIGNATURE_INVALID,
                      fod.signature_status(other_public_pem))

    def test_roundtrip_through_bytes_constructor_preserves_all_fields(self):
        fod1 = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        fod2 = FodId.from_byte_array(fod1.as_byte_array())
        self.assertEqual(fod1.flags, fod2.flags)
        self.assertEqual(fod1.license_id, fod2.license_id)
        self.assertEqual(fod1.hash, fod2.hash)
        self.assertEqual(fod1.domain, fod2.domain)


def _declared_length_offset(raw):
    """The offset of the four byte payload length declaration in a version
    3 envelope: the version byte, the domain and its terminator, then the
    four date bytes."""
    return 1 + raw.index(0, 1) + 1 + 4


class FodIdTryParseTests(unittest.TestCase):
    """The non-raising readers. Every case asserts the three facts a result
    carries, being whether the parse succeeded, the value, and the status,
    and the raising readers are checked against the same inputs."""

    def setUp(self):
        self.factory = FodIdTestFactory()

    def assert_parsed(self, result):
        self.assertIsInstance(result, FodIdParseResult)
        self.assertTrue(result.ok)
        self.assertTrue(bool(result))
        self.assertIsInstance(result.value, FodId)
        self.assertIs(FodIdParseStatus.PARSED, result.status)
        return result.value

    def assert_failed(self, result, status):
        self.assertIsInstance(result, FodIdParseResult)
        self.assertFalse(result.ok)
        self.assertFalse(bool(result))
        self.assertIsNone(result.value)
        self.assertIs(status, result.status)

    def assert_canonical(self, fod):
        self.assertEqual(CANONICAL_FLAGS, fod.flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_HASH, fod.hash)

    # ----- Vocabulary -----

    def test_status_vocabulary_is_the_owid_one_plus_two(self):
        # Every OWID status has a member of the same name and value, so an
        # OWID failure is carried through unchanged, and the two 51Did
        # payload statuses are the only additions.
        for status in ParseStatus:
            member = FodIdParseStatus.of(status)
            self.assertEqual(status.name, member.name)
            self.assertEqual(status.value, member.value)
        owid_names = {status.name for status in ParseStatus}
        extra = {member.name for member in FodIdParseStatus} - owid_names
        self.assertEqual(
            {"PAYLOAD_TOO_SHORT", "INVALID_TYPE_PAYLOAD_LENGTH"}, extra)

    def test_result_is_immutable_and_carries_exactly_three_facts(self):
        result = FodId.try_from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        self.assertEqual(3, len(result))
        self.assertEqual(("ok", "value", "status"), result._fields)
        with self.assertRaises(AttributeError):
            result.ok = False

    # ----- Success -----

    def test_valid_identifier_parses_in_both_alphabets(self):
        standard = self.factory.signed_owid_base64(canonical_payload())
        url_safe = FodId.to_base64_url(standard)
        for form in (standard, url_safe, standard.rstrip("="),
                     " " + url_safe + "\n"):
            fod = self.assert_parsed(FodId.try_from_base64(form))
            self.assert_canonical(fod)
            self.assertEqual(standard, fod.as_base64())

    def test_valid_identifier_parses_from_bytes(self):
        raw = self.factory.signed_bytes(canonical_payload())
        for form in (raw, bytearray(raw), memoryview(raw)):
            fod = self.assert_parsed(FodId.try_from_byte_array(form))
            self.assert_canonical(fod)
            self.assertEqual(raw, fod.as_byte_array())

    def test_longer_self_hosted_creator_domain_is_accepted(self):
        raw = envelope_bytes(self.factory.crypto, canonical_payload(),
                             domain=LONG_DOMAIN)
        fod = self.assert_parsed(FodId.try_from_byte_array(raw))
        self.assertEqual(LONG_DOMAIN, fod.domain)
        self.assert_canonical(fod)
        self.assertTrue(fod.verify(self.factory.public_pem))

    def test_longer_creator_context_section_is_accepted(self):
        # An older reader meets a context section of a version it does not
        # know. The header and value are read and the rest is kept.
        payload = bytes(canonical_payload()) + bytes(range(64))
        fod = self.assert_parsed(FodId.try_from_base64(
            self.factory.signed_owid_base64(payload)))
        self.assert_canonical(fod)
        self.assertEqual(FodId.HASH_LENGTH, len(fod.hash))
        self.assertEqual(payload, fod.payload)

    def test_far_longer_payload_is_not_rejected_for_its_length(self):
        payload = bytes(canonical_payload()) + bytes(3000)
        fod = self.assert_parsed(FodId.try_from_byte_array(
            self.factory.signed_bytes(payload)))
        self.assert_canonical(fod)
        self.assertEqual(len(payload), len(fod.payload))

    def test_random_identifier_parses_with_a_sixteen_byte_value(self):
        fod = self.assert_parsed(FodId.try_from_base64(
            self.factory.signed_owid_base64(canonical_random_payload())))
        self.assertEqual(IdType.RANDOM, fod.type)
        self.assertEqual(FodId.GUID_LENGTH, len(fod.hash))

    def test_reserved_header_only_parses_best_effort(self):
        payload = bytearray(FodId.HEADER_LENGTH)
        payload[FodId.FLAGS_OFFSET] = 0b1100_0000
        fod = self.assert_parsed(FodId.try_from_base64(
            self.factory.signed_owid_base64(payload)))
        self.assertEqual(IdType.RESERVED, fod.type)
        self.assertEqual(b"", fod.hash)

    def test_success_does_not_verify_the_signature(self):
        # All zero signature: the shape is right, the signature is not.
        raw = envelope_bytes(self.factory.crypto, canonical_payload(),
                             signature=bytes(64))
        fod = self.assert_parsed(FodId.try_from_byte_array(raw))
        self.assertFalse(fod.verify(self.factory.public_pem))

    # ----- The two 51Did payload rules -----

    def test_short_random_payload_reports_invalid_type_payload_length(self):
        payload = canonical_random_payload()[:FodId.RANDOM_PAYLOAD_LENGTH - 1]
        self.assert_failed(
            FodId.try_from_base64(self.factory.signed_owid_base64(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)
        self.assert_failed(
            FodId.try_from_byte_array(self.factory.signed_bytes(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)

    def test_short_probabilistic_payload_reports_invalid_type_length(self):
        payload = canonical_payload()[:FodId.PAYLOAD_LENGTH - 1]
        payload[FodId.FLAGS_OFFSET] = 0b0000_0101
        self.assert_failed(
            FodId.try_from_base64(self.factory.signed_owid_base64(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)

    def test_short_hashed_email_payload_reports_invalid_type_length(self):
        payload = canonical_payload()[:FodId.PAYLOAD_LENGTH - 1]
        self.assertEqual(IdType.HASHED_EMAIL,
                         IdType.from_flags(payload[FodId.FLAGS_OFFSET]))
        self.assert_failed(
            FodId.try_from_base64(self.factory.signed_owid_base64(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)

    def test_header_only_random_payload_reports_invalid_type_length(self):
        payload = canonical_random_payload()[:FodId.HEADER_LENGTH]
        self.assert_failed(
            FodId.try_from_base64(self.factory.signed_owid_base64(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)

    def test_payload_shorter_than_the_header_reports_payload_too_short(self):
        for length in range(FodId.HEADER_LENGTH):
            payload = bytes([CANONICAL_FLAGS] * length)
            self.assert_failed(
                FodId.try_from_base64(
                    self.factory.signed_owid_base64(payload)),
                FodIdParseStatus.PAYLOAD_TOO_SHORT)
            self.assert_failed(
                FodId.try_from_byte_array(self.factory.signed_bytes(payload)),
                FodIdParseStatus.PAYLOAD_TOO_SHORT)

    # ----- OWID failures carried through unchanged -----

    def test_invalid_base64_reports_the_owid_invalid_base64_status(self):
        for text in ("This is not valid Base64!@#$", "A", "===="):
            self.assert_failed(FodId.try_from_base64(text),
                               FodIdParseStatus.INVALID_BASE64)

    def test_declaration_mismatch_is_propagated_unchanged(self):
        # The declared payload length is raised by one, so the declaration
        # disagrees with the bytes present. The status is the OWID one,
        # and nothing cryptographic is involved because parsing takes no
        # key and checks no signature.
        raw = bytearray(self.factory.signed_bytes(canonical_payload()))
        at = _declared_length_offset(raw)
        declared = struct.unpack("<I", raw[at:at + 4])[0]
        raw[at:at + 4] = struct.pack("<I", declared + 1)
        owid_status = Owid.parse_bytes(bytes(raw)).status
        self.assertIs(ParseStatus.BYTE_COUNT_MISMATCH, owid_status)
        self.assert_failed(FodId.try_from_byte_array(bytes(raw)),
                           FodIdParseStatus.BYTE_COUNT_MISMATCH)
        self.assert_failed(
            FodId.try_from_base64(base64.b64encode(bytes(raw)).decode()),
            FodIdParseStatus.BYTE_COUNT_MISMATCH)

    def test_other_owid_failures_are_propagated_unchanged(self):
        raw = self.factory.signed_bytes(canonical_payload())
        cases = (
            (bytes([0x09]) + raw[1:], FodIdParseStatus.UNSUPPORTED_VERSION),
            (raw[:3], FodIdParseStatus.UNEXPECTED_END),
            (bytes([0x00]), FodIdParseStatus.ABSENT_NODE),
        )
        for buffer, expected in cases:
            self.assertIs(ParseStatus[expected.name],
                          Owid.parse_bytes(buffer).status)
            self.assert_failed(FodId.try_from_byte_array(buffer), expected)
            self.assert_failed(
                FodId.try_from_base64(base64.b64encode(buffer).decode()),
                expected)

    def test_absent_input_reports_missing_input(self):
        for value in (None, ""):
            self.assert_failed(FodId.try_from_base64(value),
                               FodIdParseStatus.MISSING_INPUT)
        for buffer in (None, b"", bytearray()):
            self.assert_failed(FodId.try_from_byte_array(buffer),
                               FodIdParseStatus.MISSING_INPUT)

    def test_wrong_input_type_reports_invalid_input_type(self):
        self.assert_failed(FodId.try_from_base64(1234),
                           FodIdParseStatus.INVALID_INPUT_TYPE)
        self.assert_failed(FodId.try_from_base64(b"AwB="),
                           FodIdParseStatus.INVALID_INPUT_TYPE)
        self.assert_failed(FodId.try_from_byte_array("AwB="),
                           FodIdParseStatus.INVALID_INPUT_TYPE)

    # ----- A date the runtime cannot hold -----

    def _dated_past_the_year_9999(self):
        """A signed envelope whose four byte minute count is 0xFFFFFFFF,
        which the wire format allows and which lands on 15 February 10186,
        past the end of the year 9999 where ``datetime`` stops. The bytes
        are changed after signing, which is fine because the read refuses
        the date before any signature is looked at."""
        raw = bytearray(self.factory.signed_bytes(canonical_payload()))
        # The four little endian date bytes sit after the version byte, the
        # domain and its terminator.
        at = 1 + raw.index(0, 1) + 1
        raw[at:at + 4] = bytes([0xFF] * 4)
        return bytes(raw)

    def test_date_past_the_year_9999_is_implementation_capacity_exceeded(
            self):
        # The OWID reader judges the count before the arithmetic, so the
        # read answers with a status instead of raising OverflowError, and
        # the 51Did surface carries that status through unchanged on both
        # the byte and the base64 surface. The same bytes read fine where
        # the date type is wider, so the status is the runtime's limit and
        # not a fault in the data.
        raw = self._dated_past_the_year_9999()
        self.assertIs(ParseStatus.IMPLEMENTATION_CAPACITY_EXCEEDED,
                      Owid.parse_bytes(raw).status)
        self.assert_failed(
            FodId.try_from_byte_array(raw),
            FodIdParseStatus.IMPLEMENTATION_CAPACITY_EXCEEDED)
        self.assert_failed(
            FodId.try_from_base64(base64.b64encode(raw).decode()),
            FodIdParseStatus.IMPLEMENTATION_CAPACITY_EXCEEDED)

    def test_raising_readers_name_the_date_the_runtime_cannot_hold(self):
        # The raising readers run the same walk, so the date is the
        # documented OwidError with the status in the message, never the
        # OverflowError the arithmetic would have raised.
        raw = self._dated_past_the_year_9999()
        with self.assertRaises(OwidError) as raised:
            FodId.from_base64(base64.b64encode(raw).decode())
        self.assertIn("ImplementationCapacityExceeded", str(raised.exception))
        with self.assertRaises(OwidError) as raised:
            FodId.from_byte_array(raw)
        self.assertIn("ImplementationCapacityExceeded", str(raised.exception))

    # ----- Parsing and verifying are separate -----

    def test_tampered_signature_parses_then_verifies_as_invalid(self):
        raw = bytearray(self.factory.signed_bytes(canonical_payload()))
        raw[-1] ^= 0xFF
        fod = self.assert_parsed(FodId.try_from_byte_array(bytes(raw)))
        self.assert_canonical(fod)
        self.assertFalse(fod.verify(self.factory.public_pem))
        self.assertIs(SignatureStatus.SIGNATURE_INVALID,
                      fod.signature_status(self.factory.public_pem))

    def test_missing_or_unusable_key_is_not_reported_as_a_forgery(self):
        fod = self.assert_parsed(FodId.try_from_base64(
            self.factory.signed_owid_base64(canonical_payload())))
        self.assertIs(SignatureStatus.KEY_UNAVAILABLE,
                      fod.signature_status(""))
        self.assertIs(SignatureStatus.INVALID_KEY,
                      fod.signature_status("not a pem"))
        # The boolean form raises for a key it cannot use rather than
        # answering False, so an outage never reads as a forgery.
        with self.assertRaises(Exception):
            fod.verify("not a pem")

    # ----- The raising readers over the same inputs -----

    def test_raising_readers_keep_their_documented_exception_types(self):
        with self.assertRaises(OwidError) as raised:
            FodId.from_base64("This is not valid Base64!@#$")
        self.assertIn("InvalidBase64", str(raised.exception))
        with self.assertRaises(OwidError):
            FodId.from_byte_array(b"")
        with self.assertRaises(TypeError):
            FodId.from_base64(1234)
        with self.assertRaises(TypeError):
            FodId.from_byte_array("AwB=")
        short = self.factory.signed_owid_base64(
            canonical_random_payload()[:FodId.RANDOM_PAYLOAD_LENGTH - 1])
        with self.assertRaises(ValueError) as raised:
            FodId.from_base64(short)
        self.assertIn("RANDOM", str(raised.exception))
        header_only = self.factory.signed_bytes(b"\x00\x00")
        with self.assertRaises(ValueError) as raised:
            FodId.from_byte_array(header_only)
        self.assertIn("at least", str(raised.exception))
        raw = bytearray(self.factory.signed_bytes(canonical_payload()))
        at = _declared_length_offset(raw)
        raw[at:at + 4] = struct.pack("<I", 1)
        with self.assertRaises(OwidError) as raised:
            FodId.from_byte_array(bytes(raw))
        self.assertIn("ByteCountMismatch", str(raised.exception))

    def test_raising_and_non_raising_readers_agree_on_success(self):
        standard = self.factory.signed_owid_base64(canonical_payload())
        raising = FodId.from_base64(standard)
        result = FodId.try_from_base64(standard)
        self.assertEqual(raising.as_byte_array(),
                         result.value.as_byte_array())
        self.assertEqual(raising.hash, result.value.hash)


if __name__ == "__main__":
    unittest.main()
