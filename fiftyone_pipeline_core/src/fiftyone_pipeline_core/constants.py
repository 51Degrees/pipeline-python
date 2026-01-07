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

class Constants():

    """!
    The string used to split evidence name parts
    """
    EVIDENCE_SEPARATOR = "."

    """!
    Used to prefix evidence that is obtained from HTTP headers 
    """
    EVIDENCE_HTTPHEADER_PREFIX = "header"

    """!
    Used to prefix evidence that is obtained from HTTP bookies 
    """
    EVIDENCE_COOKIE_PREFIX = "cookie"

    """!
    Used to prefix evidence that is obtained from an HTTP request"s
    query string or is passed into the pipeline for off-line 
    processing.
    """
    EVIDENCE_QUERY_PREFIX = "query"

    """!
    The suffix used when the JavaScriptBuilderElement
    "enable cookies" parameter is supplied as evidence.
    """
    EVIDENCE_ENABLE_COOKIES_SUFFIX = "fod-js-enable-cookies"

    """!
    The complete key to be used when the 
    JavaScriptBuilderElement "enable cookies" 
    parameter is supplied as part of the query 
    string.
    """
    EVIDENCE_ENABLE_COOKIES = EVIDENCE_QUERY_PREFIX + EVIDENCE_SEPARATOR + EVIDENCE_ENABLE_COOKIES_SUFFIX