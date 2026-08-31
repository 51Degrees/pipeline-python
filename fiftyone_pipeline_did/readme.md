# fiftyone_pipeline_did

Strongly typed Python reader and cloud client for the 51Did (51Degrees
Identifier) returned by the 51Degrees Cloud service. Mirrors the .NET
`FiftyOne.Did` package.

## Terminology

- The **51Did** (51Degrees Identifier) is the identifier as a whole.
- The **envelope** is the data model that carries it: a signed OWID holding
  the version, domain, date, payload and signature. It changes byte-for-byte
  every time the cloud issues one.
- The **match key** is the stable, comparable part of the payload after
  the Flags and License Id, being a 32-byte SHA-256 for Probabilistic and
  HashedEmail identifiers, or 16 GUID bytes for Random. Two 51Dids for the
  same inputs share the same match key even though their envelopes differ.

**Comparing two 51Dids means comparing their match keys, never their
envelopes.**

## Payload layout

| Offset | Length | Field      | Type                                            |
|-------:|-------:|------------|-------------------------------------------------|
|      0 |      1 | Flags      | uint8: bits 0-2 usage, bits 6-7 identifier type |
|      1 |      4 | LicenseId  | uint32 (little-endian)                          |
|      5 |  16/32 | Match key  | SHA-256 (Probabilistic, HashedEmail) or GUID (Random) |

| Bits 7-6 | `IdType`        | Match key length | Minimum payload |
|---------:|-----------------|-----------------:|----------------:|
|     `00` | `PROBABILISTIC` |           32 |              37 |
|     `01` | `RANDOM`        |           16 |              21 |
|     `10` | `HASHED_EMAIL`  |           32 |              37 |
|     `11` | `RESERVED`      |    remainder |               5 |

Identifiers issued before the type tag existed have bits 6-7 zeroed and decode
as `PROBABILISTIC`.

## OWID dependency

