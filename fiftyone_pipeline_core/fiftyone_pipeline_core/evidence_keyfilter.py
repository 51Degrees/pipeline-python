# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2019 51 Degrees Mobile Experts Limited, 5 Charlotte Close,
# Caversham, Reading, Berkshire, United Kingdom RG4 7BY.
#
# This Original Work is licensed under the European Union Public Licence (EUPL)
# v.1.2 and is subject to its terms as set out below.
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
# ********************************************************************


class EvidenceKeyFilter:
    """
    An EvidenceKeyFilter is attached to a FlowElement and is used to check
    if a specific evidence key is needed by it. This allows for keys that are
    not used by any FLowElement in a pipeline to be discarded, and on a FlowElement
    level allows for caching of data / memoization based on the evidence a FlowElement
    requires.

    """

    def filterEvidence(self, evidenceKeyObject):
        """
        Filter evidence from a dictionary of evidence keys/values.
        Runs filterEvidenceKey on each key in the dictionary

        @type evidenceKeyObject: dict
        @param evidenceKeyObject: Evidence dictionary contents

        @rtype: dict
        @return: EReturns filtered evidence dictionary contents
        """

        filtered = {}

        for key, value in evidenceKeyObject.items():

            if self.filterEvidenceKey(key):

                filtered[key] = value

        return filtered

    def filterEvidenceKey(self, key):
        """
        See if a property key should be in the filtered evidence

        @type key: string
        @param key: property name

        @rtype: bool
        @return: Returns is this be filtered out or not?

        """

        return True