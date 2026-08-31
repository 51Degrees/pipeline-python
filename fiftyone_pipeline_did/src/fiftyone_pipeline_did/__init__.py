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

"""Strongly typed reader and cloud client for the 51Did (51Degrees
Identifier) value.

:class:`~fiftyone_pipeline_did.fod_id.FodId` parses a 51Did from its base64
OWID form in either alphabet, exposes the three payload fields (Flags,
License Id and the match key) and the identifier
:class:`~fiftyone_pipeline_did.id_type.IdType`, and delegates OWID-level
concerns to the wrapped envelope. ``FodId.try_from_base64`` and
``FodId.try_from_byte_array`` read external data without raising and answer
with a :class:`~fiftyone_pipeline_did.fod_id.FodIdParseResult` naming the
:class:`~fiftyone_pipeline_did.fod_id.FodIdParseStatus` either way. Parsing
never checks the signature. Compare 51Dids by their match key
(``match_key``), never by their envelopes.

:class:`~fiftyone_pipeline_did.did_client.DidClient` handles every
manipulation of a 51Did a server needs against the 51Degrees cloud: the
signing public keys and the key in force when an identifier was created,
offline and cloud signature verification, and redeeming a sealed creator
context result with the licence key into a typed
:class:`~fiftyone_pipeline_did.did_client.RedeemResult`.
"""

from .did_client import (
    DEFAULT_ENDPOINT,
    ContextResult,
    DidArgumentError,
    DidClient,
    DidClientError,
    DidNotSupportedError,
    FactorResult,
    PublicKeyEntry,
    RedeemResult,
    SignatureCheck,
    SignatureReason,
    SignatureResult,
)
# The OWID library is carried inside this package as the private module
# _owid, because it cannot be installed from a package registry (see the
# package readme). The envelope type, the error type and the signature
# status vocabulary are re-exported here so that callers have supported
# names for the OWID types the public API refers to, as the private module
# itself is not part of that API.
from ._owid import Owid, OwidError, SignatureStatus
from .fod_id import DATE_EPOCH, FodId, FodIdParseResult, FodIdParseStatus
from .id_type import IdType

__all__ = [
    "FodId",
    "FodIdParseResult",
    "FodIdParseStatus",
    "IdType",
    "DATE_EPOCH",
    "DidClient",
    "RedeemResult",
    "PublicKeyEntry",
    "SignatureCheck",
    "ContextResult",
    "SignatureResult",
    "FactorResult",
    "SignatureReason",
    "DidClientError",
    "DidArgumentError",
    "DidNotSupportedError",
    "DEFAULT_ENDPOINT",
    "Owid",
    "OwidError",
    "SignatureStatus",
]
