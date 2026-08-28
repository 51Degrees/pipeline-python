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

"""The 51Did cloud client.

:class:`DidClient` handles every manipulation of a 51Did a server needs
against the 51Degrees cloud, so server code never builds a cloud URL or
handles a key itself. It fetches the signing public keys once and caches
them, picks the key in force when an identifier was created, verifies a
signature offline against that key, verifies a signature through the
cloud's verify endpoint, and redeems a sealed creator context result with
the licence key, returning a typed :class:`RedeemResult`.

Creating a 51Did is not part of this client. Creation is the cloud ``json``
endpoint through the cloud request engine and pipeline, and a page creates
from the browser because the identifier describes the browser's own
connection. The verify-context and verify-full endpoints are browser calls
for the same reason and are not offered here.

Standard library only (``urllib`` and ``json``), so this package gains no
dependency the pipeline does not already carry.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from owid import Version

from .fod_id import DATE_EPOCH, FodId
from .id_type import IdType

#: The public cloud API base, used when neither the ``endpoint`` argument
#: nor the ``FOD_CLOUD_API_URL`` environment variable is set.
DEFAULT_ENDPOINT = "https://cloud.51degrees.com/api/v4/"

#: The environment variable the cloud request engine reads for the API
#: base, honoured here when no endpoint argument is given.
ENDPOINT_VARIABLE = "FOD_CLOUD_API_URL"

#: How far either side of a key boundary a neighbouring key is also tried,
#: matching the tolerance the cloud applies. A creation time is recorded to
#: the minute and stamped a moment after the key was chosen, so an
#: identifier dated a few minutes past a boundary may carry the previous
#: key's signature, and one dated a few minutes before it may carry the
#: next.
BOUNDARY_TOLERANCE = timedelta(minutes=15)

#: A cached key list older than this is fetched again before use.
KEY_LIST_MAX_AGE = timedelta(days=1)

#: The only envelope version the cloud signs and verifies.
SUPPORTED_VERSION = Version.VERSION3

#: Seconds to wait for the cloud before the default transport gives up.
DEFAULT_TIMEOUT = 30.0


def _package_version() -> str:
    """The installed version of this package, for the User-Agent, or
    ``unknown`` when it is imported from a checkout that is not
    installed."""
    try:
        from importlib.metadata import version
        return version("fiftyone_pipeline_did")
    except Exception:
        return "unknown"


#: Sent with every request so the cloud can tell which package called.
USER_AGENT = "fiftyone_pipeline_did/" + _package_version()


class ContextResult(str, Enum):
    """The creator context outcome of a redemption, as the cloud reports it
    in the ``context`` field. The values are the cloud's own strings, so a
    result can be compared to a member or printed as received."""

    #: Every factor matched the browser and connection that created it.
    VERIFIED = "verified"
    #: At least one factor differed. ``factors`` says which.
    MISMATCH = "mismatch"
    #: The identifier carries no creator context.
    NO_CONTEXT = "nocontext"
    #: The service holds no secret covering the identifier's date.
    NOT_CHECKABLE = "notcheckable"
    #: The sealed result was redeemed outside the freshness window.
    EXPIRED = "expired"
    #: The sealed result had already been redeemed on that instance.
    REPLAYED = "replayed"
    #: The sealed result could not be read. Every cryptographic failure, a
    #: missing licence key included, comes back as this one word by design,
    #: and a context string this package does not know is mapped here too.
    UNREADABLE = "unreadable"
    #: First use could not be confirmed (HTTP 503). The caller may retry.
    UNCONFIRMED = "unconfirmed"


class SignatureResult(str, Enum):
    """The signature outcome of a redemption, as the cloud reports it in the
    ``signature`` field of a redeemed result. Absent on every other
    outcome."""

    VERIFIED = "verified"
    INVALID = "invalid"
    #: The cloud did not report the signature, as on an expired result.
    UNKNOWN = "unknown"


class FactorResult(str, Enum):
    """The outcome of one factor in a mismatch. The cloud reports ``null``
    for a factor that was not compared, which is passed through as
    ``None``."""

    VERIFIED = "verified"
    MISMATCH = "mismatch"


class SignatureReason(str, Enum):
    """The reason a :meth:`DidClient.verify_signature_detailed` answer was
    given."""

    #: A candidate key verified the signature.
    VERIFIED = "verified"
    #: The envelope version is not the one the cloud signs.
    VERSION = "version"
    #: The payload is shorter than the base length for its type.
    LENGTH = "length"
    #: No published key covers the identifier's date.
    NO_KEY = "nokey"
    #: Every candidate key was tried and none verified the signature.
    SIGNATURE = "signature"


class DidClientError(Exception):
    """An answer from the cloud that was not the one asked for. Carries the
    HTTP status and the response body so a caller can relay or log what the
    cloud said."""

    def __init__(self, message: str, status_code: Optional[int] = None,
                 body: Optional[str] = None) -> None:
        super().__init__(message)
        #: The HTTP status, where there was one.
        self.status_code = status_code
        #: The response body, where there was one.
        self.body = body


class DidArgumentError(DidClientError, ValueError):
    """The cloud refused the request because the 51Did sent was not a valid
    identifier (HTTP 400 with an ``errors`` list). The message carries the
    cloud's own text. Also a :class:`ValueError`, the language's argument
    error."""


class DidNotSupportedError(DidClientError):
    """The host answering does not offer the creator context (HTTP 404 from
    the redeem endpoint). A caller can name this case rather than treat it
    as a failed check."""


@dataclass(frozen=True)
class PublicKeyEntry:
    """A published signing key and the moment it came into force. A key
    stays in force until the next key starts."""

    #: When the key came, or comes, into force, as an aware UTC datetime.
    starts_at: datetime
    #: The key in SPKI PEM form.
    public_key: str


@dataclass(frozen=True)
class SignatureCheck:
    """The detailed answer to an offline signature check."""

    #: Whether a candidate key verified the signature.
    valid: bool
    #: Why the answer was given.
    reason: SignatureReason


#: The type of a factor value in :attr:`RedeemResult.factors`.
FactorValue = Optional[FactorResult]

#: The shape of an injected transport: a callable taking the prepared
#: :class:`urllib.request.Request` and returning the HTTP status and the
#: response body, whatever the status. An object with an ``open`` method
#: (an :class:`urllib.request.OpenerDirector`) is accepted as well.
Transport = Callable[[urllib.request.Request], Tuple[int, bytes]]

_ISO_8601 = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?"
    r"(Z|[+-]\d{2}:?\d{2})?$")


def parse_iso8601(text: str) -> datetime:
    """Parses an ISO 8601 date and time as the cloud writes one, with any
    number of fractional second digits and ``Z`` or an offset, into an
    aware UTC datetime. Raises :class:`ValueError` for anything else.

    Written here rather than through :meth:`datetime.fromisoformat`,
    because on Python 3.9 and 3.10 that method takes neither ``Z`` nor the
    seven fractional digits the cloud emits.
    """
    match = _ISO_8601.match(text.strip())
    if match is None:
        raise ValueError("not an ISO 8601 date and time: {0!r}".format(text))
    year, month, day, hour, minute, second, fraction, zone = match.groups()
    microsecond = int((fraction or "0")[:6].ljust(6, "0"))
    value = datetime(int(year), int(month), int(day), int(hour),
                     int(minute), int(second), microsecond,
                     tzinfo=timezone.utc)
    if zone and zone != "Z":
        sign = 1 if zone[0] == "+" else -1
        digits = zone[1:].replace(":", "")
        offset = timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
        value = value - sign * offset
    return value


def _try_parse_json(text: str) -> Any:
    """Parses JSON without raising, answering ``None`` for text that is not
    JSON."""
    try:
        return json.loads(text)
    except ValueError:
        return None


class RedeemResult:
    """The typed answer to a redemption. Built from the cloud's JSON body,
    with the raw status and body kept for logging."""

    def __init__(self, status_code: int, raw: str,
                 parsed: Dict[str, Any]) -> None:
        #: The HTTP status the cloud answered with, 200 or 503.
        self.status_code = status_code
        #: The response body exactly as received.
        self.raw = raw
        context = parsed.get("context")
        context = context if isinstance(context, str) else ""
        #: The ``context`` string exactly as the cloud sent it, kept so an
        #: outcome this package does not know is still visible.
        self.context_raw = context
        #: One of :class:`ContextResult`. A string this package does not
        #: know maps to :attr:`ContextResult.UNREADABLE`, so an
        #: unrecognised outcome is never mistaken for a good one.
        self.context = _context_of(context)
        signature = parsed.get("signature")
        #: One of :class:`SignatureResult`.
        self.signature = (
            SignatureResult.VERIFIED if signature == "verified"
            else SignatureResult.INVALID if signature == "invalid"
            else SignatureResult.UNKNOWN)
        factors = parsed.get("factors")
        #: Factor name to :class:`FactorResult` (or ``None`` where nothing
        #: was compared), present only when the cloud sent ``factors``,
        #: which is the mismatch outcome. The names are ``transport``,
        #: ``device``, ``browserip``, ``connectionip``, ``asn`` and
        #: ``browser``.
        self.factors: Optional[Dict[str, FactorValue]] = (
            {str(name): _factor_of(value) for name, value in factors.items()}
            if isinstance(factors, dict) else None)
        verified_at = parsed.get("verifiedAt")
        #: When the verify endpoint checked the context and sealed the
        #: result, present on the redeemed and expired outcomes.
        self.verified_at: Optional[datetime] = None
        if isinstance(verified_at, str):
            try:
                self.verified_at = parse_iso8601(verified_at)
            except ValueError:
                self.verified_at = None
        seconds = parsed.get("secondsSinceVerified")
        #: Whole seconds between the sealing and this redemption by the
        #: cloud's clock, present on the redeemed and expired outcomes.
        self.seconds_since_verified: Optional[int] = (
            int(seconds)
            if isinstance(seconds, (int, float))
            and not isinstance(seconds, bool) else None)

    @classmethod
    def from_response(cls, status_code: int, raw: str) -> "RedeemResult":
        """Builds a result from a redeem response body, raising
        :class:`DidClientError` when the body is not a JSON object."""
        parsed = _try_parse_json(raw)
        if not isinstance(parsed, dict):
            raise DidClientError(
                "Redeem answered HTTP {0} with a body that is not a JSON "
                "object: {1}".format(status_code, raw), status_code, raw)
        return cls(status_code, raw, parsed)

    def to_dict(self) -> Dict[str, Any]:
        """The result in the cloud's own response shape (``signature``,
        ``context``, ``factors`` when present, ``verifiedAt``,
        ``secondsSinceVerified``), so a server can answer a page with it
        directly. ``signature`` is left out when the cloud did not report
        it, as the cloud leaves it out."""
        body: Dict[str, Any] = {}
        if self.signature is not SignatureResult.UNKNOWN:
            body["signature"] = self.signature.value
        body["context"] = self.context.value
        if self.factors is not None:
            body["factors"] = {
                name: (value.value if value is not None else None)
                for name, value in self.factors.items()}
        if self.verified_at is not None:
            # ISO 8601 UTC to the second, as the cloud writes it.
            body["verifiedAt"] = self.verified_at.astimezone(
                timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if self.seconds_since_verified is not None:
            body["secondsSinceVerified"] = self.seconds_since_verified
        return body

    def __repr__(self) -> str:
        return "RedeemResult(status_code={0}, context={1!r})".format(
            self.status_code, self.context_raw)


def _context_of(text: str) -> ContextResult:
    try:
        return ContextResult(text)
    except ValueError:
        return ContextResult.UNREADABLE


def _factor_of(value: Any) -> FactorValue:
    if value == "verified":
        return FactorResult.VERIFIED
    if value == "mismatch":
        return FactorResult.MISMATCH
    return None


class DidClient:
    """Everything a server does with a 51Did against the 51Degrees cloud.

    The public key list is cached per instance with the time it was
    fetched, behind a lock, so one instance can serve a whole server across
    threads.

    :param resource_key: the page's resource key. Required. Public by
        nature, it travels in the route of the key and verify requests and
        in the form body of the redeem request.
    :param licence_key: a licence key of the same account. Server side
        only. Needed to redeem where the account holds licence keys, and
        sent only in the body of the redeem request, never in a URL.
    :param endpoint: the API base including the ``/api/v4/`` segment.
        Defaults to the ``FOD_CLOUD_API_URL`` environment variable, then to
        the public cloud. A value without a trailing slash gains one.
    :param transport: the HTTP transport, either a callable taking the
        prepared :class:`urllib.request.Request` and returning
        ``(status, body_bytes)``, or an
        :class:`urllib.request.OpenerDirector`. Defaults to
        :func:`urllib.request.urlopen`. Tests inject one.
    :param now: the clock, returning an aware UTC datetime. Defaults to
        :meth:`datetime.now` in UTC. Tests inject one.
    :param timeout: seconds the default transport waits for the cloud.
    """

    def __init__(self, resource_key: str, licence_key: Optional[str] = None,
                 endpoint: Optional[str] = None,
                 transport: Optional[Any] = None,
                 now: Optional[Callable[[], datetime]] = None,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        if not isinstance(resource_key, str) or resource_key == "":
            raise ValueError("resource_key is required")
        self._resource_key = resource_key
        self._licence_key = licence_key if licence_key else None
        base = endpoint or os.environ.get(ENDPOINT_VARIABLE) or \
            DEFAULT_ENDPOINT
        # Normalised to end in exactly one slash so every URL is the base
        # plus a relative path, as the cloud request engine treats the same
        # value.
        self._endpoint = base.rstrip("/") + "/"
        self._transport = transport
        self._timeout = timeout
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._keys: Optional[List[PublicKeyEntry]] = None
        self._fetched_at: Optional[datetime] = None
        self._fetch_count = 0

    @property
    def endpoint(self) -> str:
        """The API base every request is built on."""
        return self._endpoint

    @property
    def resource_key(self) -> str:
        """The resource key the requests carry."""
        return self._resource_key

    # ----- Public keys and key selection -----

    def public_keys(self) -> List[PublicKeyEntry]:
        """The published signing keys, oldest first, fetched on first use
        and then served from the cache until the list is a day old. Keys are
        published up to three months ahead of their start, so the list
        holds entries that have not started yet."""
        with self._lock:
            return list(self._public_keys_locked())

    def public_key_for(self, fod_id: Union[FodId, str]) \
            -> Optional[PublicKeyEntry]:
        """The key in force when the identifier was created, being the
        entry whose start is latest on or before the identifier's date. The
        list is fetched again, once, before answering when no entry covers
        the date, when the date is later than the newest start held, or
        when the list is more than a day old. Answers ``None`` when the
        date precedes every published key."""
        date = _date_of(_as_fod_id(fod_id))
        return _in_force_at(self._keys_for(date), date)

    # ----- Offline signature verification -----

    def verify_signature(self, fod_id: Union[FodId, str]) -> bool:
        """Verifies the identifier's signature offline against the
        published keys, as the cloud's own verify endpoint does. The
        envelope version must be the one the cloud signs, the payload must
        be at least the base length for its type (a longer payload carries
        a creator context and is accepted), and the signature must verify
        against the key in force at the identifier's date or, within
        fifteen minutes of a boundary, the neighbouring key. No earlier key
        is ever tried, so a key leaked from one period cannot sign an
        identifier dated in another."""
        return self.verify_signature_detailed(fod_id).valid

    def verify_signature_detailed(self, fod_id: Union[FodId, str]) \
            -> SignatureCheck:
        """As :meth:`verify_signature`, with the reason alongside the
        answer, so a caller can tell an identifier no key covers from one
        whose signature failed."""
        identifier = _as_fod_id(fod_id)
        if identifier.version != SUPPORTED_VERSION:
            return SignatureCheck(False, SignatureReason.VERSION)
        if not _payload_length_valid(identifier):
            return SignatureCheck(False, SignatureReason.LENGTH)
        date = _date_of(identifier)
        candidates = _candidates_for_date(self._keys_for(date), date)
        if not candidates:
            return SignatureCheck(False, SignatureReason.NO_KEY)
        for key in candidates:
            if identifier.verify(key.public_key):
                return SignatureCheck(True, SignatureReason.VERIFIED)
        return SignatureCheck(False, SignatureReason.SIGNATURE)

    # ----- Cloud signature verification -----

    def verify(self, fod_id: Union[FodId, str]) -> bool:
        """Verifies the identifier's signature through the cloud's verify
        endpoint, the open endpoint that needs no licence key. One use
        against the resource key.

        Raises :class:`DidArgumentError` (also a :class:`ValueError`) when
        the cloud could not parse the value as a 51Did, with the cloud's
        message, and :class:`DidClientError` on any answer other than valid
        or invalid. A transport failure raises the :class:`OSError` the
        transport raised (:class:`urllib.error.URLError` by default)."""
        text = _identifier_text(fod_id)
        # The identifier travels under both names. The creator context
        # release names the parameter 51did and keeps owid as an alias,
        # while a cloud that has not taken that release reads owid only
        # and answers 400 to a request carrying 51did alone.
        encoded = urllib.parse.quote(text, safe="")
        url = "{0}id/verify/{1}?51did={2}&owid={2}".format(
            self._endpoint, urllib.parse.quote(self._resource_key, safe=""),
            encoded)
        status, body = self._send(urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}, method="GET"))
        parsed = _try_parse_json(body)
        if isinstance(parsed, dict):
            valid = parsed.get("valid")
            if isinstance(valid, bool):
                return valid
            errors = parsed.get("errors")
            if status == 400 and isinstance(errors, list):
                raise DidArgumentError(
                    " ".join(str(e) for e in errors), status, body)
        raise DidClientError(
            "Verify answered HTTP {0}: {1}".format(status, body), status,
            body)

    # ----- Redeem -----

    def redeem(self, fod_id: Union[FodId, str], result: str,
               challenge: Optional[str] = None) -> RedeemResult:
        """Redeems a sealed creator context result against the identifier,
        on the server, with the licence key.

        The resource key, the 51Did, the sealed result, the challenge and
        the licence key all travel in the body of a POST to ``id/redeem``,
        so none of them reaches an access log. (The redeem endpoint takes
        the resource key in the form on a POST, where the key and verify
        endpoints take it in the route on a GET.) One use against the
        resource key, the second of the two a browser context check costs.

        A 200 and a 503 both produce a result, the 503 being the
        ``unconfirmed`` outcome the caller may retry. Every cryptographic
        failure comes back as the one word ``unreadable`` by design, so the
        client does not try to tell them apart either.

        :param fod_id: the identifier the caller knows independently, or
            its base64 in either alphabet.
        :param result: the sealed result exactly as the verify endpoint
            returned it to the page.
        :param challenge: the single-use challenge given to the verify
            endpoint, where one was.
        :raises DidArgumentError: when the cloud could not parse the value
            as a 51Did (HTTP 400), with the cloud's message.
        :raises DidNotSupportedError: when the host does not offer the
            creator context (HTTP 404).
        :raises DidClientError: on any other status.
        :raises OSError: when the transport failed to reach the cloud
            (:class:`urllib.error.URLError` by default).
        """
        text = _identifier_text(fod_id)
        form = [
            ("resource", self._resource_key),
            ("51did", text),
            ("result", result if isinstance(result, str) else ""),
            ("challenge", challenge if isinstance(challenge, str) else ""),
        ]
        if self._licence_key is not None:
            form.append(("license", self._licence_key))
        url = self._endpoint + "id/redeem"
        status, body = self._send(urllib.request.Request(
            url,
            data=urllib.parse.urlencode(form).encode("ascii"),
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST"))
        if status in (200, 503):
            return RedeemResult.from_response(status, body)
        if status == 400:
            parsed = _try_parse_json(body)
            errors = parsed.get("errors") if isinstance(parsed, dict) \
                else None
            message = " ".join(str(e) for e in errors) \
                if isinstance(errors, list) else body
            raise DidArgumentError(message, status, body)
        if status == 404:
            raise DidNotSupportedError(
                "The host does not offer the creator context: " + body,
                status, body)
        raise DidClientError(
            "Redeem answered HTTP {0}: {1}".format(status, body), status,
            body)

    # ----- Internals -----

    def _send(self, request: urllib.request.Request) -> Tuple[int, str]:
        """Sends the request through the transport and answers the status
        and the body as text, whatever the status. A non-2xx answer is an
        answer, not an exception, so each caller can read what the cloud
        said. Only a failure to reach the cloud raises, as the
        :class:`OSError` the transport raised."""
        transport = self._transport
        if transport is None:
            status, body = _urlopen(
                lambda: urllib.request.urlopen(request,
                                               timeout=self._timeout))
        elif hasattr(transport, "open"):
            status, body = _urlopen(
                lambda: transport.open(request, timeout=self._timeout))
        else:
            status, body = transport(request)
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return int(status), body

    def _public_keys_locked(self) -> List[PublicKeyEntry]:
        if self._keys is None or self._stale():
            return self._refresh_locked()
        return self._keys

    def _keys_for(self, date: datetime) -> List[PublicKeyEntry]:
        """The key list to select from for the given date, fetched again
        once where the rule in :meth:`public_key_for` calls for it and the
        list was not just fetched."""
        with self._lock:
            fetched_before = self._fetch_count
            keys = self._public_keys_locked()
            if self._fetch_count == fetched_before \
                    and self._needs_refetch(keys, date):
                keys = self._refresh_locked()
            return keys

    def _needs_refetch(self, keys: List[PublicKeyEntry],
                       date: datetime) -> bool:
        if _in_force_at(keys, date) is None:
            return True
        if keys and date > keys[-1].starts_at:
            return True
        return self._stale()

    def _stale(self) -> bool:
        return self._fetched_at is None \
            or self._now() - self._fetched_at > KEY_LIST_MAX_AGE

    def _refresh_locked(self) -> List[PublicKeyEntry]:
        keys = self._fetch_keys()
        self._keys = keys
        self._fetched_at = self._now()
        self._fetch_count += 1
        return keys

    def _fetch_keys(self) -> List[PublicKeyEntry]:
        """GET ``id/key/{resource}`` and read each entry's start and public
        key. ``startsAt`` is read where present and ``created`` otherwise,
        because the endpoint as deployed before the creator context release
        emits ``created`` and ``publicKey`` only. ``weekStart`` is
        ignored."""
        url = "{0}id/key/{1}".format(
            self._endpoint, urllib.parse.quote(self._resource_key, safe=""))
        status, body = self._send(urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}, method="GET"))
        if status != 200:
            raise DidClientError(
                "Public keys answered HTTP {0}: {1}".format(status, body),
                status, body)
        parsed = _try_parse_json(body)
        if not isinstance(parsed, list):
            raise DidClientError(
                "Public keys answered with a body that is not a JSON "
                "array: " + body, status, body)
        keys = []
        for entry in parsed:
            start = None
            public_key = None
            if isinstance(entry, dict):
                start = entry.get("startsAt") or entry.get("created")
                public_key = entry.get("publicKey")
            starts_at = None
            if isinstance(start, str):
                try:
                    starts_at = parse_iso8601(start)
                except ValueError:
                    starts_at = None
            if starts_at is None or not isinstance(public_key, str):
                raise DidClientError(
                    "Public keys entry lacks a start or a publicKey: "
                    + json.dumps(entry), status, body)
            keys.append(PublicKeyEntry(starts_at, public_key))
        keys.sort(key=lambda key: key.starts_at)
        return keys


def _urlopen(open_call: Callable[[], Any]) -> Tuple[int, bytes]:
    """Runs a urllib open and answers the status and body whatever the
    status, since urllib raises for anything outside 2xx and the error is
    itself the response. A failure to reach the host propagates as the
    :class:`urllib.error.URLError` (an :class:`OSError`) it raised."""
    try:
        with open_call() as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        body = error.read()
        error.close()
        return error.code, body


def _as_fod_id(value: Union[FodId, str]) -> FodId:
    """The identifier as a FodId, parsing a base64 string where one was
    given."""
    if isinstance(value, FodId):
        return value
    if isinstance(value, str):
        return FodId.from_base64(value)
    raise TypeError("fod_id must be a FodId or a base64 string")


def _identifier_text(value: Union[FodId, str]) -> str:
    """The text sent to the cloud for an identifier. A parsed identifier
    goes in the URL-safe alphabet, which needs no further encoding, and a
    string goes as given so the cloud can report its own parse error."""
    if isinstance(value, FodId):
        return value.as_base64_url()
    if isinstance(value, str) and value != "":
        return value
    raise TypeError("fod_id must be a FodId or a non-empty base64 string")


def _date_of(fod_id: FodId) -> datetime:
    """The identifier's creation moment, from the minutes the envelope
    carries, as an aware UTC datetime."""
    return DATE_EPOCH + timedelta(minutes=fod_id.date_minutes)


def _payload_length_valid(fod_id: FodId) -> bool:
    """Whether the payload is at least the base length for its type, being
    five header bytes plus a 32 byte match key, or 16 for a Random
    identifier. Anything beyond the base is a creator context section,
    whose exact lengths belong to the cloud, so any longer payload is
    accepted here."""
    value_length = FodId.GUID_LENGTH if fod_id.type is IdType.RANDOM \
        else FodId.HASH_LENGTH
    return len(fod_id.payload) >= FodId.HEADER_LENGTH + value_length


def _in_force_at(keys: List[PublicKeyEntry],
                 at: datetime) -> Optional[PublicKeyEntry]:
    """The entry in force at the moment, being the newest whose start has
    passed, or ``None`` when the moment precedes every entry."""
    best = None
    for key in keys:
        if key.starts_at > at:
            continue
        if best is None or key.starts_at > best.starts_at:
            best = key
    return best


def _candidates_for_date(keys: List[PublicKeyEntry],
                         at: datetime) -> List[PublicKeyEntry]:
    """The entries that may have signed something created at the moment,
    best first: the entry in force, then the entry in force a tolerance
    earlier and the entry in force a tolerance later where those differ.
    Deliberately not every earlier entry."""
    candidates: List[PublicKeyEntry] = []

    def add(entry: Optional[PublicKeyEntry]) -> None:
        if entry is not None and all(c is not entry for c in candidates):
            candidates.append(entry)

    add(_in_force_at(keys, at))
    add(_in_force_at(keys, at - BOUNDARY_TOLERANCE))
    add(_in_force_at(keys, at + BOUNDARY_TOLERANCE))
    return candidates
