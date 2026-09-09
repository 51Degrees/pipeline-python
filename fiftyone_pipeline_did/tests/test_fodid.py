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
    Usage,
    SignatureStatus,
)

# The named terms value is private to the package and is not exported, so
# the vocabulary tests below reach the private module directly, as the
# package surface page says the package's own tests may.
from fiftyone_pipeline_did._terms import Terms

# The byte layout is not part of the package's public surface. These tests
# build payloads byte by byte, so they read it from the private module, as
# https://github.com/51Degrees/specifications/blob/main/did-specification/package-surface.md
# says the package's own tests may.
from fiftyone_pipeline_did._layout import (
    ABSENT_TERMS_INDEX,
    FLAGS_OFFSET,
    GUID_LENGTH,
    HEADER_LENGTH,
    LICENSE_ID_LENGTH,
    LICENSE_ID_OFFSET,
    MATCH_KEY_LENGTH,
    MATCH_KEY_OFFSET,
    PAYLOAD_LENGTH,
    RANDOM_PAYLOAD_LENGTH,
    SUPPORTED_PAYLOAD_VERSION,
    TERMS_LENGTH,
)
from .envelope import envelope_bytes, signed_envelope

TEST_DOMAIN = "51degrees.com"
# 0x85: the personalized marketing usage in bits 0-2, the payload version 0
# in bits 4-5 and the HashedEmail type tag in bits 6-7.
CANONICAL_FLAGS = 0x85
CANONICAL_LICENSE_ID = 0x12345678
CANONICAL_MATCH_KEY = bytes((0x20 + i) for i in range(MATCH_KEY_LENGTH))

#: A creator domain longer than the one the cloud signs with, as a
#: self-hosted container may be configured to use.
LONG_DOMAIN = "identifiers." + ("a" * 120) + ".example"


def _write_license_id(payload):
    # Little-endian: low byte first (0x12345678 -> 78 56 34 12).
    payload[LICENSE_ID_OFFSET] = 0x78
    payload[LICENSE_ID_OFFSET + 1] = 0x56
    payload[LICENSE_ID_OFFSET + 2] = 0x34
    payload[LICENSE_ID_OFFSET + 3] = 0x12


def payload_ending_at_match_key():
    """The canonical payload cut off at the end of the match key, so it
    carries no Terms byte. A reader takes that as a Terms of zero, and
    this is the fixture for that rule rather than anything an issuer
    would write."""
    payload = bytearray(PAYLOAD_LENGTH)
    payload[FLAGS_OFFSET] = CANONICAL_FLAGS
    _write_license_id(payload)
    payload[MATCH_KEY_OFFSET:
            MATCH_KEY_OFFSET + MATCH_KEY_LENGTH] = \
        CANONICAL_MATCH_KEY
    return bytearray(payload)


def canonical_payload():
    """The canonical payload as an issuer writes one, carrying the
    payload version 0 in its flags byte and the Terms byte of the
    document a personalized marketing identifier is created under. This
    is the creating side, so it writes every field an issuer writes."""
    return with_terms(payload_ending_at_match_key(), MODEL_TERMS_INDEX)


#: The address the specification gives for Terms index 1, the Model Terms
#: for Marketing version 2.
MODEL_TERMS_URL = "https://m4ow.uk/mtm/2.txt"
#: The Terms index of the Model Terms for Marketing version 2.
MODEL_TERMS_INDEX = 1
#: An index the specification has not assigned, standing for one added
#: after this package was released.
UNKNOWN_TERMS_INDEX = 200
#: A creator context section. How long a section is belongs to the cloud
#: and changes with the section version, so an arbitrary length is used.
CONTEXT_SECTION = bytes(range(1, 24))


def with_terms(payload, index):
    """The payload with a Terms byte after the match key, which is where
    the specification puts it."""
    return bytearray(bytes(payload) + bytes([index]))


