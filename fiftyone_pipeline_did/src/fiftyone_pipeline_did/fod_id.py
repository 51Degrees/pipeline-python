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

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import NamedTuple, Optional, Tuple

from ._layout import (
    ABSENT_TERMS_INDEX,
    FLAGS_OFFSET,
    GUID_LENGTH,
    HEADER_LENGTH,
    LICENSE_ID_LENGTH,
    LICENSE_ID_OFFSET,
    MATCH_KEY_LENGTH,
    MATCH_KEY_OFFSET,
    SUPPORTED_PAYLOAD_VERSION,
    TERMS_LENGTH,
)
from ._owid import (
    Owid,
    OwidError,
    ParseResult,
    ParseStatus,
    SignatureStatus,
    Version,
)

from .id_type import IdType
from ._terms import Terms
from .usage import Usage

#: The moment the envelope's date field counts minutes from, being the OWID
#: epoch of 2020-01-01T00:00:00Z. The envelope carries an unsigned 32-bit
#: count of minutes since this moment, and :attr:`FodId.date` is that count
#: read as an aware UTC datetime.
DATE_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


class FodIdParseStatus(Enum):
    """Why reading a 51Did succeeded or failed.

    The vocabulary is the OWID one, member for member and value for value,
    with two members added for the checks this package makes on the payload
    once the envelope has been read. A failure in the envelope keeps the
    OWID status unchanged, so a caller sees the same reason whichever
    language read the bytes, and a failure in the payload names which of the
    two 51Did rules was broken.

    Every member other than :attr:`PARSED` is an expected outcome for data
    that arrived from outside, not a fault in the program. A parse that
    reports :attr:`PARSED` says the bytes have the shape of a 51Did and
    nothing about whether the signature is genuine, which is a separate
    question answered by :meth:`FodId.verify` or
    :meth:`FodId.signature_status`.
    """

    #: The bytes form a structurally valid 51Did. Says nothing about the
    #: signature.
    PARSED = "Parsed"
    #: Nothing was supplied to parse.
    MISSING_INPUT = "MissingInput"
    #: The input was supplied in a form this surface cannot read.
    INVALID_INPUT_TYPE = "InvalidInputType"
    #: The string is not valid base 64, so there are no bytes to read.
    INVALID_BASE64 = "InvalidBase64"
    #: The first byte names an envelope version this package does not know.
    UNSUPPORTED_VERSION = "UnsupportedVersion"
    #: The data stopped in the middle of an envelope field.
    UNEXPECTED_END = "UnexpectedEnd"
    #: The creator domain is not terminated, or is longer than the OWID
    #: maximum.
    INVALID_DOMAIN_ENCODING = "InvalidDomainEncoding"
    #: The declared payload byte count disagrees with the bytes present.
    BYTE_COUNT_MISMATCH = "ByteCountMismatch"
    #: The envelope is consistent but larger than this runtime can hold, or
    #: dated past the end of the year 9999 where ``datetime`` stops. The
    #: four byte minute count of OWID versions 2 and 3 runs to 15 February
    #: 10186, and the OWID reader judges the count before the arithmetic,
    #: so a read answers with this status rather than raising. The same
    #: bytes read fine where the date type is wider, so the status is not a
    #: fault in the data.
    IMPLEMENTATION_CAPACITY_EXCEEDED = "ImplementationCapacityExceeded"
    #: The version 0 marker, which stands for an absent envelope and never
    #: produces a value.
    ABSENT_NODE = "AbsentNode"
    #: The envelope is malformed in a way none of the above describes.
    MALFORMED_ENVELOPE = "MalformedEnvelope"

    #: The envelope was read but its payload is shorter than the 5 byte
    #: header (flags and licence id), so the identifier type cannot even be
    #: read.
    PAYLOAD_TOO_SHORT = "PayloadTooShort"
    #: The header was read and names a type whose match key needs more
    #: bytes than the payload holds, being a 16 byte GUID match key after
    #: the header for Random and a 32 byte SHA-256 match key for
    #: Probabilistic and HashedEmail.
    INVALID_TYPE_PAYLOAD_LENGTH = "InvalidTypePayloadLength"
    #: Bits 4 and 5 of the flags byte name a payload layout version this
    #: package does not know, so no field is read. A later version exists
    #: precisely because a field moved, so reading the payload under the
    #: layout this package knows would answer with values that are wrong
    #: rather than absent.
    UNSUPPORTED_PAYLOAD_VERSION = "UnsupportedPayloadVersion"

    @classmethod
    def of(cls, status: ParseStatus) -> "FodIdParseStatus":
        """The member carrying an OWID status, unchanged in name and
        value."""
        return cls[status.name]