`FodId` builds on the OWID envelope library
([SWAN-community/owid-python](https://github.com/SWAN-community/owid-python),
package `owid`), consumed via the
[51Degrees/owid-python](https://github.com/51Degrees/owid-python) fork, which
is a git submodule of this repository and will move to upstream once that is
published. `Owid` is composed, not subclassed, so `FodId` holds an `Owid` and
delegates OWID-level concerns to it.

The published package does not take OWID from PyPI. The 51Degrees fork is not
published there, and the name `owid` on PyPI belongs to an unrelated project,
so a declared dependency would install the wrong thing. Instead
`ci/copy-owid-source.ps1` copies the fork's source into the package as the
private module `fiftyone_pipeline_did._owid` before the distribution is built,
carrying the Apache-2.0 licence and a notice naming the source commit with it.
The leading underscore keeps the top level name `owid` free on the consumer's
machine. The only third party requirement the package declares is
`cryptography`, which OWID uses for the signatures.

Nothing changes for a developer working in this repository, because the
submodule stays where it is and the same script puts the copy in place.
Run `pwsh ./setup.ps1` from the repository root, or
`git submodule update --init --recursive` followed by
`pwsh ./ci/copy-owid-source.ps1`, before building or running the tests. The
tests and examples import the fork under its own name, `owid`, which is how
they build signed envelopes to test against.

The OWID types the public API refers to are re-exported from the package
itself, so a caller never has to reach into the private module. Catch
`fiftyone_pipeline_did.OwidError` for an OWID level failure raised by the
raising readers, use `fiftyone_pipeline_did.Owid` for the envelope that
`FodId.from_owid` takes, and read `fiftyone_pipeline_did.SignatureStatus`
from `FodId.signature_status`. An `Owid` only ever comes from a successful
parse or from an OWID `Creator` that signs one into being, so there is no
way to hold an unsigned or partly built envelope.

## Usage

```python
from fiftyone_pipeline_did import FodId, IdType

fod_id = FodId.from_base64(base64_from_cloud_service)   # either alphabet

flags = fod_id.flags
type_ = fod_id.type          # IdType.PROBABILISTIC / RANDOM / HASHED_EMAIL
license_id = fod_id.license_id
match_key = fod_id.match_key  # SHA-256 or GUID bytes, see type

# Delegated OWID-level fields and operations.
domain = fod_id.domain
minutes = fod_id.date_minutes    # the date field: minutes since 2020-01-01Z
verified = fod_id.verify(public_key_pem)
base64 = fod_id.as_base64()      # standard alphabet, padded, as the cloud
url_safe = fod_id.as_base64_url()  # URL-safe alphabet, no padding, for a link
```

`from_base64` accepts the standard alphabet the cloud issues and the
URL-safe alphabet a page puts in a link, with or without padding. On an
identifier carrying a creator context the License Id field holds an
encrypted value that only 51Degrees can turn back into a licence
identifier, so `license_id` is the field's raw value and identifies
nothing outside 51Degrees.

`fod_id.hash` remains as a deprecated alias of `match_key`. Reading the
alias returns the same bytes and warns with `DeprecationWarning`, and the
alias will be removed in a future release, so move callers to `match_key`.

## Parsing without exceptions

An identifier arriving from outside, in a query string, a header or a
form field, may be anything at all, and failing to be a 51Did is an
ordinary outcome rather than a fault. `try_from_base64` and
`try_from_byte_array` read such input without raising and answer with a
`FodIdParseResult`, a small immutable tuple carrying three facts:

- `ok`, whether the parse succeeded;
- `value`, the `FodId` on success and `None` on failure, never a partly
  read identifier;
- `status`, a `FodIdParseStatus`, which is `PARSED` on success and the
  specific reason otherwise.

The result is truthy on success, so `if result:` reads naturally.

```python
from fiftyone_pipeline_did import FodId, FodIdParseStatus

result = FodId.try_from_base64(text_from_the_request)   # either alphabet
if result:
    fod_id = result.value
else:
    reason = result.status      # for example FodIdParseStatus.INVALID_BASE64
```

Parsing and verifying are separate steps. A successful parse says the
bytes have the shape of a 51Did and nothing about whether the signature
is genuine, so a parsed identifier is not known to be genuine until
`fod_id.verify(public_key_pem)`, `fod_id.signature_status(public_key_pem)`
or a `DidClient` check says so. `signature_status` answers in the OWID
`SignatureStatus` vocabulary, where only `SIGNATURE_VALID` and
`SIGNATURE_INVALID` are about the signature. `KEY_UNAVAILABLE`,
`INVALID_KEY` and `VERIFICATION_ERROR` say the question could not be
answered, which must never be read as a forgery, and the boolean `verify`
raises for a key it cannot use rather than answering `False` for the same
reason.

### Status meanings

The `FodIdParseStatus` vocabulary is the OWID one, member for member and
value for value, plus two members for the payload rules this package
applies once the envelope has been read. A failure inside the envelope is
carried through with the OWID status unchanged, so the reason reads the
same whichever language parsed the bytes.

| Status | Meaning |
| --- | --- |
| `PARSED` | A structurally valid 51Did. The signature has not been checked |
| `MISSING_INPUT` | `None`, an empty string or an empty buffer |
| `INVALID_INPUT_TYPE` | Not a string (base64 reader) or not a bytes-like object (byte reader) |
| `INVALID_BASE64` | The text is not base64 in either alphabet |
| `UNSUPPORTED_VERSION` | The first byte names an envelope version this package does not know |
| `UNEXPECTED_END` | The data stopped in the middle of an envelope field |
| `INVALID_DOMAIN_ENCODING` | The creator domain is not terminated or is longer than the OWID maximum |
| `BYTE_COUNT_MISMATCH` | The declared payload length disagrees with the bytes present |
| `IMPLEMENTATION_CAPACITY_EXCEEDED` | The envelope is consistent but larger than this runtime can hold, or dated past the end of the year 9999 where `datetime` stops. The four byte minute count runs to 15 February 10186, and the read answers with this status rather than raising on such a count |
| `ABSENT_NODE` | The version 0 marker, which stands for an absent envelope |
| `MALFORMED_ENVELOPE` | Malformed in a way none of the above describes |
| `PAYLOAD_TOO_SHORT` | The envelope was read but the payload is shorter than the 5 byte header, so the type cannot be read |
| `INVALID_TYPE_PAYLOAD_LENGTH` | The header names a type whose match key needs more bytes than the payload holds |

### Lower bounds and no upper bound

The payload must hold the 5 byte header before the type can be read, and
the type then says how many match key bytes must follow, being 16 for
`RANDOM` and 32 for `PROBABILISTIC` and `HASHED_EMAIL`, as the payload
layout table above shows. `RESERVED` keeps the best-effort reading, being
the header fields and whatever bytes follow. Anything beyond the match key
is a creator context section whose lengths belong to the cloud, so a
longer payload, a longer creator domain (a self-hosted container may sign
with one) or a longer envelope is accepted and this package places no
upper bound of its own on any of them. An older reader meeting a context
section of a version it does not know still reads the header and the
match key.

`DidClient` refuses text longer than 4096 characters before it parses
it, fetches a key or calls the cloud. That figure is client policy,
deliberately arbitrary and generous, and it is not a statement of how
long a 51Did can be. The parser answers such text with an ordinary
result, whilst the client raises its usual `ValueError`.

### Expected results and exceptions

Every `FodIdParseStatus` other than `PARSED` is an expected data result
from the `try_` readers and never an exception. The raising readers,
`from_base64`, `from_byte_array`, `from_owid` and the constructor, read
through the same logic and keep their documented exceptions for callers
who prefer them, being `TypeError` for `None` or a wrong input type,
`ValueError` for `PAYLOAD_TOO_SHORT` and `INVALID_TYPE_PAYLOAD_LENGTH`,
and `OwidError` for every other status, with the message naming the
status. Signature verification against a key that cannot be decoded, a
key list that cannot be fetched, and a cloud answer other than the one
asked for remain exceptions, because they are faults in the surroundings
and not properties of the identifier.

### Migrating from the removed OWID API

The OWID library no longer offers a throwing parse or a public
constructor, so an envelope cannot be assembled by hand, and code that
used those through this package changes as follows.

```python
# Before the hardening, external input was read by catching what the
# reader raised.
from fiftyone_pipeline_did import FodId, OwidError
try:
    fod_id = FodId.from_base64(text)
except (OwidError, ValueError):
    fod_id = None

# After the hardening, ask for the result and its reason.
from fiftyone_pipeline_did import FodId
result = FodId.try_from_base64(text)
fod_id = result.value if result else None

# Before the hardening, an envelope was built by hand and signed
# afterwards, as the tests and the offline example did.
owid = Owid(domain=domain, payload=payload)
creator.sign(owid)

# After the hardening, the creator signs a new envelope into being from
# the payload.
owid = creator.create(payload)
```

`from_base64`, `from_byte_array`, `from_owid` and the constructor keep
working and keep their exception types.

## Comparing two 51Dids

```python
a = FodId.from_base64(idprobglobal_a)
b = FodId.from_base64(idprobglobal_b)

# The envelope (date, signature, base64) differs across reissues.
# The match key inside the payload is stable, so compare match keys:
same_match_key = a.match_key == b.match_key
```

## Verifying on your server

`DidClient` handles every manipulation of a 51Did a server needs against
the cloud, so server code never builds a cloud URL or handles a key
itself. One instance serves a whole server, and its key cache is safe to
share across threads. It uses `urllib` and `json` from the standard
library, so this package gains no dependency the pipeline does not
already carry.

```python
import os
from fiftyone_pipeline_did import DidClient, FodId

client = DidClient(
    os.environ["_51DEGREES_RESOURCE_KEY"],
    os.environ.get("_51DEGREES_LICENSE_KEY"),   # optional, see below
    # endpoint defaults to FOD_CLOUD_API_URL, then the public cloud
)
```

| Argument | Meaning |
| --- | --- |
| `resource_key` | Required. The page's resource key, public by nature. It travels in the route of the key and verify requests and in the form body of the redeem request |
| `licence_key` | Optional. A licence key of the same account, server side only. Needed to redeem where the account holds licence keys. Sent only in the body of the redeem request, never in a URL |
| `endpoint` | Optional. The API base including the `/api/v4/` segment. Defaults to the `FOD_CLOUD_API_URL` environment variable, the same variable the cloud request engine honours, then to `https://cloud.51degrees.com/api/v4/`. A value without a trailing slash gains one |
| `transport` | Optional. The HTTP transport, either a callable taking the prepared `urllib.request.Request` and returning `(status, body_bytes)`, or an `urllib.request.OpenerDirector`. Defaults to `urllib.request.urlopen`. Tests inject one |
| `now` | Optional. The clock, returning an aware UTC `datetime`. Tests inject one |

Every request carries a `User-Agent` naming this package and its version.

**1. Parse.** The identifier arrives from a page in the URL-safe alphabet
and from the cloud in the standard one. `from_base64` takes either, with
or without padding, and `as_base64_url()` gives the form to put in a URL.
Input that may not be a 51Did at all is better read with
`try_from_base64`, which names the reason instead of raising (see
"Parsing without exceptions" above). Neither checks the signature.

```python
fod_id = FodId.from_base64(fifty_one_did)
```

**2. Verify the signature offline.** The client fetches the published
signing public keys from the cloud once, caches them for a day, and picks
the key in force when the identifier was created, being the entry whose
start is latest on or before the identifier's date (a key stays in force
until the next one starts, and keys are published up to three months
ahead). Near a period boundary the neighbouring key is tried as well. No
earlier key is ever tried. The envelope version must be the one the
cloud signs and the payload at least the base length for its type, and a
longer payload carries a creator context and is accepted, its exact
lengths being for the cloud to judge.

```python
valid = client.verify_signature(fod_id)            # bool
check = client.verify_signature_detailed(fod_id)   # SignatureCheck
# check.valid is False and check.reason is SignatureReason.NO_KEY when
# no published key covers the identifier's date
keys = client.public_keys()          # [PublicKeyEntry(starts_at, public_key)]
key = client.public_key_for(fod_id)  # the entry in force, or None
```

**3. Verify the signature through the cloud.** The open `verify`
endpoint, one use against the resource key and no licence key needed. The
identifier is sent under both the `51did` and `owid` query names, so the
call works with hosts that read either parameter. A string that does not
parse as a 51Did raises `DidArgumentError` (a `ValueError`) before any
request is made, with the message naming the `FodIdParseStatus`, and a
value the cloud itself refuses raises the same error carrying the cloud's
message and `status_code` 400.

```python
valid = client.verify(fod_id)   # bool
```

**4. Redeem a sealed creator context result.** The verify-context and
verify-full endpoints are browser calls, because the creator context
describes the browser's own connection, and they return the verdict only
as an encrypted `result` the browser cannot read or forge. The party that
acts on it redeems it on the server, with the licence key, against the
51Did it knows independently.

```python
redeemed = client.redeem(fod_id, result, challenge)
redeemed.context                  # ContextResult: VERIFIED, MISMATCH,
                                  #   NO_CONTEXT, NOT_CHECKABLE, EXPIRED,
                                  #   REPLAYED, UNREADABLE, UNCONFIRMED
redeemed.signature                # SignatureResult: VERIFIED, INVALID
                                  #   or UNKNOWN
redeemed.factors                  # only on a mismatch: name to
                                  #   FactorResult (VERIFIED or MISMATCH)
                                  #   or None where nothing was compared,
                                  #   for transport, device, browserip,
                                  #   connectionip, asn and browser
redeemed.verified_at              # datetime, on the redeemed and expired
                                  #   outcomes
redeemed.seconds_since_verified
redeemed.status_code              # 200, or 503 for UNCONFIRMED, which may
                                  #   be retried
redeemed.raw                      # the body as received
redeemed.to_dict()                # the cloud's own response shape, for
                                  #   relaying to a page
```

A context string this package does not know maps to `UNREADABLE`, so an
unrecognised outcome is never mistaken for a good one, and `context_raw`
keeps the string as sent. Every cryptographic failure comes back from the
cloud as the one word `unreadable` by design, a missing licence key
included, so the client does not try to tell them apart either. A string
that does not parse as a 51Did raises `DidArgumentError` before any
request is made, a cloud that refuses the 51Did raises the same error
with HTTP 400, a host
that does not offer the creator context raises `DidNotSupportedError`
(HTTP 404), and any other status raises `DidClientError` carrying
`status_code` and `body`. A transport failure raises the `OSError` the
transport raised, which is `urllib.error.URLError` by default.

## Examples

The `examples` folder holds an offline example and a web demo that
calls the 51Degrees cloud.

`fodid_example.py` builds a sample 51Did in process and parses it back
with this package, so it needs no resource key and makes no cloud calls.

`creator_context_web/` is a small demo web app, `server.py` serving
`page.html`, that runs the 51Did creator context flow the way
production does. The creator context only makes sense from a browser,
because a server verifying its own connection would be checking itself
against itself, so there is no console example.

1. **Create** a 51Did by calling the `json` endpoint, which issues an
   identifier for the calling connection. The browser makes this call.
2. **Verify** it with `verify-full`, which returns both the signature
   outcome and the creator context verdict only as an encrypted
   `result` that the caller cannot read or forge. (A deployment holding
   no context secret answers in the open instead.) The browser makes
   this call too, so the cloud observes the browser's live connection,
   then the page hands the encrypted result to its own server.
3. **Redeem** the encrypted result with `redeem`, presenting the 51Did,
   the encrypted result and the account's licence key, and receive the
   true creator context verdict, when the verification happened
   (`verifiedAt`) and how long ago that was (`secondsSinceVerified`).
   The server makes this call, as the only party holding the licence
   key.

A fresh challenge is issued per page load and bound through both steps
by the cloud. A production server would also remember the value it
issued and reject a redemption carrying any other, which the demo
keeps out of scope.

### The server-side step to copy into your own server

The one part that belongs on your server is the redeem call with the
licence key, which is what the `/redeem` handler in `server.py` does
with the `DidClient` from this package. It parses the identifier the
page sent, checks its signature offline against the published public
keys, then redeems the encrypted result with the challenge, adding the
licence key the browser never sees. The essential lines are these.

```python
from fiftyone_pipeline_did import DidClient, FodId

# Once, at start-up. RESOURCE, LICENCE and API come from the
# environment variables below.
client = DidClient(RESOURCE, LICENCE or None, API)

# In the /redeem handler, with 51did, result and challenge from the
# page. The identifier arrives in the URL-safe alphabet, which
# from_base64 accepts alongside the standard one.
fod_id = FodId.from_base64(query.get("51did", [""])[0])
signature_valid = client.verify_signature(fod_id)
redeemed = client.redeem(
    fod_id, query.get("result", [""])[0], query.get("challenge", [""])[0])
body = redeemed.to_dict()
body["serverSignature"] = "verified" if signature_valid else "invalid"
self.send_json(redeemed.status_code, body)
```

The handler answers the page with the cloud's status and a body in the
cloud's own shape (`signature`, `context`, `factors` when present,
`verifiedAt`, `secondsSinceVerified`) built from the typed result, plus
`serverSignature`, the server's own offline check of the identifier's
signature. The page ignores fields it does not know, so `page.html` is
the same for every language.