def random_payload_ending_at_match_key():
    """The canonical Random payload cut off at the end of its GUID."""
    payload = bytearray(RANDOM_PAYLOAD_LENGTH)
    payload[FLAGS_OFFSET] = (1 << 6) | 0b001  # Random tag + usage bits
    _write_license_id(payload)
    for i in range(GUID_LENGTH):
        payload[MATCH_KEY_OFFSET + i] = 0x40 + i
    return bytearray(payload)


def canonical_random_payload():
    """The canonical Random payload as an issuer writes one, carrying the
    zero Terms byte a non-marketing identifier carries."""
    return with_terms(
        random_payload_ending_at_match_key(), ABSENT_TERMS_INDEX)


def with_payload_version(payload, version):
    """The payload with its version bits set to the given version, leaving
    every other bit of the flags byte alone."""
    changed = bytearray(payload)
    changed[FLAGS_OFFSET] = (
        (payload[FLAGS_OFFSET] & 0b1100_1111) | (version << 4))
    return changed


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
        self.assertEqual(MATCH_KEY_OFFSET + MATCH_KEY_LENGTH,
                         PAYLOAD_LENGTH)
        self.assertEqual(LICENSE_ID_OFFSET + LICENSE_ID_LENGTH,
                         MATCH_KEY_OFFSET)
        self.assertEqual(MATCH_KEY_OFFSET + GUID_LENGTH,
                         RANDOM_PAYLOAD_LENGTH)

    def test_raw_surface_is_not_public(self):
        # The raw byte, the layout constants and the old Hash names are
        # gone. Every field has a typed accessor, and an offset is only
        # ever wanted in order to read a field by hand, which is the way
        # that gets the cumulative usage bits wrong. The layout stays
        # available to this package through the private _layout module.
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        for name in ("flags", "hash", "date_minutes", "FLAGS_OFFSET",
                     "LICENSE_ID_OFFSET", "LICENSE_ID_LENGTH",
                     "MATCH_KEY_OFFSET", "MATCH_KEY_LENGTH",
                     "HEADER_LENGTH", "GUID_LENGTH",
                     "RANDOM_PAYLOAD_LENGTH", "PAYLOAD_LENGTH",
                     "HASH_OFFSET", "HASH_LENGTH"):
            self.assertFalse(hasattr(FodId, name), name)
            self.assertFalse(hasattr(fod, name), name)

    def test_exposes_owid_level_fields(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        # OWID-level concerns are delegated to the wrapped envelope.
        self.assertEqual(TEST_DOMAIN, fod.domain)
        self.assertIsNotNone(fod.version)

    def test_from_base64_unpacks_all_three_fields(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        self.assertEqual(CANONICAL_FLAGS, fod._flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
        self.assertEqual(TEST_DOMAIN, fod.domain)

    def test_from_byte_array_unpacks_all_three_fields(self):
        buffer = self.factory.signed_bytes(canonical_payload())
        fod = FodId.from_byte_array(buffer)
        self.assertEqual(CANONICAL_FLAGS, fod._flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
        self.assertEqual(TEST_DOMAIN, fod.domain)

    def test_from_owid_unpacks_all_three_fields(self):
        owid = self.factory.signed_owid(canonical_payload())
        fod = FodId.from_owid(owid)
        self.assertEqual(CANONICAL_FLAGS, fod._flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
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
        payload[LICENSE_ID_OFFSET:LICENSE_ID_OFFSET + 4] = \
            bytes([0x01, 0x00, 0x00, 0x00])
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(1, fod.license_id)

    def test_license_id_max_value(self):
        payload = canonical_payload()
        payload[LICENSE_ID_OFFSET:LICENSE_ID_OFFSET + 4] = \
            bytes([0xFF, 0xFF, 0xFF, 0xFF])
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(4294967295, fod.license_id)

    def test_license_id_high_bit_stays_unsigned(self):
        payload = canonical_payload()
        payload[LICENSE_ID_OFFSET:LICENSE_ID_OFFSET + 4] = \
            bytes([0x00, 0x00, 0x00, 0x80])
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(0x80000000, fod.license_id)

    def test_flags_byte_of_zero_is_read(self):
        # The byte itself is private now, so these two read it where it is
        # kept and pin that every bit of it survives the parse for the
        # typed accessors to read.
        payload = canonical_payload()
        payload[FLAGS_OFFSET] = 0x00
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(0, fod._flags)

    def test_every_flags_bit_outside_the_version_is_read(self):
        # Bits 4 and 5 are the payload version and only version 0 is read,
        # so every other bit is set and those two are left clear. A payload
        # with them set is refused rather than read, which
        # FodIdVersionTests covers.
        payload = canonical_payload()
        payload[FLAGS_OFFSET] = 0xCF
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(0xCF, fod._flags)

    def test_match_key_is_immutable(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_payload()))
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
        self.assertIsInstance(fod.match_key, bytes)
        # bytes is immutable, so the match key cannot be used to mutate the
        # OWID.
        with self.assertRaises(TypeError):
            fod.match_key[0] = 0x00

    def test_payload_one_byte_short_raises(self):
        base64 = self.factory.signed_owid_base64(
            bytearray(PAYLOAD_LENGTH - 1))
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
        payload[0:PAYLOAD_LENGTH] = canonical_payload()
        for i in range(PAYLOAD_LENGTH, len(payload)):
            payload[i] = 0xCC
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(CANONICAL_FLAGS, fod._flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
        self.assertEqual(MATCH_KEY_LENGTH, len(fod.match_key))

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
        self.assertEqual(CANONICAL_FLAGS, fod._flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
        self.assertEqual(MATCH_KEY_LENGTH, len(fod.match_key))

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
        self.assertEqual(fod1._flags, fod2._flags)
        self.assertEqual(fod1.license_id, fod2.license_id)
        self.assertEqual(fod1.match_key, fod2.match_key)
        self.assertEqual(fod1.domain, fod2.domain)

    # ----- Type model -----

    def test_type_decoded_from_top_two_flag_bits(self):
        self.assertEqual(IdType.PROBABILISTIC, self._type_for(0b0000_0101))
        self.assertEqual(IdType.HASHED_EMAIL, self._type_for(0b1000_0101))
        self.assertEqual(IdType.RESERVED, self._type_for(0b1100_0101))

    def _type_for(self, flags):
        payload = canonical_payload()
        payload[FLAGS_OFFSET] = flags
        return FodId.from_base64(
            self.factory.signed_owid_base64(payload)).type

    def test_usage_is_the_highest_granted(self):
        """The usage is the highest granted, because the bits are
        cumulative. A mask for the non-marketing bit alone would say yes
        for every marketing identifier, which is the wrong answer for a
        data protection decision."""
        cases = [
            (0b000, Usage.NONE, None),
            (0b001, Usage.NON_MARKETING, "non-marketing"),
            (0b011, Usage.STANDARD, "standard"),
            (0b111, Usage.PERSONALIZED, "personalized"),
        ]
        for bits, expected, id_usage in cases:
            payload = canonical_random_payload()
            payload[FLAGS_OFFSET] = (1 << 6) | bits
            fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
            self.assertEqual(expected, fod.usage, "usage bits %s" % bin(bits))
            self.assertEqual(id_usage, fod.usage.id_usage)
            self.assertEqual(IdType.RANDOM, fod.type)
            self.assertFalse(fod.usage_from_consent)

    def test_usage_from_consent_is_bit_three(self):
        payload = canonical_random_payload()
        payload[FLAGS_OFFSET] = (1 << 6) | 0b1011
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertTrue(fod.usage_from_consent)
        self.assertEqual(Usage.STANDARD, fod.usage)

    def test_type_random_when_bits_01(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_random_payload()))
        self.assertEqual(IdType.RANDOM, fod.type)

    def test_random_payload_21_bytes_parses(self):
        fod = FodId.from_base64(
            self.factory.signed_owid_base64(canonical_random_payload()))
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(GUID_LENGTH, len(fod.match_key))
        self.assertEqual(bytes((0x40 + i) for i in range(GUID_LENGTH)),
                         fod.match_key)

    def test_random_payload_one_byte_short_raises(self):
        payload = canonical_random_payload()[:RANDOM_PAYLOAD_LENGTH - 1]
        base64 = self.factory.signed_owid_base64(payload)
        with self.assertRaises(ValueError):
            FodId.from_base64(base64)

    def test_random_payload_larger_than_spec_uses_first_16_value_bytes(self):
        payload = bytearray(PAYLOAD_LENGTH)
        payload[0:RANDOM_PAYLOAD_LENGTH] = canonical_random_payload()
        for i in range(RANDOM_PAYLOAD_LENGTH, len(payload)):
            payload[i] = 0xCC
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(IdType.RANDOM, fod.type)
        self.assertEqual(GUID_LENGTH, len(fod.match_key))

    def test_hashed_email_payload_one_byte_short_raises(self):
        payload = canonical_payload()[:PAYLOAD_LENGTH - 1]
        base64 = self.factory.signed_owid_base64(payload)
        with self.assertRaises(ValueError):
            FodId.from_base64(base64)

    def test_reserved_header_only_parses(self):
        payload = bytearray(MATCH_KEY_OFFSET)
        payload[FLAGS_OFFSET] = 0b1100_0000
        fod = FodId.from_base64(self.factory.signed_owid_base64(payload))
        self.assertEqual(IdType.RESERVED, fod.type)
        self.assertEqual(0, len(fod.match_key))

    # ----- Gap tests (runbook section 6b) -----

    def test_compare_two_51dids_same_payload(self):
        # Two reissues of the same payload at different times. The envelope
        # differs and the match key inside is the same.
        payload = canonical_payload()
        a = signed_envelope(
            self.factory.crypto, payload,
            date=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))
        b = signed_envelope(
            self.factory.crypto, payload,
            date=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))

        fa = FodId.from_base64(a.as_base64())
        fb = FodId.from_base64(b.as_base64())

        self.assertEqual(fa.match_key, fb.match_key)  # match key is stable
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
        self.assertEqual(CANONICAL_FLAGS, fod._flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
        self.assertFalse(fod.verify(self.factory.public_pem))

    def test_source_envelope_cannot_be_changed_after_construction(self):
        # The FodId used to copy the OWID it was given so a later change to
        # the source could not reach it. The OWID library now hands out an
        # envelope that cannot be changed at all, which is what makes the
        # copy unnecessary, so that is the fact this test pins.
        owid = self.factory.signed_owid(canonical_payload())
        fod = FodId.from_owid(owid)
        with self.assertRaises(AttributeError):
            owid.payload = bytes(PAYLOAD_LENGTH)
        with self.assertRaises(AttributeError):
            owid.signature = bytes(64)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
        self.assertEqual(0x20, fod.payload[MATCH_KEY_OFFSET])

    def test_constructor_reads_the_envelope_back_through_the_parser(self):
        # The envelope handed in is written out and read back, so the FodId
        # holds the same bytes whatever object the caller passed.
        owid = self.factory.signed_owid(canonical_payload())
        fod = FodId(owid)
        self.assertEqual(owid.as_byte_array(), fod.as_byte_array())
        self.assertEqual(CANONICAL_FLAGS, fod._flags)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)

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
        self.assertEqual(fod1._flags, fod2._flags)
        self.assertEqual(fod1.license_id, fod2.license_id)
        self.assertEqual(fod1.match_key, fod2.match_key)
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
        self.assertEqual(CANONICAL_FLAGS, fod._flags)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)

    # ----- Vocabulary -----

    def test_status_vocabulary_is_the_owid_one_plus_three(self):
        # Every OWID status has a member of the same name and value, so an
        # OWID failure is carried through unchanged, and the three 51Did
        # payload statuses are the only additions.
        for status in ParseStatus:
            member = FodIdParseStatus.of(status)
            self.assertEqual(status.name, member.name)
            self.assertEqual(status.value, member.value)
        owid_names = {status.name for status in ParseStatus}
        extra = {member.name for member in FodIdParseStatus} - owid_names
        self.assertEqual(
            {
                "PAYLOAD_TOO_SHORT",
                "INVALID_TYPE_PAYLOAD_LENGTH",
                "UNSUPPORTED_PAYLOAD_VERSION",
            },
            extra)

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
        # know. The header and match key are read and the rest is kept.
        payload = bytes(canonical_payload()) + bytes(range(64))
        fod = self.assert_parsed(FodId.try_from_base64(
            self.factory.signed_owid_base64(payload)))
        self.assert_canonical(fod)
        self.assertEqual(MATCH_KEY_LENGTH, len(fod.match_key))
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
        self.assertEqual(GUID_LENGTH, len(fod.match_key))

    def test_reserved_header_only_parses_best_effort(self):
        payload = bytearray(HEADER_LENGTH)
        payload[FLAGS_OFFSET] = 0b1100_0000
        fod = self.assert_parsed(FodId.try_from_base64(
            self.factory.signed_owid_base64(payload)))
        self.assertEqual(IdType.RESERVED, fod.type)
        self.assertEqual(b"", fod.match_key)

    def test_success_does_not_verify_the_signature(self):
        # All zero signature: the shape is right, the signature is not.
        raw = envelope_bytes(self.factory.crypto, canonical_payload(),
                             signature=bytes(64))
        fod = self.assert_parsed(FodId.try_from_byte_array(raw))
        self.assertFalse(fod.verify(self.factory.public_pem))

    # ----- The two 51Did payload rules -----

    def test_short_random_payload_reports_invalid_type_payload_length(self):
        payload = canonical_random_payload()[:RANDOM_PAYLOAD_LENGTH - 1]
        self.assert_failed(
            FodId.try_from_base64(self.factory.signed_owid_base64(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)
        self.assert_failed(
            FodId.try_from_byte_array(self.factory.signed_bytes(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)

    def test_short_probabilistic_payload_reports_invalid_type_length(self):
        payload = canonical_payload()[:PAYLOAD_LENGTH - 1]
        payload[FLAGS_OFFSET] = 0b0000_0101
        self.assert_failed(
            FodId.try_from_base64(self.factory.signed_owid_base64(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)

    def test_short_hashed_email_payload_reports_invalid_type_length(self):
        payload = canonical_payload()[:PAYLOAD_LENGTH - 1]
        self.assertEqual(IdType.HASHED_EMAIL,
                         IdType.from_flags(payload[FLAGS_OFFSET]))
        self.assert_failed(
            FodId.try_from_base64(self.factory.signed_owid_base64(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)

    def test_header_only_random_payload_reports_invalid_type_length(self):
        payload = canonical_random_payload()[:HEADER_LENGTH]
        self.assert_failed(
            FodId.try_from_base64(self.factory.signed_owid_base64(payload)),
            FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH)

    def test_payload_shorter_than_the_header_reports_payload_too_short(self):
        for length in range(HEADER_LENGTH):
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
            canonical_random_payload()[:RANDOM_PAYLOAD_LENGTH - 1])
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
        self.assertEqual(raising.match_key, result.value.match_key)

class FodIdTermsTests(unittest.TestCase):
    """The Terms byte, which says which terms document the identifier was
    created under so that the terms travel with the identifier. The byte is
    an index into a table in the specification and not a version number,
    and it follows the match key, so the identifier type fixes where it
    sits. The package turns the index into the address, so ``terms``
    answers with the address and a caller never handles the byte.
    """

    def setUp(self):
        self.factory = FodIdTestFactory()

    def _read(self, payload):
        return FodId.from_base64(self.factory.signed_owid_base64(payload))

    # ----- A payload that ends at the match key -----

    def test_payload_ending_at_the_match_key_has_no_address(self):
        # There is no byte after the match key to read. A missing byte is
        # index 0, which says the terms are not stated in the identifier,
        # so absence and zero mean the same thing and no presence flag is
        # needed to tell them apart.
        for name, payload, length in (
                ("probabilistic", payload_ending_at_match_key(),
                 MATCH_KEY_LENGTH),
                ("random", random_payload_ending_at_match_key(),
                 GUID_LENGTH)):
            with self.subTest(name):
                fod = self._read(payload)
                self.assertIsNone(fod.terms)
                self.assertEqual(length, len(fod.match_key))

    def test_an_absent_byte_and_a_zero_byte_read_the_same(self):
        absent = self._read(payload_ending_at_match_key())
        stated = self._read(with_terms(payload_ending_at_match_key(),
                                       ABSENT_TERMS_INDEX))
        self.assertEqual(absent.terms, stated.terms)
        self.assertIsNone(absent.terms)
        self.assertIsNone(stated.terms)

    # ----- An index this package knows -----

    def test_index_one_answers_with_the_model_terms_address(self):
        for name, payload, length in (
                ("probabilistic", payload_ending_at_match_key(),
                 MATCH_KEY_LENGTH),
                ("random", random_payload_ending_at_match_key(),
                 GUID_LENGTH)):
            with self.subTest(name):
                fod = self._read(with_terms(payload, MODEL_TERMS_INDEX))
                self.assertEqual(MODEL_TERMS_URL, fod.terms)
                self.assertEqual(length, len(fod.match_key))

    def test_the_address_is_the_versioned_document(self):
        # The address names the exact document in force when the
        # identifier was made, because a receiver has to be able to check
        # years later what it agreed to, and an address whose contents can
        # be edited cannot answer that.
        fod = self._read(with_terms(payload_ending_at_match_key(),
                                    MODEL_TERMS_INDEX))
        self.assertEqual("https://m4ow.uk/mtm/2.txt", fod.terms)

    # ----- An index this package does not know -----

    def test_an_unknown_index_has_no_address(self):
        # No address is ever built from an index this package cannot name,
        # because that would name a document nobody wrote and a receiver
        # would record having accepted terms that do not exist.
        fod = self._read(with_terms(payload_ending_at_match_key(),
                                    UNKNOWN_TERMS_INDEX))
        self.assertIsNone(fod.terms)

    def test_an_unknown_index_answers_as_no_terms_stated_does(self):
        # A caller cannot tell the two apart, which is deliberate, since
        # both say the identifier does not give the terms and the answer
        # has to come from somewhere else.
        unknown = self._read(with_terms(payload_ending_at_match_key(),
                                        UNKNOWN_TERMS_INDEX))
        none = self._read(with_terms(payload_ending_at_match_key(),
                                     ABSENT_TERMS_INDEX))
        self.assertIsNone(none.terms)
        self.assertIsNone(unknown.terms)

    def test_every_index_the_package_does_not_know_has_no_address(self):
        for index in (2, 3, 127, 128, 255):
            with self.subTest(index=index):
                fod = self._read(
                    with_terms(payload_ending_at_match_key(), index))
                self.assertIsNone(fod.terms)
                self.assertIs(Terms.UNKNOWN, Terms.from_index(index))

    # ----- The byte is read at the right offset -----

    def test_terms_is_read_before_a_creator_context_section(self):
        # The bytes after the Terms are a creator context section whose
        # lengths belong to the cloud, so the byte has to be read at the
        # offset the match key ends at and not at the end of the payload.
        for name, payload, key in (
                ("probabilistic", payload_ending_at_match_key(),
                 CANONICAL_MATCH_KEY),
                ("random", random_payload_ending_at_match_key(),
                 bytes((0x40 + i) for i in range(GUID_LENGTH)))):
            with self.subTest(name):
                built = (with_terms(payload, MODEL_TERMS_INDEX)
                         + CONTEXT_SECTION)
                fod = self._read(built)
                self.assertEqual(key, fod.match_key)
                self.assertEqual(MODEL_TERMS_URL, fod.terms)

    def test_a_context_section_alone_does_not_state_terms(self):
        # The first byte after the match key is the Terms and not the
        # start of the context section, so a section opening with a zero
        # reads as terms that are not stated.
        built = (with_terms(payload_ending_at_match_key(),
                            ABSENT_TERMS_INDEX)
                 + CONTEXT_SECTION)
        fod = self._read(built)
        self.assertIsNone(fod.terms)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)

    def test_reserved_type_takes_every_byte_as_its_match_key(self):
        # A Reserved type has no defined match key length, so its
        # documented best-effort reading takes every byte after the header
        # and leaves none to read as the Terms. It therefore states no
        # terms.
        payload = payload_ending_at_match_key()
        payload[FLAGS_OFFSET] = 0b1100_0101
        fod = self._read(with_terms(payload, MODEL_TERMS_INDEX))
        self.assertIs(IdType.RESERVED, fod.type)
        self.assertIsNone(fod.terms)

    # ----- The same answer from every reader -----

    def test_every_reader_reads_the_same_terms(self):
        payload = with_terms(payload_ending_at_match_key(),
                             MODEL_TERMS_INDEX)
        base64 = self.factory.signed_owid_base64(payload)
        owid = self.factory.signed_owid(payload)
        readers = (
            FodId.from_base64(base64),
            FodId.from_byte_array(self.factory.signed_bytes(payload)),
            FodId.from_owid(owid),
            FodId(owid),
            FodId.try_from_base64(base64).value,
            FodId.try_from_byte_array(
                self.factory.signed_bytes(payload)).value,
        )
        for fod in readers:
            self.assertEqual(MODEL_TERMS_URL, fod.terms)

    def test_base64_roundtrip_preserves_the_terms(self):
        first = self._read(with_terms(payload_ending_at_match_key(),
                                      MODEL_TERMS_INDEX))
        for base64 in (first.as_base64(), first.as_base64_url()):
            fod = FodId.from_base64(base64)
            self.assertEqual(first.terms, fod.terms)
            self.assertEqual(MODEL_TERMS_URL, fod.terms)

    def test_terms_does_not_change_how_the_other_fields_read(self):
        # The byte must not move any field before it, so an identifier
        # reads the same with the byte and without.
        without = self._read(payload_ending_at_match_key())
        stated = self._read(with_terms(payload_ending_at_match_key(),
                                       MODEL_TERMS_INDEX))
        self.assertEqual(without.type, stated.type)
        self.assertEqual(without.usage, stated.usage)
        self.assertEqual(without.usage_from_consent,
                         stated.usage_from_consent)
        self.assertEqual(without.license_id, stated.license_id)
        self.assertEqual(without.match_key, stated.match_key)

    def test_the_payload_rules_are_unchanged_by_the_terms(self):
        # A payload one byte short of its match key still fails, and a
        # Terms byte written onto it only makes up the match key, because
        # the type says how many bytes the match key takes and only then
        # does the Terms begin.
        short = random_payload_ending_at_match_key()[
            :RANDOM_PAYLOAD_LENGTH - 1]
        result = FodId.try_from_base64(
            self.factory.signed_owid_base64(short))
        self.assertFalse(result.ok)
        self.assertIs(FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH,
                      result.status)
        fod = self._read(with_terms(short, MODEL_TERMS_INDEX))
        self.assertEqual(GUID_LENGTH, len(fod.match_key))
        self.assertIsNone(fod.terms)


class FodIdVersionTests(unittest.TestCase):
    """Bits 4 and 5 of the flags byte, being the payload layout version.
    This package reads version 0 and refuses every other version rather
    than reading fields that may have moved.
    """

    def setUp(self):
        self.factory = FodIdTestFactory()

    def _read(self, payload):
        return FodId.try_from_base64(
            self.factory.signed_owid_base64(payload))

    def test_version_zero_reads_every_field(self):
        result = self._read(canonical_payload())
        self.assertTrue(result.ok)
        fod = result.value
        self.assertIs(IdType.HASHED_EMAIL, fod.type)
        self.assertIs(Usage.PERSONALIZED, fod.usage)
        self.assertEqual(CANONICAL_LICENSE_ID, fod.license_id)
        self.assertEqual(CANONICAL_MATCH_KEY, fod.match_key)
        self.assertEqual(MODEL_TERMS_URL, fod.terms)

    def test_the_layout_names_the_version_this_package_reads(self):
        self.assertEqual(0, SUPPORTED_PAYLOAD_VERSION)

    def test_an_unassigned_version_is_refused(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                result = self._read(
                    with_payload_version(canonical_payload(), version))
                self.assertFalse(result.ok)
                self.assertIs(
                    FodIdParseStatus.UNSUPPORTED_PAYLOAD_VERSION,
                    result.status)
                # Nothing is handed back, rather than a value with some
                # fields filled in, because there is no identifier to
                # expose fields for when the layout was not understood.
                self.assertIsNone(result.value)

    def test_the_raising_readers_name_the_version(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                base64 = self.factory.signed_owid_base64(
                    with_payload_version(canonical_payload(), version))
                with self.assertRaises(ValueError) as caught:
                    FodId.from_base64(base64)
                self.assertIn("version {0}".format(version),
                              str(caught.exception))

    def test_the_version_is_read_apart_from_the_usage_and_type_bits(self):
        # A reader masking the wrong bits would refuse a version 0
        # identifier or let a later version through, so every combination
        # is tried.
        for usage in (0b000, 0b001, 0b011, 0b111):
            for id_type in (0b00, 0b10, 0b11):
                flags = (id_type << 6) | usage
                payload = payload_ending_at_match_key()
                payload[FLAGS_OFFSET] = flags
                with self.subTest(flags=flags):
                    self.assertTrue(self._read(payload).ok)
                    for version in (1, 2, 3):
                        refused = self._read(
                            with_payload_version(payload, version))
                        self.assertIs(
                            FodIdParseStatus.UNSUPPORTED_PAYLOAD_VERSION,
                            refused.status)
                        self.assertIsNone(refused.value)


class TermsTests(unittest.TestCase):
    """The Terms vocabulary on its own, without an identifier around it.
    It is private to the package, so these tests reach it directly."""

    def test_the_layout_gives_the_terms_one_byte(self):
        self.assertEqual(1, TERMS_LENGTH)
        self.assertEqual(0, ABSENT_TERMS_INDEX)

    def test_from_index_names_the_indexes_the_package_knows(self):
        self.assertIs(Terms.NOT_STATED, Terms.from_index(0))
        self.assertIs(Terms.MODEL_TERMS_FOR_MARKETING_2,
                      Terms.from_index(1))

    def test_from_index_names_every_other_index_unknown(self):
        for index in range(2, 256):
            self.assertIs(Terms.UNKNOWN, Terms.from_index(index))

    def test_only_a_named_document_has_an_address(self):
        self.assertIsNone(Terms.NOT_STATED.url)
        self.assertIsNone(Terms.UNKNOWN.url)
        self.assertEqual("https://m4ow.uk/mtm/2.txt",
                         Terms.MODEL_TERMS_FOR_MARKETING_2.url)

    def test_every_member_agrees_with_the_table(self):
        # Each member carries its own index and address, and the index to
        # member map is built from the members, so this fails if a member
        # does not read back from its own index or if one that names a
        # document was added without an address.
        for member in Terms:
            if member is Terms.UNKNOWN:
                # Stands for every index the table does not carry, so it
                # has no index of its own and no address.
                self.assertEqual(-1, member.index)
                self.assertIsNone(member.url)
                continue
            self.assertIs(
                member, Terms.from_index(member.index),
                "{0} does not read back from its own index".format(member))
            if member is Terms.NOT_STATED:
                # Names no document, so it has no address.
                self.assertEqual(0, member.index)
                self.assertIsNone(member.url)
            else:
                self.assertIsNotNone(
                    member.url,
                    "{0} names a document with no address".format(member))
                self.assertTrue(member.url.startswith("https://"))

    def test_no_two_members_share_an_index(self):
        # One index stands for one document, so which document an
        # identifier was created under never depends on the order the
        # members happen to be written in.
        indexes = [m.index for m in Terms if m.index >= 0]
        self.assertEqual(len(indexes), len(set(indexes)))

    def test_the_named_value_is_not_part_of_the_package_surface(self):
        # The address on FodId is the whole of what a caller reads, so the
        # named value is not exported from the package.
        import fiftyone_pipeline_did as package
        self.assertFalse(hasattr(package, "Terms"))

if __name__ == "__main__":
    unittest.main()
