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

from owid import Owid, Version

from .id_type import IdType

#: The moment the envelope's date field counts minutes from, being the OWID
#: epoch of 2020-01-01T00:00:00Z. :attr:`FodId.date_minutes` is the unsigned
#: 32-bit count of minutes since this moment.
DATE_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


class FodId:
    """A strongly typed reader for the 51Did (51Degrees Identifier) value
    returned by the 51Degrees Cloud service.

    A 51Did is described at three levels. The **51Did** is the identifier as a
    whole. The **envelope** is the signed :class:`owid.Owid` that carries it
    (version, domain, date, payload, signature), re-issued fresh on every call.
    The **value** is the stable, comparable part of the payload after the Flags
    and License Id, exposed as :attr:`hash`. Two 51Dids for the same inputs
    share the same value even though their envelopes differ. *Compare values,
    never envelopes.*

    Payload layout. The header (offsets 0-4) is shared by every identifier
    type; bits 6-7 of Flags select the :class:`IdType` and the length of the
    value that follows (32-byte SHA-256 for Probabilistic and HashedEmail, or
    16 GUID bytes for Random).

    This type **composes** an OWID (holds the wrapped envelope and delegates
    OWID-level concerns to it) rather than inheriting from it. Constructing a
    ``FodId`` does **not** verify the signature; call :meth:`verify`
    explicitly.
    """

    #: Byte offset of the Flags field within the payload.
    FLAGS_OFFSET = 0
    #: Byte offset of the License Id field within the payload.
    LICENSE_ID_OFFSET = 1
    #: Byte length of the License Id field.
    LICENSE_ID_LENGTH = 4
    #: Byte offset of the value (Hash) field within the payload.
    HASH_OFFSET = 5
    #: Byte length of the SHA-256 value.
    HASH_LENGTH = 32
    #: Byte length of the header (Flags + License Id) common to every type.
    HEADER_LENGTH = HASH_OFFSET
    #: Byte length of the GUID value carried by Random identifiers.
    GUID_LENGTH = 16
    #: Minimum byte length of a Random 51Did payload.
    RANDOM_PAYLOAD_LENGTH = HEADER_LENGTH + GUID_LENGTH
    #: Minimum byte length of a Probabilistic or HashedEmail 51Did payload.
    PAYLOAD_LENGTH = HASH_OFFSET + HASH_LENGTH
    #: Largest possible byte length of a serialized 51Did envelope.
    MAXIMUM_BYTE_LENGTH = 136

    _MAXIMUM_PAYLOAD_LENGTH = 56

    def __init__(self, owid: Owid) -> None:
        """Promotes an already-parsed :class:`owid.Owid` into a 51Did by
        unpacking its payload.

        The OWID is **copied** (round-tripped through its byte form), not
        aliased, so a ``FodId`` can never desync from its envelope if the caller
        later mutates the OWID they passed in. The OWID must therefore be signed
        (serializable).

        Raises :class:`TypeError` if ``owid`` is ``None``, :class:`ValueError`
        if the envelope exceeds :attr:`MAXIMUM_BYTE_LENGTH` or the payload
        length is outside the range a 51Did can have, and
        :class:`owid.OwidError` if the OWID cannot be serialized (e.g. it is
        unsigned).
        """
        if owid is None:
            raise TypeError("owid must not be None")
        source_payload = owid.payload
        if len(owid.domain) > self.MAXIMUM_BYTE_LENGTH:
            raise self._too_long()
        wire = owid.as_byte_array()
        if len(wire) > self.MAXIMUM_BYTE_LENGTH:
            raise self._too_long(len(wire))
        if len(source_payload) > self._MAXIMUM_PAYLOAD_LENGTH:
            raise self._payload_too_long(len(source_payload))
        self._byte_length = len(wire)
        self._owid = Owid.from_byte_array(wire)
        payload = self._owid.payload
        if payload is None or len(payload) < self.HEADER_LENGTH:
            raise ValueError(
                "51Did payload must be at least {0} bytes; got {1}.".format(
                    self.HEADER_LENGTH, 0 if payload is None else len(payload)
                )
            )
        self._flags = payload[self.FLAGS_OFFSET]
        # Little-endian uint32, unsigned (Python ints are unbounded and
        # non-negative here, so the high bit never becomes negative).
        self._license_id = int.from_bytes(
            payload[self.LICENSE_ID_OFFSET:self.LICENSE_ID_OFFSET
                    + self.LICENSE_ID_LENGTH],
            byteorder="little",
            signed=False,
        )
        id_type = IdType.from_flags(self._flags)
        if id_type is IdType.RANDOM:
            value_length = self.GUID_LENGTH
        elif id_type is IdType.RESERVED:
            value_length = len(payload) - self.HEADER_LENGTH
        else:
            value_length = self.HASH_LENGTH
        if len(payload) < self.HEADER_LENGTH + value_length:
            raise ValueError(
                "51Did payload for the {0} type must be at least {1} bytes; "
                "got {2}.".format(
                    id_type.name, self.HEADER_LENGTH + value_length,
                    len(payload)
                )
            )
        # bytes is immutable, so slicing yields a value that cannot be used to
        # mutate the underlying payload - no defensive copy is required.
        self._hash = bytes(
            payload[self.HASH_OFFSET:self.HASH_OFFSET + value_length])

    @classmethod
    def from_base64(cls, base64: str) -> "FodId":
        """Parses a 51Did from its base64-encoded OWID string in either
        alphabet.

        The cloud issues a 51Did in the standard alphabet with padding, and a
        page puts one in a link in the URL-safe alphabet (``-`` and ``_``)
        without padding. Both are accepted here, with or without padding,
        by normalising to the standard form before decoding, so a server
        never converts an identifier it received from a link.

        Raises :class:`TypeError` if ``base64`` is ``None``,
        :class:`ValueError` if the decoded envelope is too long, and
        :class:`owid.OwidError` if it is not valid base64 or not a valid OWID.
        """
        if base64 is None:
            raise TypeError("base64 must not be None")
        standard = cls.to_standard_base64(base64)
        maximum_base64_length = ((cls.MAXIMUM_BYTE_LENGTH + 2) // 3) * 4
        if len(standard) > maximum_base64_length:
            raise cls._too_long()
        return cls(Owid.from_base64(standard))

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
        """Parses a 51Did from the raw bytes of an OWID envelope.

        Raises :class:`TypeError` if ``buffer`` is ``None``,
        :class:`ValueError` if it exceeds :attr:`MAXIMUM_BYTE_LENGTH`, and
        :class:`owid.OwidError` if the bytes are not a valid OWID.
        """
        if buffer is None:
            raise TypeError("buffer must not be None")
        if len(buffer) > cls.MAXIMUM_BYTE_LENGTH:
            raise cls._too_long(len(buffer))
        return cls(Owid.from_byte_array(buffer))

    @classmethod
    def _too_long(cls, actual: int | None = None) -> ValueError:
        detail = "" if actual is None else "; got {0}".format(actual)
        return ValueError(
            "A 51Did must not exceed {0} bytes{1}.".format(
                cls.MAXIMUM_BYTE_LENGTH, detail
            )
        )

    @classmethod
    def _payload_too_long(cls, actual: int) -> ValueError:
        return ValueError(
            "A 51Did payload must not exceed {0} bytes; got {1}.".format(
                cls._MAXIMUM_PAYLOAD_LENGTH, actual
            )
        )

    def _has_valid_length(self) -> bool:
        """Internal defensive check used by :class:`DidClient`."""
        return len(self.payload) <= self._MAXIMUM_PAYLOAD_LENGTH \
            and len(self.signature) == 64 \
            and self._byte_length <= self.MAXIMUM_BYTE_LENGTH

    @classmethod
    def from_owid(cls, owid: Owid) -> "FodId":
        """Promotes an already-parsed OWID into a 51Did.

        The constructor **copies** the OWID (round-tripped through its byte
        form), not aliases it, so a ``FodId`` can never desync from its
        envelope if the caller later mutates the OWID it passed in. The
        supplied OWID must therefore be signed (serializable). Raises
        :class:`TypeError` if ``owid`` is ``None`` and :class:`ValueError` if
        its envelope is too long to be a 51Did.
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
    def hash(self) -> bytes:
        """The value bytes (a 32-byte SHA-256, or 16 GUID bytes for Random).

        This is the stable, comparable part of the envelope - use it as the
        cache / dedup key.
        """
        return self._hash

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
        """Verifies the OWID signature against the supplied public key. This is
        an explicit, separate step - construction never verifies.
        """
        return self._owid.verify_with_public_key(public_pem, [])
