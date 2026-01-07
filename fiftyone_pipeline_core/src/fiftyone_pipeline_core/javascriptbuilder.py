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
        * see http://51degrees.com/terms/client-services-privacy-policy/
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
        variables["_sessionId"] = query_params["query.session-id"] if "query.session-id" in query_params else None
        variables["_sequence"] = query_params["query.sequence"] if "query.sequence" in query_params else None

        variables["_parameters"] = dict([
            (param.split(".")[1], query_params[param])
            for param in query_params.keys()
            if param.startswith("query.")
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
