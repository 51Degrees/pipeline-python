# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2023 51 Degrees Mobile Experts Limited, Davidson House,
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


class CloudRequestException(Exception):
    """!
        Exception that can be thrown when the available data does not match that
        which is expected.
    """

    # TODO: remove/implement additional arguments, currently unused
    def __init__(self, message, httpStatusCode = 0, responseHeaders = {}):
        """!
            Constructor for CloudRequestException
            @type message: string
            @param message: Exception message string
            @type httpStatusCode: int
            @param httpStatusCode: the status code returned in the HTTP response
            @type responseHeaders: dict
            @param responseHeaders: the HTTP headers returned in the response
        """
        self.message = message
        self.httpStatusCode = httpStatusCode
        self.responseHeaders = responseHeaders
        super().__init__(self.message)