class FodIdParseResult(NamedTuple):
    """What a 51Did parse produced, and why.

    Three facts, exactly as the OWID library reports them. Whether the parse
    succeeded, the value (which is absent on failure, never a partly read
    identifier), and the status, which is :attr:`FodIdParseStatus.PARSED` on
    success and the specific reason otherwise. Truthy on success, so
    ``if result:`` reads naturally.

    A successful parse says the bytes have the shape of a 51Did. The
    signature has not been checked, so the value is not known to be genuine
    until :meth:`FodId.verify` or a :class:`~fiftyone_pipeline_did.DidClient`
    check says so.
    """

    #: True when the input was a complete, structurally valid 51Did.
    ok: bool
    #: The identifier on success, otherwise None.
    value: Optional["FodId"]
    #: PARSED on success, otherwise the specific reason.
    status: FodIdParseStatus

    def __bool__(self) -> bool:
        return self.ok


def _failed(status: FodIdParseStatus) -> FodIdParseResult:
    return FodIdParseResult(False, None, status)


class FodId:
    """A strongly typed reader for the 51Did (51Degrees Identifier) value
    returned by the 51Degrees Cloud service.

    A 51Did is described at three levels. The **51Did** is the identifier as a
    whole. The **envelope** is the signed
    :class:`~fiftyone_pipeline_did.Owid` that carries it (version, domain,
    date, payload, signature), re-issued fresh on every call.
    The **match key** is the stable, comparable part of the payload after
    the Flags and License Id, exposed as :attr:`match_key`. Two 51Dids for
    the same inputs share the same match key even though their envelopes
    differ. *Compare match keys, never envelopes.*

    Payload layout. Every field has a typed accessor here, being
    :attr:`type`, :attr:`usage`, :attr:`usage_from_consent`,
    :attr:`license_id`, :attr:`match_key` and :attr:`terms`, and those
    accessors are the supported way to read an identifier. The bytes and offsets behind them
    are specified at
    https://github.com/51Degrees/specifications/blob/main/did-specification/identifier-layout.md
    and the surface this class offers, which is the same in every 51Did
    package, at
    https://github.com/51Degrees/specifications/blob/main/did-specification/package-surface.md
    which are the authority for both. In short, the header is shared by
    every identifier type and the type then fixes the length of the match
    key that follows, being a 32-byte SHA-256 for Probabilistic and
    HashedEmail or 16 GUID bytes for Random, and the Terms byte follows the
    match key. A payload longer than that is accepted, because the bytes
    after the Terms are a creator context section whose lengths belong to
    the cloud, so this package places no upper bound on a payload or an
    envelope. A payload that ends at the match key reads as terms that are
    not stated.

    Bits 4 and 5 of the flags byte say which payload layout the identifier
    follows, and this package reads version 0. A payload naming any other
    version is refused with
    :attr:`FodIdParseStatus.UNSUPPORTED_PAYLOAD_VERSION` rather than read
    under the layout this package knows, because a later version exists
    precisely because a field moved, so reading one here would answer with
    values that are wrong rather than absent. The version is not exposed,
    because a caller has nothing to decide with it.

    Reading and verifying are separate steps. :meth:`try_from_base64` and
    :meth:`try_from_byte_array` read external data without raising and
    answer with a :class:`FodIdParseResult` naming the reason either way,
    whilst :meth:`from_base64`, :meth:`from_byte_array` and the constructor
    raise for the same inputs. None of them checks the signature, so a
    parsed 51Did is not known to be genuine until :meth:`verify` or
    :meth:`signature_status` says so.

    This type **composes** an OWID (holds the wrapped envelope and delegates
    OWID-level concerns to it) rather than inheriting from it.
    """

    def __init__(self, owid: Owid) -> None:
        """Promotes an already-parsed :class:`~fiftyone_pipeline_did.Owid`
        into a 51Did by unpacking its payload.

        The envelope is written out and read back through this package's
        own parser rather than held by reference, so the ``FodId`` owns an
        envelope of its own whatever object the caller passed in.

        Raises :class:`TypeError` if ``owid`` is ``None``,
        :class:`~fiftyone_pipeline_did.OwidError` if the envelope cannot be
        written out and read back, and :class:`ValueError` if the payload is
        shorter than the header or than the minimum for its identifier
        type.
        """
        if owid is None:
            raise TypeError("owid must not be None")
        read = Owid.parse_bytes(owid.as_byte_array())
        if not read.ok:
            raise OwidError(
                "the envelope could not be read back: {0}".format(
                    read.status.value))
        self._assign(read.owid, *_unpack_or_raise(read.owid.payload))

    def _assign(self, owid: Owid, flags: int, license_id: int,
                match_key: bytes, terms_index: int) -> None:
        self._owid = owid
        self._flags = flags
        self._license_id = license_id
        self._match_key = match_key
        self._terms_index = terms_index

    @classmethod
    def _build(cls, owid: Owid, flags: int, license_id: int,
               match_key: bytes, terms_index: int) -> "FodId":
        """An identifier over fields :func:`_read_payload` has already
        checked, so the constructor's read is not repeated."""
        fod_id = cls.__new__(cls)
        fod_id._assign(owid, flags, license_id, match_key, terms_index)
        return fod_id

    @classmethod
    def _from_read(cls, read: ParseResult) -> FodIdParseResult:
        """The non-raising reader over an OWID read. Carries an OWID failure
        through unchanged, then applies the two 51Did payload rules, and
        builds the identifier only when both have passed."""
        if not read.ok:
            return _failed(FodIdParseStatus.of(read.status))
        status, flags, license_id, match_key, terms_index = _read_payload(
            read.owid.payload)
        if status is not FodIdParseStatus.PARSED:
            return _failed(status)
        return FodIdParseResult(
            True,
            cls._build(read.owid, flags, license_id, match_key, terms_index),
            FodIdParseStatus.PARSED)

    @classmethod
    def _from_read_or_raise(cls, read: ParseResult, argument: str) \
            -> "FodId":
        """The raising reader over the same OWID read and the same payload
        rules, so there is one reading and not two. The exception type
        follows the kind of failure, which is what the raising readers have
        always done."""
        if not read.ok:
            if read.status is ParseStatus.INVALID_INPUT_TYPE:
                raise TypeError(
                    "{0} is not a type this reader accepts".format(argument))
            raise OwidError("{0} is not a valid 51Did: {1}".format(
                argument, read.status.value))
        return cls._build(read.owid, *_unpack_or_raise(read.owid.payload))

    @classmethod
    def try_from_base64(cls, value) -> FodIdParseResult:
        """Reads a 51Did from its base64 form in either alphabet without
        raising.

        The cloud issues a 51Did in the standard alphabet with padding, and
        a page puts one in a link in the URL-safe alphabet (``-`` and ``_``)
        without padding. Both are accepted, with or without padding, by
        normalising to the standard form before the envelope is read.

        The value may be anything at all, as external data is. ``None`` and
        the empty string report :attr:`FodIdParseStatus.MISSING_INPUT`,
        anything other than a string reports
        :attr:`FodIdParseStatus.INVALID_INPUT_TYPE`, and every other failure
        names its reason. The signature is not checked.
        """
        return cls._from_read(_read_base64(value))

    @classmethod
    def try_from_byte_array(cls, buffer) -> FodIdParseResult:
        """Reads a 51Did from the raw bytes of an envelope without raising.

        The buffer must hold exactly one envelope. ``None`` and an empty
        buffer report :attr:`FodIdParseStatus.MISSING_INPUT`, anything that
        is not ``bytes``, ``bytearray`` or ``memoryview`` reports
        :attr:`FodIdParseStatus.INVALID_INPUT_TYPE`, and every other failure
        names its reason. The signature is not checked.
        """
        return cls._from_read(Owid.parse_bytes(buffer))

    @classmethod
    def from_base64(cls, base64: str) -> "FodId":
        """Parses a 51Did from its base64-encoded OWID string in either
        alphabet, raising when the value is not one.

        The same reading as :meth:`try_from_base64`, for callers who prefer
        an exception. Raises :class:`TypeError` if ``base64`` is ``None`` or
        not a string, :class:`ValueError` if the envelope was read but its
        payload is shorter than the header or than the minimum for its
        identifier type, and :class:`~fiftyone_pipeline_did.OwidError` for
        every other failure, with the message naming the
        :class:`FodIdParseStatus`.
        """
        if base64 is None:
            raise TypeError("base64 must not be None")
        return cls._from_read_or_raise(_read_base64(base64), "base64")

    @staticmethod
    def to_standard_base64(value: str) -> str:
        """Restores a base64 string in either alphabet to the standard
        alphabet with padding, which is the form the OWID library decodes.

        ``-`` becomes ``+`` and ``_`` becomes ``/``, then ``==`` is added
        when the length modulo 4 is 2 and ``=`` when it is 3. A value already
        in the standard padded form is returned unchanged.
        """
        cleaned = value.strip().replace("-", "+").replace("_", "/")
        remainder = len(cleaned) % 4
        if remainder == 2:
            cleaned += "=="
        elif remainder == 3:
            cleaned += "="
        return cleaned

    @staticmethod
    def to_base64_url(value: str) -> str:
        """Converts a base64 string in either alphabet to the URL-safe
        alphabet without padding, the inverse of :meth:`to_standard_base64`,
        so a 51Did can be placed in a URL without further encoding.
        """
        return value.strip().replace("+", "-").replace("/", "_").rstrip("=")

    @classmethod
    def from_byte_array(cls, buffer: bytes) -> "FodId":
        """Parses a 51Did from the raw bytes of an OWID envelope, raising
        when the bytes are not one.

        The same reading as :meth:`try_from_byte_array`, for callers who
        prefer an exception. Raises :class:`TypeError` if ``buffer`` is
        ``None`` or not a bytes-like object, :class:`ValueError` if the
        envelope was read but its payload is shorter than the header or than
        the minimum for its identifier type, and
        :class:`~fiftyone_pipeline_did.OwidError` for every other failure,
        with the message naming the :class:`FodIdParseStatus`.
        """
        if buffer is None:
            raise TypeError("buffer must not be None")
        return cls._from_read_or_raise(Owid.parse_bytes(buffer), "buffer")

    @classmethod
    def from_owid(cls, owid: Owid) -> "FodId":
        """Promotes an already-parsed OWID into a 51Did.

        The constructor writes the envelope out and reads it back through
        this package's own parser rather than holding the caller's object,
        so the ``FodId`` owns an envelope of its own. Raises
        :class:`TypeError` if ``owid`` is ``None``, and otherwise what the
        constructor raises.
        """
        if owid is None:
            raise TypeError("owid must not be None")
        return cls(owid)

    @property
    def type(self) -> IdType:
        """The identifier type, being Probabilistic, Random, HashedEmail or
        Reserved. See :class:`~fiftyone_pipeline_did.IdType`."""
        return IdType.from_flags(self._flags)

    @property
    def usage(self) -> Usage:
        """The usage the identifier was created for, as the highest usage
        granted. See :class:`~fiftyone_pipeline_did.Usage` for why it is
        read that way and for what each usage allows."""
        return Usage.from_flags(self._flags)

    @property
    def usage_from_consent(self) -> bool:
        """Whether the usage was derived from an IAB consent string the
        caller sent, rather than stated by the caller directly. Both are
        legitimate ways to arrive at a usage, and this says nothing about
        which usage it is."""
        return (self._flags & 0b1000) != 0

    @property
    def license_id(self) -> int:
        """The raw value of the 4-byte little-endian License Id field
        (0 to 4294967295).

        On an identifier carrying a creator context, the four bytes at
        offset 1 hold an encrypted value that only 51Degrees can turn back
        into a licence identifier, so this property is the field's raw value
        and identifies nothing outside 51Degrees.
        """
        return self._license_id

    @property
    def match_key(self) -> bytes:
        """The match key from the payload, a 32-byte SHA-256 for
        Probabilistic and HashedEmail identifiers, or 16 GUID bytes for
        Random ones.

        The match key is the stable, comparable part of the envelope. Two
        51Dids for the same inputs share the same match key even though
        their envelopes (date, signature) differ on every issue. Use the
        match key as the cache key and as the key for spotting duplicates.
        """
        return self._match_key

    @property
    def terms(self) -> Optional[str]:
        """The address of the terms document the identifier was created
        under, so the terms travel with the identifier instead of
        alongside it.

        The byte after the match key is an index into a table in the
        specification and this package turns the index into the address,
        so a caller never handles the byte. The address is answered and
        never fetched, because what to do with the document is the
        receiver's decision.

        ``None`` covers both an index of zero, which says the terms are
        not stated in the identifier, and an index added to the table
        after this package was released, which it cannot name. A caller
        cannot tell those two apart, which is deliberate, because both
        lead to the same place, being that the identifier does not say
        which terms it was created under and the answer has to come from
        somewhere else. No address is ever built from an index this
        package does not know, since that would name a document nobody
        wrote.

        No address does not mean the identifier is unrestricted. Where an
        identifier may go is a separate question :attr:`usage` answers,
        which still bars a non-marketing identifier from a demand source.
        """
        return Terms.from_index(self._terms_index).url

    @property
    def version(self) -> Version:
        """The OWID version."""
        return self._owid.version

    @property
    def domain(self) -> str:
        """The domain of the OWID creator."""
        return self._owid.domain

    @property
    def date(self) -> datetime:
        """The OWID creation date, as an aware UTC datetime."""
        return self._owid.date

    @property
    def payload(self) -> bytes:
        """The OWID payload bytes."""
        return self._owid.payload

    @property
    def signature(self) -> bytes:
        """The 64-byte OWID signature."""
        return self._owid.signature

    def as_base64(self) -> str:
        """Returns the OWID as a standard base64 string with padding, the
        form the cloud issues."""
        return self._owid.as_base64()

    def as_base64_url(self) -> str:
        """Returns the OWID as a URL-safe base64 string without padding, the
        form to place in a URL. :meth:`from_base64` accepts it back."""
        return self.to_base64_url(self.as_base64())

    def as_byte_array(self) -> bytes:
        """Returns the OWID as a byte array including the signature."""
        return self._owid.as_byte_array()

    def verify(self, public_pem: str) -> bool:
        """Verifies the OWID signature against the supplied public key. This
        is an explicit, separate step, because parsing never verifies.

        Answers ``False`` only when the signature is well formed and does
        not match. A key that cannot be decoded raises, as the fault is in
        the key and not the identifier, so an outage is never reported as a
        forgery. :meth:`signature_status` gives the same answer as a named
        status without raising.
        """
        return self._owid.verify_with_public_key(public_pem, [])

    def signature_status(self, public_pem: str) -> SignatureStatus:
        """Says whether the signature is genuine, or why that could not be
        decided, in the OWID vocabulary.

        Only :attr:`~fiftyone_pipeline_did.SignatureStatus.SIGNATURE_VALID`
        and :attr:`~fiftyone_pipeline_did.SignatureStatus.SIGNATURE_INVALID`
        are about the signature. The others say the question could not be
        answered, for example
        :attr:`~fiftyone_pipeline_did.SignatureStatus.KEY_UNAVAILABLE` when
        no key was given, and must never be read as a forgery.
        """
        return self._owid.signature_status(public_pem, [])


