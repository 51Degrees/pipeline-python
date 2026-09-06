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

from enum import IntEnum
from typing import Optional


class Usage(IntEnum):
    """The usage a 51Did was created for, read from the identifier through
    :attr:`~fiftyone_pipeline_did.FodId.usage`. It decides where the
    identifier may go, because one created for :attr:`NON_MARKETING` must
    never be passed to a demand source, and one created for
    :attr:`STANDARD` or :attr:`PERSONALIZED` may be passed only to a
    recipient that has accepted the applicable terms.

    The three usages are cumulative rather than exclusive in the bits that
    carry them. Non-marketing sets the first, standard sets the first two,
    and personalized sets all three, so every marketing identifier also
    carries the non-marketing bit. A caller who masked for that bit alone
    would read every marketing identifier as non-marketing, which is the
    wrong way round for a data protection decision.
    :attr:`~fiftyone_pipeline_did.FodId.usage` answers with the highest
    usage granted, so that mistake cannot be made. The bits themselves are
    specified at
    https://github.com/51Degrees/specifications/blob/main/did-specification/identifier-layout.md

    The names match the cloud's ``id.usage`` values, ``non-marketing``,
    ``standard`` and ``personalized``, and are the same in every 51Did
    package."""

    #: No usage bit is set. The cloud never issues such an identifier, so
    #: this is an identifier from somewhere else or a damaged one, and it
    #: should be treated as though it may not be passed on.
    NONE = 0
    #: Created for use that is not marketing. Must not be passed to a
    #: demand source.
    NON_MARKETING = 1
    #: Created for standard marketing, being targeting unrelated to the
    #: person's browsing history or interactions.
    STANDARD = 2
    #: Created for personalized marketing, being targeting related to the
    #: person's browsing history or interactions.
    PERSONALIZED = 3

    @classmethod
    def from_flags(cls, flags: int) -> "Usage":
        """Decode the usage from bits 0-2 of a flags byte, as the highest
        usage granted."""
        if flags & 0b100:
            return cls.PERSONALIZED
        if flags & 0b010:
            return cls.STANDARD
        if flags & 0b001:
            return cls.NON_MARKETING
        return cls.NONE

    @property
    def id_usage(self) -> Optional[str]:
        """The cloud's ``id.usage`` value for this usage, or ``None`` for
        :attr:`NONE`."""
        return _ID_USAGE[self]


_ID_USAGE = {
    Usage.NONE: None,
    Usage.NON_MARKETING: "non-marketing",
    Usage.STANDARD: "standard",
    Usage.PERSONALIZED: "personalized",
}
