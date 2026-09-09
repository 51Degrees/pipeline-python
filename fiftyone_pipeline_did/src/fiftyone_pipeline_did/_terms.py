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


from enum import Enum
from typing import Optional


class Terms(Enum):
    """The terms document a 51Did was created under, read from the
    identifier through :attr:`~fiftyone_pipeline_did.FodId.terms`, so that
    the terms travel with the identifier instead of alongside it and a
    receiver can tell which document was in force when the identifier was
    made.

    The payload carries an index into a table of terms documents and not a
    version number, so that a later document can live at any address rather
    than only at one a number could be put into. That table is the whole of
    the definition, so a new terms document is a new index there and every
    package has to be released to know it, and an index is never reused or
    repointed once published. It is specified at
    https://github.com/51Degrees/specifications/blob/main/did-specification/identifier-layout.md

    :attr:`NOT_STATED` and :attr:`UNKNOWN` are different answers and must
    never be read as the same one. :attr:`NOT_STATED` says this identifier
    does not carry the answer, so the answer has to come from somewhere
    else, being the Terms Document Locator in an OpenRTB request or
    whatever the surrounding protocol provides, and it does not mean the
    identifier is unrestricted. :attr:`UNKNOWN` says the identifier does
    state its terms and that this package cannot name them, because the
    index was added after the package was released. A caller meeting
    :attr:`UNKNOWN` should treat the identifier as covered by terms it
    cannot yet read, and either update the package or refuse the
    identifier.

    The members carry a name and not the index, because :attr:`UNKNOWN`
    stands for any index this package does not know and so has no single
    index to carry.

    This module is private to the package, as its underscore name says. The
    package turns the index into the address that
    :attr:`~fiftyone_pipeline_did.FodId.terms` answers with, so a caller
    never handles the byte, and the names here are the ones the
    specification gives so that every package describes one document the
    same way.

    The Usage and the Terms answer different questions and a receiver needs
    both, because the Usage says where an identifier may go and the Terms
    says under which document it was created."""

    #: The terms are not stated in the identifier, which is index 0 and
    #: also what an identifier whose payload ends at the match key reads
    #: as. It names no document, so it has no address.
    NOT_STATED = (0, None)
    #: Index 1, the Model Terms for Marketing version 2, at
    #: https://m4ow.uk/mtm/2.txt
    MODEL_TERMS_FOR_MARKETING_2 = (1, "https://m4ow.uk/mtm/2.txt")
    #: An index added after this package was released, so the identifier
    #: states terms this package cannot name. Never treat it as
    #: :attr:`NOT_STATED`, which would read an identifier created under
    #: terms as one created under none.
    #: Its index is -1 rather than a real one. A Terms index read from a
    #: payload is one byte, so it is 0 to 255 and can never be negative,
    #: which is what makes -1 safe as the index that is not in the table.
    UNKNOWN = (-1, None)

    def __init__(self, index: int, url: Optional[str]) -> None:
        self._index = index
        self._url = url

    @classmethod
    def from_index(cls, index: int) -> "Terms":
        """The member for a Terms index, and :attr:`UNKNOWN` for an index
        this package does not know."""
        return _BY_INDEX.get(index, cls.UNKNOWN)

    @property
    def index(self) -> int:
        """The Terms index this member is carried as in a payload, and -1
        for :attr:`UNKNOWN`, which has none of its own."""
        return self._index

    @property
    def url(self) -> Optional[str]:
        """The address of the terms document, and ``None`` for
        :attr:`NOT_STATED` and for :attr:`UNKNOWN`, where there is no
        document this package can name.

        The address is answered and never fetched, because what to do with
        the document is the receiver's decision."""
        return self._url


#: The table above read by index. It is built from the members rather than
#: written out a second time, so a member and its index can never disagree,
#: and a new terms document is one new member above and nothing here. The
#: negative index of :attr:`Terms.UNKNOWN` is left out, because it stands
#: for every index the table does not carry.
_BY_INDEX = {
    terms.index: terms for terms in Terms if terms.index >= 0
}