def _read_base64(value) -> ParseResult:
    """The OWID read of a base64 string in either alphabet. Anything that is
    not a string goes to the OWID reader as given, so the reason it reports
    (nothing supplied, or a type it cannot read) is the one carried."""
    if isinstance(value, str):
        value = FodId.to_standard_base64(value)
    return Owid.parse(value)


def _date_minutes(fod_id: "FodId") -> int:
    """The envelope's date as the unsigned 32-bit count of minutes since
    :data:`DATE_EPOCH`, which is the form the envelope carries on the wire.

    Private to this package. :attr:`FodId.date` is the supported way to
    read the creation moment, and the client uses this count only where it
    needs the same whole minute the envelope holds.
    """
    return int((fod_id.date - DATE_EPOCH).total_seconds() // 60)


def _read_payload(
        payload: bytes) -> Tuple[FodIdParseStatus, int, int, bytes, int]:
    """Applies the two 51Did payload rules and unpacks the four fields.

    The header must be present before the type can be read, and the type
    then says how many match key bytes must follow. The Terms byte follows
    the match key, and anything beyond it is a creator context section
    whose lengths belong to the cloud, so a longer payload passes. A
    Reserved type has no known match key length and keeps the documented
    best-effort reading, being the header fields and whatever bytes follow.

    Returns the status and, on success, the flags, the licence id, the
    match key bytes and the Terms index. On failure the four fields are
    zero and empty.
    """
    if payload is None or len(payload) < HEADER_LENGTH:
        return FodIdParseStatus.PAYLOAD_TOO_SHORT, 0, 0, b"", 0
    flags = payload[FLAGS_OFFSET]
    # The version is read before any field, because a later version exists
    # precisely because a field moved. Reading a payload of a version this
    # package does not know under the layout it does know would answer with
    # values that are wrong rather than absent, which is worse than
    # refusing, and a version that nothing checks protects nothing.
    if _payload_version(flags) != SUPPORTED_PAYLOAD_VERSION:
        return (
            FodIdParseStatus.UNSUPPORTED_PAYLOAD_VERSION, 0, 0, b"", 0)
    match_key_length = _match_key_length(IdType.from_flags(flags), payload)
    if len(payload) < HEADER_LENGTH + match_key_length:
        return FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH, 0, 0, b"", 0
    # Little-endian uint32, unsigned (Python ints are unbounded and
    # non-negative here, so the high bit never becomes negative).
    license_id = int.from_bytes(
        payload[LICENSE_ID_OFFSET:LICENSE_ID_OFFSET + LICENSE_ID_LENGTH],
        byteorder="little",
        signed=False,
    )
    # bytes is immutable, so slicing yields a match key that cannot be used
    # to change the underlying payload and no defensive copy is required.
    match_key = bytes(
        payload[MATCH_KEY_OFFSET:MATCH_KEY_OFFSET + match_key_length])
    return (FodIdParseStatus.PARSED, flags, license_id, match_key,
            _read_terms_index(payload, MATCH_KEY_OFFSET + match_key_length))


def _read_terms_index(payload: bytes, offset: int) -> int:
    """The Terms byte at the offset the match key ends at, and the index
    that says the terms are not stated where the payload ends there.

    A payload ending at the match key has no byte to read, so absence and
    zero mean the same thing and neither has to be told apart from the
    other.

    A Reserved type cannot carry a Terms byte this package can find,
    because no match key length is defined for that type and so every byte
    after the header is its match key. The offset then lands at the end of
    the payload, nothing is left to read, and the identifier answers with
    the index that says the terms are not stated. That is the right answer
    and not a defect, so no special case is written for it.
    """
    if len(payload) < offset + TERMS_LENGTH:
        return ABSENT_TERMS_INDEX
    return payload[offset]


def _unpack_or_raise(payload: bytes) -> Tuple[int, int, bytes, int]:
    """The payload rules for the raising readers, with the messages they
    have always given."""
    status, flags, license_id, match_key, terms_index = _read_payload(payload)
    if status is not FodIdParseStatus.PARSED:
        raise ValueError(_payload_message(status, payload))
    return flags, license_id, match_key, terms_index


def _payload_version(flags: int) -> int:
    """Bits 4 and 5 of the flags byte, being the version of the payload
    layout the identifier follows. The envelope carries a version of its
    own at its first byte, which versions the envelope, whilst this one
    versions the payload.
    """
    return (flags >> 4) & 0b11


def _match_key_length(id_type: IdType, payload: bytes) -> int:
    """How many match key bytes the type needs after the header."""
    if id_type is IdType.RANDOM:
        return GUID_LENGTH
    if id_type is IdType.RESERVED:
        return len(payload) - HEADER_LENGTH
    return MATCH_KEY_LENGTH


def _payload_message(status: FodIdParseStatus, payload: bytes) -> str:
    """The message the raising readers give for a payload failure."""
    length = 0 if payload is None else len(payload)
    if status is FodIdParseStatus.PAYLOAD_TOO_SHORT:
        return "51Did payload must be at least {0} bytes; got {1}.".format(
            HEADER_LENGTH, length)
    if status is FodIdParseStatus.UNSUPPORTED_PAYLOAD_VERSION:
        return (
            "51Did payload version {0} is not one this package can "
            "read.".format(_payload_version(payload[FLAGS_OFFSET])))
    id_type = IdType.from_flags(payload[FLAGS_OFFSET])
    return ("51Did payload for the {0} type must be at least {1} bytes; "
            "got {2}.".format(
                id_type.name,
                HEADER_LENGTH + _match_key_length(id_type, payload),
                length))