A verdict of `nocontext` is a normal outcome and not an error. A
self-hosted container may be configured not to emit the creator
context, so an identifier it issued has nothing to check and redeems
as `nocontext` with no factors, and the page shows it the way it shows
any verdict. A 404 from `verify-full` or `redeem` means the host
answering does not support the creator context at all, which is a
service without the feature rather than a failed check. The client
raises `DidNotSupportedError` for that case, the handler answers 404
with a text body, and the page shows "not supported by this host". Any
other answer the cloud gives is relayed with its status and body, so
the page reports whatever the service said readably, and an
unreachable cloud answers 502 with `{ "error": ... }`.

### Environment variables

| Variable | Meaning |
| --- | --- |
| `_51DEGREES_RESOURCE_KEY` | Required. The page's resource key, public by nature. The older `RESOURCE_KEY` is read when the aligned name is not set |
| `_51DEGREES_LICENSE_KEY` | Optional. A licence key of the same account, held server side only. Only an account that holds licence keys needs one to redeem, so an account holding none runs without it. The older `LICENSE_KEY` is read when the aligned name is not set |
| `FOD_CLOUD_API_URL` | Optional. The cloud API base including the `/api/v4/` segment, defaulting to `https://cloud.51degrees.com/api/v4/`. This is the same variable the cloud request engine honours. A host other than cloud.51degrees.com would be used to (a) use an on premise web server, or (b) use a privately hosted version of the 51Degrees cloud for performance reasons, which is the private hosting option of the cloud service. Both run the same service, so the demo works unchanged against either |
| `PORT` | The port to listen on, defaulting to `5100` |

