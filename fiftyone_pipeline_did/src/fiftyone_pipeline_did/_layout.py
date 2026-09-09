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

"""The byte layout of a 51Did payload, used inside this package only.

These offsets and lengths are not part of the package's public surface.
The only reason to hold an offset is to read a field by hand, and every
field has a typed accessor on
:class:`~fiftyone_pipeline_did.FodId` that reads it correctly, so a caller
who reaches for the bytes is taking the way that produces wrong answers.
The usage bits are the clearest case, being cumulative rather than
exclusive, so a mask for the non-marketing bit alone reads every marketing
identifier as non-marketing. Use :attr:`~fiftyone_pipeline_did.FodId.usage`
and the other accessors instead.

The layout itself is specified at
https://github.com/51Degrees/specifications/blob/main/did-specification/identifier-layout.md
and the surface every 51Did package offers is specified at
https://github.com/51Degrees/specifications/blob/main/did-specification/package-surface.md
which is where a change to either belongs first.

This module is imported by the package's own code and its own tests, which
build payloads byte by byte. It is not exported from the package's
``__init__``.
"""

#: Byte offset of the Flags field within the payload.
FLAGS_OFFSET = 0
#: Byte offset of the License Id field within the payload.
LICENSE_ID_OFFSET = 1
#: Byte length of the License Id field.
LICENSE_ID_LENGTH = 4
#: Byte offset of the match key field within the payload.
MATCH_KEY_OFFSET = 5
#: Byte length of the match key field (SHA-256).
MATCH_KEY_LENGTH = 32
#: Byte length of the header (Flags + License Id) common to every type.
HEADER_LENGTH = MATCH_KEY_OFFSET
#: Byte length of the GUID match key carried by Random identifiers.
GUID_LENGTH = 16
#: Minimum byte length of a Random 51Did payload.
RANDOM_PAYLOAD_LENGTH = HEADER_LENGTH + GUID_LENGTH
#: Minimum byte length of a Probabilistic or HashedEmail 51Did payload.
PAYLOAD_LENGTH = MATCH_KEY_OFFSET + MATCH_KEY_LENGTH
#: Byte length of the Terms field, which follows the match key. There is no
#: offset constant for it, because the identifier type fixes the match key
#: length and so the type says where the field starts.
TERMS_LENGTH = 1
#: The Terms index a payload with no byte after the match key reads as,
#: being the index that says the terms are not stated in the identifier.
#: Absence and zero mean the same thing and neither has to be told apart
#: from the other.
ABSENT_TERMS_INDEX = 0
