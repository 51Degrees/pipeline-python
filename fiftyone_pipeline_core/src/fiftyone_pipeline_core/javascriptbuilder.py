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


import json
import re
from pathlib import Path
try:
    #python2
    from urllib import urlencode
except ImportError:
    #python3
    from urllib.parse import urlencode

import chevron
from jsmin import jsmin

from .flowelement import FlowElement
from .evidence_keyfilter import EvidenceKeyFilter
from .elementdata_dictionary import ElementDataDictionary
from .constants import Constants


# Evidence keys the rendered script is not configured with. Both are
# appended to the script's own request by the script itself, so naming them
# here as well would send each twice and, worse, put the session id into the
# record the script keeps of a request's inputs. That record decides whether
# a later page view in the same tab can be served from the cached response,
# and a session id changes on every page view, so a record holding one could
# never match. The same two are excluded by the .NET builder, which is the
# reference for this behaviour.
EXCLUDED_PARAMETERS = ["query.session-id", "query.sequence"]

# The sequence the script is rendered with when the evidence holds no usable
# value.
DEFAULT_SEQUENCE = 1

# The largest sequence, which is the largest 32 bit signed integer.
MAX_SEQUENCE = 2 ** 31 - 1

# The most digits the largest sequence can have.
MAX_SEQUENCE_DIGITS = len(str(MAX_SEQUENCE))

# A whole number as text, with the digits on their own so nothing else
# has to be read as a number. The six ASCII space characters are named
# one by one rather than written as "\s", because "\s" also matches
# characters such as U+001C that int() then refuses, and a page can put
# any of them in the query string. A leading minus is refused here, so
# what is handed on is always digits this code can read.
SEQUENCE_PATTERN = re.compile(r"[ \t\n\r\f\v]*\+?([0-9]+)[ \t\n\r\f\v]*")

# A session id the script can be given. The session id is written into the
# script inside quotes without any escaping, so anything else could end the
# string early and break the script or change what it does.
SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}")