### Running

With the resource key set as above:

```
cd fiftyone_pipeline_did/examples/creator_context_web
python server.py
```

then open `http://localhost:5100/`. To demonstrate across two devices,
serve on an address both can reach and open the copied link on the
second device.

### What a run costs

Every call the demo makes to the cloud is one use against the
subscription behind the resource key. Checking a 51Did from the browser
makes two, verify-full from the page and redeem from the server, so a
browser-based context check is two uses every time. Checking only the
signature with `verify` is one use.

### The copy-and-paste proof

Once the 51Did has fully validated, the page shows a **copy-and-paste
section** with a link carrying the same 51Did, and an explanation of
what will happen next. Open that link in a **different browser** and
the same page loads with the same identifier. The signature still
verifies and the identifier unpacks, because it is genuine, but the
creator context does **not** validate, because the context binds the
identifier to the browser and connection it was created on. That
visible failure is the demonstration that matters, a copied or stolen
identifier caught at presentation with nothing stored server side.
Opening the link in the same browser is not the demonstration, since
the same browser presents the same context and may still verify.

### The stylesheet

`examples-main.min.css` beside the demo is the design system build and
is refreshed by common-ci's `update-example-assets` step.

## Non-goals

- **No signature verification on parsing.** A parsed 51Did is not known to
  be genuine. Call `verify(public_key_pem)`, `signature_status(public_key_pem)`
  or a `DidClient` check when needed.
- **No upper bound on the size of an identifier.** The lengths beyond the
  header and match key belong to the cloud. The 4096 character figure in
  `DidClient` is client policy against obviously malformed text, not a
  format limit.
- **No creation of new 51Dids.** This is a parser; new 51Dids are issued by the
  51Degrees cloud / on-premise hashing engines.
