# fiftyone_pipeline_did

Strongly typed Python reader for the 51Did (51Degrees Identifier) returned by
the 51Degrees Cloud service. Mirrors the .NET `FiftyOne.Did` package.

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

fod_id = FodId.from_base64(base64_from_cloud_service)

flags = fod_id.flags
type_ = fod_id.type          # IdType.PROBABILISTIC / RANDOM / HASHED_EMAIL
license_id = fod_id.license_id
value = fod_id.hash          # SHA-256 or GUID bytes, see type

# Delegated OWID-level fields and operations.
domain = fod_id.domain
verified = fod_id.verify(public_key_pem)
base64 = fod_id.as_base64()
```

## Comparing two 51Dids

```python
a = FodId.from_base64(idprobglobal_a)
b = FodId.from_base64(idprobglobal_b)

# The envelope (date, signature, base64) differs across reissues.
# The value inside the payload is stable - this is what you compare:
same_value = a.hash == b.hash
```

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
licence key, which is what the `/redeem` handler in `server.py` does.
It takes the identifier, the encrypted result and the challenge from
the page, adds the licence key the browser never sees, and relays the
cloud's answer as received. The essential lines are these.

```python
params = urllib.parse.urlencode({
    "51did": query.get("51did", [""])[0],
    "result": query.get("result", [""])[0],
    "challenge": query.get("challenge", [""])[0],
    "license": LICENCE,
})
url = f"{API}id/redeem/{RESOURCE}?{params}"
request = urllib.request.Request(
    url, headers={"User-Agent": "51did-demo-python"})
with urllib.request.urlopen(request) as response:
    status = response.status
    body = response.read()
```

`API` is the cloud API base, `RESOURCE` the resource key and `LICENCE`
the licence key, all read from the environment variables below. The
answer is JSON carrying `signature`, `context`, `verifiedAt` and
`secondsSinceVerified`.

A verdict of `nocontext` is a normal outcome and not an error. A
self-hosted container may be configured not to emit the creator
context, so an identifier it issued has nothing to check and redeems
as `nocontext` with no factors, and the page shows it the way it shows
any verdict. A 404 from `verify-full` or `redeem` means the host
answering does not support the creator context at all, which is a
service without the feature rather than a failed check, and the page
shows "not supported by this host". The web server's `/redeem` relays
the cloud's status, content type and body exactly as received, so the
page reports whatever the service said readably.

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
