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

## Non-goals

- **No signature verification on construction.** Call `verify(public_key_pem)`
  when needed.
- **No creation of new 51Dids.** This is a parser; new 51Dids are issued by the
  51Degrees cloud / on-premise hashing engines.
