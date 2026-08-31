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
import warnings

from ._owid import (
    Owid,
    OwidError,
    ParseResult,
    ParseStatus,
    SignatureStatus,
    Version,
)

from .id_type import IdType

#: The moment the envelope's date field counts minutes from, being the OWID
#: epoch of 2020-01-01T00:00:00Z. :attr:`FodId.date_minutes` is the unsigned
#: 32-bit count of minutes since this moment.
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
    #: The envelope is consistent but larger than this runtime can hold.
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

    Payload layout. The header (offsets 0-4) is shared by every identifier
    type; bits 6-7 of Flags select the :class:`IdType` and the length of the
    match key that follows (32-byte SHA-256 for Probabilistic and
    HashedEmail, or 16 GUID bytes for Random). A payload longer than the
    header and match key is accepted, because the bytes after the match key
    are a creator context section whose lengths belong to the cloud, so
    this package places no upper bound on a payload or an envelope.

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

    #: Byte offset of the Flags field within the payload.
    FLAGS_OFFSET = 0
    #: Byte offset of the License Id field within the payload.
    LICENSE_ID_OFFSET = 1
    #: Byte length of the License Id field.
    LICENSE_ID_LENGTH = 4
    #: Byte offset of the match key field within the payload.
    HASH_OFFSET = 5
    #: Byte length of the match key field (SHA-256).
    HASH_LENGTH = 32
    #: Byte length of the header (Flags + License Id) common to every type.
    HEADER_LENGTH = HASH_OFFSET
    #: Byte length of the GUID match key carried by Random identifiers.
    GUID_LENGTH = 16
    #: Minimum byte length of a Random 51Did payload.
    RANDOM_PAYLOAD_LENGTH = HEADER_LENGTH + GUID_LENGTH
    #: Minimum byte length of a Probabilistic or HashedEmail 51Did payload.
    PAYLOAD_LENGTH = HASH_OFFSET + HASH_LENGTH

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
                match_key: bytes) -> None:
        self._owid = owid
        self._flags = flags
        self._license_id = license_id
        self._match_key = match_key

    @classmethod
    def _build(cls, owid: Owid, flags: int, license_id: int,
               match_key: bytes) -> "FodId":
        """An identifier over fields :func:`_read_payload` has already
        checked, so the constructor's read is not repeated."""
        fod_id = cls.__new__(cls)
        fod_id._assign(owid, flags, license_id, match_key)
        return fod_id

    @classmethod
    def _from_read(cls, read: ParseResult) -> FodIdParseResult:
        """The non-raising reader over an OWID read. Carries an OWID failure
        through unchanged, then applies the two 51Did payload rules, and
        builds the identifier only when both have passed."""
        if not read.ok:
            return _failed(FodIdParseStatus.of(read.status))
        status, flags, license_id, match_key = _read_payload(
            read.owid.payload)
        if status is not FodIdParseStatus.PARSED:
            return _failed(status)
        return FodIdParseResult(
            True, cls._build(read.owid, flags, license_id, match_key),
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
    def flags(self) -> int:
        """The 1-byte usage flags bit-mask from the payload (0-255)."""
        return self._flags

    @property
    def type(self) -> IdType:
        """The identifier type carried in bits 6-7 of :attr:`flags`."""
        return IdType.from_flags(self._flags)

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
    def hash(self) -> bytes:
        """Deprecated alias for :attr:`match_key`.

        The stable, comparable part of a 51Did is now called the match key,
        mirroring the Model Terms for Marketing vocabulary. Reading this
        property warns with :class:`DeprecationWarning` and returns the
        same bytes as :attr:`match_key`. The alias will be removed in a
        future release.
        """
        warnings.warn(
            "FodId.hash is renamed to FodId.match_key. This alias will be "
            "removed in a future release.",
            DeprecationWarning, stacklevel=2)
        return self._match_key

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
    def date_minutes(self) -> int:
        """The envelope's own date as the unsigned 32-bit count of minutes
        since :data:`DATE_EPOCH` (2020-01-01T00:00:00Z).

        This is the value the envelope carries on the wire and the value the
        OWID ``public-key?date=`` parameter takes, so a caller comparing
        creation times gets the integer rather than a converted date.
        """
        return int((self._owid.date - DATE_EPOCH).total_seconds() // 60)

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


def _read_payload(payload: bytes) -> Tuple[FodIdParseStatus, int, int, bytes]:
    """Applies the two 51Did payload rules and unpacks the three fields.

    The header must be present before the type can be read, and the type
    then says how many match key bytes must follow. Anything beyond the
    match key is a creator context section whose lengths belong to the
    cloud, so a longer payload passes. A Reserved type has no known match
    key length and keeps the documented best-effort reading, being the
    header fields and whatever bytes follow.

    Returns the status and, on success, the flags, the licence id and the
    match key bytes. On failure the three fields are zero and empty.
    """
    if payload is None or len(payload) < FodId.HEADER_LENGTH:
        return FodIdParseStatus.PAYLOAD_TOO_SHORT, 0, 0, b""
    flags = payload[FodId.FLAGS_OFFSET]
    match_key_length = _match_key_length(IdType.from_flags(flags), payload)
    if len(payload) < FodId.HEADER_LENGTH + match_key_length:
        return FodIdParseStatus.INVALID_TYPE_PAYLOAD_LENGTH, 0, 0, b""
    # Little-endian uint32, unsigned (Python ints are unbounded and
    # non-negative here, so the high bit never becomes negative).
    license_id = int.from_bytes(
        payload[FodId.LICENSE_ID_OFFSET:FodId.LICENSE_ID_OFFSET
                + FodId.LICENSE_ID_LENGTH],
        byteorder="little",
        signed=False,
    )
    # bytes is immutable, so slicing yields a match key that cannot be used
    # to change the underlying payload and no defensive copy is required.
    match_key = bytes(
        payload[FodId.HASH_OFFSET:FodId.HASH_OFFSET + match_key_length])
    return FodIdParseStatus.PARSED, flags, license_id, match_key


def _unpack_or_raise(payload: bytes) -> Tuple[int, int, bytes]:
    """The payload rules for the raising readers, with the messages they
    have always given."""
    status, flags, license_id, match_key = _read_payload(payload)
    if status is not FodIdParseStatus.PARSED:
        raise ValueError(_payload_message(status, payload))
    return flags, license_id, match_key


def _match_key_length(id_type: IdType, payload: bytes) -> int:
    """How many match key bytes the type needs after the header."""
    if id_type is IdType.RANDOM:
        return FodId.GUID_LENGTH
    if id_type is IdType.RESERVED:
        return len(payload) - FodId.HEADER_LENGTH
    return FodId.HASH_LENGTH


def _payload_message(status: FodIdParseStatus, payload: bytes) -> str:
    """The message the raising readers give for a payload failure."""
    length = 0 if payload is None else len(payload)
    if status is FodIdParseStatus.PAYLOAD_TOO_SHORT:
        return "51Did payload must be at least {0} bytes; got {1}.".format(
            FodId.HEADER_LENGTH, length)
    id_type = IdType.from_flags(payload[FodId.FLAGS_OFFSET])
    return ("51Did payload for the {0} type must be at least {1} bytes; "
            "got {2}.".format(
                id_type.name,
                FodId.HEADER_LENGTH + _match_key_length(id_type, payload),
                length))
