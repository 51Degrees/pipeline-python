# fiftyone_pipeline_did

Strongly typed Python reader and cloud client for the 51Did (51Degrees
Identifier) returned by the 51Degrees Cloud service. Mirrors the .NET
`FiftyOne.Did` package.

## Terminology

- The **51Did** (51Degrees Identifier) is the identifier as a whole.
- The **envelope** is the data model that carries it: a signed OWID holding
  the version, domain, date, payload and signature. It changes byte-for-byte
  every time the cloud issues one.
- The **value** is the stable, comparable part of the payload after the Flags
  and License Id: a 32-byte SHA-256 for Probabilistic and HashedEmail
  identifiers, or 16 GUID bytes for Random.

**Comparing two 51Dids means comparing their values, never their envelopes.**

## Payload layout

| Offset | Length | Field      | Type                                            |
|-------:|-------:|------------|-------------------------------------------------|
|      0 |      1 | Flags      | uint8: bits 0-2 usage, bits 6-7 identifier type |
|      1 |      4 | LicenseId  | uint32 (little-endian)                          |
|      5 |  16/32 | Value      | SHA-256 (Probabilistic, HashedEmail) or GUID (Random) |

| Bits 7-6 | `IdType`        | Value length | Minimum payload |
|---------:|-----------------|-------------:|----------------:|
|     `00` | `PROBABILISTIC` |           32 |              37 |
|     `01` | `RANDOM`        |           16 |              21 |
|     `10` | `HASHED_EMAIL`  |           32 |              37 |
|     `11` | `RESERVED`      |    remainder |               5 |

Identifiers issued before the type tag existed have bits 6-7 zeroed and decode
as `PROBABILISTIC`.

## OWID dependency

`FodId` builds on the OWID envelope library
([SWAN-community/owid-python](https://github.com/SWAN-community/owid-python),
package `owid`), consumed via the `51Degrees/owid-python` fork (git submodule;
switch to upstream once published). `Owid` is composed, not subclassed:
`FodId` holds an `Owid` and delegates OWID-level concerns to it.

## Usage

```python
from fiftyone_pipeline_did import FodId, IdType

fod_id = FodId.from_base64(base64_from_cloud_service)   # either alphabet

flags = fod_id.flags
type_ = fod_id.type          # IdType.PROBABILISTIC / RANDOM / HASHED_EMAIL
license_id = fod_id.license_id
value = fod_id.hash          # SHA-256 or GUID bytes, see type

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

## Comparing two 51Dids

```python
a = FodId.from_base64(idprobglobal_a)
b = FodId.from_base64(idprobglobal_b)

# The envelope (date, signature, base64) differs across reissues.
# The value inside the payload is stable - this is what you compare:
same_value = a.hash == b.hash
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

```python
fod_id = FodId.from_base64(fifty_one_did)
```

**2. Verify the signature offline.** The client fetches the published
signing public keys from the cloud once, caches them for a day, and picks
the key in force when the identifier was created, being the entry whose
start is latest on or before the identifier's date (a key stays in force
until the next one starts, and keys are published up to three months
ahead). Within fifteen minutes of a boundary the neighbouring key is
tried as well. No earlier key is ever tried, so a key leaked from one
period cannot sign an identifier dated in another. The envelope version
must be the one the cloud signs and the payload at least the base length
for its type.

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
call works against a cloud that has taken the creator context release and
one that has not. A value the cloud cannot parse as a 51Did raises
`DidArgumentError` (a `ValueError`) carrying the cloud's message.

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
included, so the client does not try to tell them apart either. A cloud
that cannot parse the 51Did raises `DidArgumentError` (HTTP 400), a host
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

- **No signature verification on construction.** Call `verify(public_key_pem)`
  when needed.
- **No creation of new 51Dids.** This is a parser; new 51Dids are issued by the
  51Degrees cloud / on-premise hashing engines.
