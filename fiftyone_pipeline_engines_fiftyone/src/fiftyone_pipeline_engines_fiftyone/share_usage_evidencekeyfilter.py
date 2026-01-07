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

from fiftyone_pipeline_core.basiclist_evidence_keyfilter import BasicListEvidenceKeyFilter

class ShareUsageEvidenceKeyFilter(BasicListEvidenceKeyFilter):
    """
    The ShareUsageEvidenceKeyFilter filters out all evidence 
    not needed by the 51Degrees ShareUsage service.
    It allows for a specific whitelist of query strings,
    a blacklist of headers and a specific cookie used for 
    session information
    """

    def __init__(self, cookie = None, query_whitelist = [], header_blacklist = []):
        """!
        Constructor for ShareUsageEvidenceKeyFilter
        @type cookie: string
        @param cookie: which cookie is used to track evidence
        @type query_whitelist: list
        @param query_whitelist: list of query string whitelist evidence to keep
        @type query_blacklist: list
        @param query_blacklist: list of header evidence to exclude
        @type 
        @param
        """
        self.query_whitelist = query_whitelist

        self.header_blacklist = header_blacklist

        self.cookie = cookie

        if cookie is None and \
            (query_whitelist is None or len(query_whitelist) == 0) and \
            (header_blacklist is None or len(header_blacklist) == 0):
            self.share_all = True
        else:
            self.share_all = False

    
    def filter_evidence_key(self, key):

        """!
        Check if a specific key should be filtered.

        @type key: string
        @param key: to check in the filter

        @rtype: bool
        @return: Is this key in the filter's keys list?

        """
        #  get prefix and key of evidence
        key_parts = key.lower().split(".")

        prefix = key_parts[0]
        suffix = key_parts[1]

        result = self.share_all

        if not self.share_all:
            if prefix == "header":
                # Add the header to the list if the header name does not
                # appear in the list of blocked headers
                result = suffix not in self.header_blacklist
            elif prefix == "cookie":
                # Only add cookies that start with the 51Degrees cookie
                # prefix
                result = suffix.startswith("51d_") or \
                    (self.include_session and suffix == self.cookie)
            elif prefix == "session":
                # Only session values that start with the 51Degrees 
                # cookie prefix
                result = suffix.startswith("51d_")
            elif prefix == "query":
                # If no query string parameter filter was specified 
                # then share all of them.
                # Otherwise, only include query string parameters that 
                # start with 51d_ or that have been specified in 
                # the constructor.
                result = self.query_whitelist is None or \
                    len(self.query_whitelist) == 0 or \
                    suffix.startswith("51d_") or \
                    suffix in self.query_whitelist
            else:
                # Add anything that is not a cookie, header, session
                # variable or query parameter
                result = True

        return result
            