def parse_sequence(value):

    """!
    A sequence as a positive 32 bit integer.

    @type value: object
    @param value: The query.sequence evidence, or None
    @rtype: int
    @return: The sequence, or None when the value is not a whole number from
    1 to 2147483647. Any value at all can be passed, including one a page
    supplied, and none of them raises.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= MAX_SEQUENCE else None
    if not isinstance(value, str):
        return None
    match = SEQUENCE_PATTERN.fullmatch(value)
    if match is None:
        return None

    # The range is checked on the digits, because a very long run of
    # digits cannot be read as a number at all and raises instead of
    # answering. Every leading zero is dropped first, so no digits left
    # means zero, which is not a sequence.
    digits = match.group(1).lstrip("0")
    if (not digits
            or len(digits) > MAX_SEQUENCE_DIGITS
            or (len(digits) == MAX_SEQUENCE_DIGITS
                and digits > str(MAX_SEQUENCE))):
        return None
    return int(digits)


def get_sequence(value):

    """!
    The sequence to render into the script.

    The template writes the sequence as bare code (var sequence = ...;), so
    anything other than a whole number would stop the script parsing, or
    change what it does. A pipeline without a SequenceElement passes the
    query string's value, or nothing at all, straight through. As the
    pipeline specification says, a value that is not a positive 32 bit
    integer becomes 1.

    @type value: object
    @param value: The query.sequence evidence, or None
    @rtype: int
    @return: The sequence to render
    """

    sequence = parse_sequence(value)
    return DEFAULT_SEQUENCE if sequence is None else sequence


def get_session_id(value):

    """!
    The session id to render into the script.

    The template writes the session id inside quotes without any escaping.
    As the pipeline specification says, a session id that is not 1 to 64
    ASCII letters, digits and hyphens is rendered as an empty string, whether
    it came from the SequenceElement or from the query string.

    @type value: object
    @param value: The query.session-id evidence, or None
    @rtype: str
    @return: The session id to render, or an empty string
    """

    if isinstance(value, str) and SESSION_ID_PATTERN.fullmatch(value):
        return value
    return ""


class JavaScriptBuilderEvidenceKeyFilter(EvidenceKeyFilter):

    def filter(self, key):
        if "query" in key:
            return True

        if key == "header.host" or key == "header.protocol":
            return True
            
        return False


class JavascriptBuilderElement(FlowElement):

    """!
    The JavaScriptBuilder aggregates JavaScript properties
    from FlowElements in the Pipeline. This JavaScript also (when needed)
    generates a fetch request to retrieve additional properties
    populated with data from the client side
    It depends on the JSON Bundler element (both are automatically
    added to a Pipeline unless specifically removed) for its list of properties.
    The results of the JSON Bundler should also be used in a user-specified
    endpoint which retrieves the JSON from the client side.
    The JavaScriptBuilder is constructed with a url for this endpoint.

    """

    def __init__(self, settings = {} ):

        """!
        JavaScriptBuilder constructor.

        * @param {dict} options options object
        * @param {string} options.obj_name the name of the client
        * side object with the JavaScript properties in it ('fod' by default)
        * @param {string} options.protocol The protocol ("http" or "https")
        * used by the client side callback url.
        * This can be overriden with header.protocol evidence
        * @param {string} options.host The host of the client side
        * callback url. This can be overriden with header.host evidence.
        * @param {string} options.endpoint The endpoint of the client side
        * callback url
        * @param {boolean} options.enable_cookies Whether the client JavaScript
        * stored results of client side processing in cookies. This can also 
        * be set per request, using the "query.fod-js-enable-cookies" evidence key.
        * For more details on personal data policy,
        * see https://51degrees.com/terms/client-services-privacy-policy/?utm_source=code&utm_medium=comment&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_core-src-fiftyone_pipeline_core-javascriptbuilder.py&utm_term=init
        * @param {boolean} options.minify Whether to minify the JavaScript

        """

        super(JavascriptBuilderElement, self).__init__()
        
        self.settings = {}

        self.settings['_objName'] = settings["obj_name"] if "obj_name" in settings else 'fod'
        self.settings['_protocol'] = settings["protocol"] if "protocol" in settings else None
        self.settings['_host'] = settings["host"] if "host" in settings else None
        self.settings['_endpoint'] = settings["endpoint"] if "endpoint" in settings else ''
        self.settings['_enableCookies'] = settings["enable_cookies"] if "enable_cookies" in settings else True

        self.minify = settings["minify"] if "minify" in settings else True

        self.datakey = "javascriptbuilder"

        self.exclude_from_messages = True

        # Load template file contents into memory

        template = Path(__file__).absolute().parent / "js_templates" / "JavaScriptResource.mustache"
        if not template.is_file():
            raise FileNotFoundError(
                "JavaScriptResource.mustache not found in js_templates directory"
                " (have you initialised the submodule?)"
            )

        f = open(template, "r")
        self.template = f.read()
        f.close()

    
    def get_evidence_key_filter(self):

        """!
        
        The JavaScriptBuilder captures query string evidence and
        headers for detecting whether the request is http or https
    
        """
   
        return JavaScriptBuilderEvidenceKeyFilter()


    def process_internal(self, flowdata):

        """!
        The JavaScriptBundler collects client side javascript to serve.

        @type flowdata: FlowData
        @param flowdata: The FlowData

        """
    
        variables = {}

        for key, value in self.settings.items():
            variables[key] = value

        variables["_jsonObject"] = json.dumps(flowdata.jsonbundler.json)

        # Generate URL and autoUpdate params

        host = self.settings["_host"]
        protocol = self.settings["_protocol"]

        if not protocol:
            # Check if protocol is provided in evidence
            if flowdata.evidence.get("header.protocol"):
                protocol = flowdata.evidence.get("header.protocol")
            
        if not protocol:
            protocol = "https"

        if not host:
            # Check if host is provided in evidence

            if flowdata.evidence.get("header.host"):
                host = flowdata.evidence.get("header.host")

        variables["_host"] = host
        variables["_protocol"] = protocol

        enableCookiesVal = flowdata.evidence.get(Constants.EVIDENCE_ENABLE_COOKIES)
        if enableCookiesVal:
            variables["_enableCookies"] = enableCookiesVal.lower() == "true"

        variables["_enableCookies"]

        query_params = self.get_evidence_key_filter().filter_evidence(flowdata.evidence.get_all())
        # Both are written into the script, so each always has a safe value.
        # The session id is written inside quotes and is empty when absent or
        # not safe, and the sequence is written as bare code, so it is always
        # a positive number.
        variables["_sessionId"] = get_session_id(query_params.get("query.session-id"))
        variables["_sequence"] = get_sequence(query_params.get("query.sequence"))

        # The session id and the sequence are left out, because the script
        # appends both to its own request after it has taken the record of
        # that request's inputs. Putting them here as well would place the
        # session id, which is different on every page view, into that
        # record, so the record could never match the next page view's, the
        # cached response would be thrown away and the snippets would run
        # again on every page. A visitor moving through a site would pay a
        # request per page for the life of the tab.
        variables["_parameters"] = dict([
            (param.split(".")[1], query_params[param])
            for param in query_params.keys()
            if param.startswith("query.")
            and param not in EXCLUDED_PARAMETERS
        ])
        variables["_parameters"] = json.dumps(variables["_parameters"])

        if variables["_host"] and variables["_protocol"] and variables["_endpoint"]:

            variables["_url"] = variables["_protocol"] + "://" + variables["_host"] + variables["_endpoint"]

            # Add query parameters to the URL

            query = {}
 
            for param, paramvalue in query_params.items():

                paramkey = param.split(".")[1]

                query[paramkey] = paramvalue
  
            url_query = urlencode(query)
            
            # Does the URL already have a query string in it?
    
            if "?" not in variables["_url"]: 
                variables["_url"] += "?"
            else:
                variables["_url"] += "&"
            
            variables["_url"] += url_query

            variables["_updateEnabled"] = True
        else:
            variables["_updateEnabled"] = False
        

        # Use results from device detection if available to determine
        # if the browser supports promises.
        try:
            variables["_supportsPromises"] = (
                flowdata.device.promise
                and flowdata.device.promise.has_value()
                and bool(flowdata.device.promise.value())
            )
        except Exception:
            variables["_supportsPromises"] = False

        try:
            variables["_supportsFetch"] = (
                flowdata.device.fetch
                and flowdata.device.fetch.has_value()
                and bool(flowdata.device.fetch.value())
            )
        except Exception:
            variables["_supportsFetch"] = False
       
        # Check if any delayedproperties exist in the json
        variables["_hasDelayedProperties"] = True if "delayexecution" in variables["_jsonObject"] else False
         
        output = chevron.render(self.template, variables)
        
        if self.minify:
            # Minify the output
            output = jsmin(output)
        
        data = ElementDataDictionary(self, {"javascript": output})

        flowdata.set_element_data(data)

        return
