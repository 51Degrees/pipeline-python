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

from __future__ import absolute_import

import json
import os
import warnings
from functools import cached_property
from json import JSONDecodeError

import requests
from fiftyone_pipeline_core.basiclist_evidence_keyfilter import BasicListEvidenceKeyFilter
from fiftyone_pipeline_engines.engine import Engine
from fiftyone_pipeline_engines.aspectdata_dictionary import AspectDataDictionary

from .requestclient import RequestClient
from .cloudrequestexception import CloudRequestException
from .constants import Constants

try:
    #python2
    from urllib import urlencode
except ImportError:
    #python3
    from urllib.parse import urlencode


# Engine that makes a call to the 51Degrees cloud service
# Returns raw JSON as a "cloud" property under "cloud" datakey
class CloudRequestEngine(Engine):
    def __init__(self, settings = {}):
        """!
        Constructor for CloudRequestEngine
        
        @type settings: dict
        @param settings: Settings should contain a resource_key or a
        license_key, and optionally
        1) requested_properties, the fully qualified names of the
        properties to ask for, as a list or a comma separated string.
        Required with a license_key alone and refused with a resource_key,
        because the cloud service ignores the list whenever a resource key
        is present
        2) a cloud_endpoint to overwrite the default baseurl
        3) an cloud_request_origin to use when making requests

        See the Credentials section of the cloud request engine
        specification for the combinations that are accepted:
        https://github.com/51Degrees/specifications/blob/main/pipeline-specification/pipeline-elements/cloud-request-engine.md#credentials

        """

        super(CloudRequestEngine, self).__init__()

        self.datakey = "cloud"

        self.properties = {
            "cloud" : {
                "type": "string",
                "description": "raw JSON from the cloud service"
            }
        }

        # A credential read from an environment variable often arrives with
        # a trailing newline, and a value that is only whitespace is a
        # mistake rather than a key, so each one is trimmed and an empty
        # one counts as absent.
        self.resource_key = self.setting_text(settings, "resource_key")
        self.license_key = self.setting_text(settings, "license_key")

        # The names of the properties to ask for, each as "section.property"
        # in the case the cloud service uses, so comparison with its answer
        # is exact. The list is read on every request, so a caller may add
        # to it after the engine is built with add_requested_properties,
        # for example once the accessible properties say which client-side
        # properties the key carries.
        self.requested_properties = self.setting_names(
            settings, "requested_properties")

        self.check_credentials()

        # The sets of requested properties already reported as not covered
        # by the key, so the report is made once rather than on every
        # request. See report_properties_not_covered.
        self.reported_not_covered = set()

        # The endpoint is the cloud_endpoint setting, then the
        # FOD_CLOUD_API_URL environment variable, then
        # cloud.51degrees.com. A host other than cloud.51degrees.com
        # would be used to (a) use an on premise web server, or (b) use
        # a privately hosted version of the 51Degrees cloud for
        # performance reasons. That is the private hosting option of
        # the cloud service, and both run the same service, so callers
        # work unchanged against either.
        if "cloud_endpoint" in settings:
            self.baseURL = settings["cloud_endpoint"]
        else:
            self.baseURL = os.environ.get(Constants.FOD_CLOUD_API_URL)
            if self.baseURL is None or (self.baseURL is not None and self.baseURL == ""):
                self.baseURL = Constants.BASE_URL_DEFAULT

        # Make sure if baseURL does not end with '/', one will be appended
        if not self.baseURL.endswith("/"):
            self.baseURL = self.baseURL + "/"
  
        if "http_client" in settings:
            self.http_client = settings["http_client"]
        else:
            self.http_client = RequestClient()

        if "cloud_request_origin" in settings:
            self.cloud_request_origin = settings["cloud_request_origin"]
        else:
            self.cloud_request_origin = None

        self.exclude_from_messages = True

    @staticmethod
    def setting_text(settings, name):

        """!
        A setting as trimmed text, or an empty string when it is missing,
        None or only whitespace.
        """

        value = settings.get(name)
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def setting_names(settings, name):

        """!
        A setting holding property names, as a list of trimmed, non-empty,
        lower-cased names. The setting may be a list of names or one comma
        separated string, and a missing setting gives an empty list.

        The names are lower-cased because the cloud service lower-cases
        property names in its answer, so "Device.IsMobile" comes back as
        "ismobile" under "device".
        """

        value = settings.get(name)
        if value is None:
            return []
        if isinstance(value, str):
            value = value.split(",")
        names = []
        for entry in value:
            entry = str(entry).strip().lower()
            if entry != "":
                names.append(entry)
        return names

    def add_requested_properties(self, names):

        """!
        Add to the properties each request asks for, after the engine is
        built. The names are trimmed and lower-cased as the constructor
        does, so a name given in the case the documentation uses still
        matches the answer, and the credential rules are checked again,
        because a list only has meaning on a licence key alone and the
        constructor's check cannot see a list added later.

        @type names: list or string
        @param names: the names to add, as a list or one comma separated
        string, each as "section.property"
        """

        self.requested_properties.extend(
            self.setting_names({"names": names}, "names"))
        self.check_credentials()

    def check_credentials(self):

        """!
        Refuse a combination of resource key, licence key and requested
        properties that the cloud service would refuse on every request, so
        a deployment sees one configuration error when the engine is built
        rather than a failure on every request it serves.
        """

        has_resource_key = self.resource_key != ""
        has_license_key = self.license_key != ""
        has_requested_properties = len(self.requested_properties) > 0

        if has_resource_key == False and has_license_key == False:
            raise ValueError(Constants.MESSAGE_NO_CREDENTIAL)

        if has_resource_key == False and has_requested_properties == False:
            raise ValueError(Constants.MESSAGE_LICENSE_KEY_NEEDS_PROPERTIES)

        if has_resource_key == True and has_requested_properties == True:
            raise ValueError(
                Constants.MESSAGE_PROPERTIES_IGNORED_WITH_RESOURCE_KEY)

    def get_credentials(self):

        """!
        The credentials to send with a request, as the keys the cloud
        service reads them from. A key that is not set is left out.

        @rtype: dict
        @return: Returns the credentials to send
        """

        credentials = {}
        if self.resource_key != "":
            credentials[Constants.RESOURCE_PARAMETER] = self.resource_key
        if self.license_key != "":
            credentials[Constants.LICENSE_PARAMETER] = self.license_key
        return credentials

    @cached_property
    def flow_element_properties(self):
        # Initialise evidence keys and properties from the cloud service
        return self.get_engine_properties()

    @cached_property
    def evidence_keys(self):
        return self.get_evidence_keys()

    def get_evidence_keys(self):
        """!
        Internal function for getting evidence keys used by cloud engines
        @rtype: dict
        @return: Returns list of keys
        """
    
        evidenceKeyRequest = self.make_cloud_request('GET', self.baseURL + "evidencekeys")

        evidenceKeys = json.loads(evidenceKeyRequest)

        return evidenceKeys

    def get_evidence_key_filter(self):
        """!
        Instance of EvidenceKeyFilter based on the evidence keys fetched
        from the cloud service by the private getEvidenceKeys() method
        
        @type: BasicListEvidenceKeyFilter
        @return: Returns BasicListEvidenceKeyFilter

        """

        return BasicListEvidenceKeyFilter(self.evidence_keys)

    def get_engine_properties(self):
        """!
        Internal method to get properties for cloud engines from the cloud service
    
        @rtype: dict
        @return: Returns properties for all engines
        """

        # Get properties for all engines. A resource key alone goes in the
        # query string as it always has. A licence key identifies an
        # account, so it is posted in the body instead, where it stays out
        # of request logs. The cloud service reads both keys from either
        # place, answers a licence key alone with everything the licence
        # entitles, and widens a resource key's answer by the products a
        # licence key sent beside it grants.

        propertiesURL = self.baseURL + "accessibleProperties"

        if self.license_key == "":
            properties = self.make_cloud_request(
                'GET',
                propertiesURL + "?" + Constants.RESOURCE_PARAMETER + "="
                + self.resource_key)
        else:
            properties = self.make_cloud_request(
                'POST', propertiesURL, self.get_credentials())

        properties = json.loads(properties)

        flowElementProperties = {}

        # Change indexes to be by name
        for datakey, elementProperties in properties["Products"].items():

            flowElementProperties[datakey] = {}

            engine_properties = elementProperties["Properties"]

            for engineProperty in engine_properties:

                # Lowercase keys

                engineProperty =  {k.lower(): v for k, v in engineProperty.items()}

                flowElementProperties[datakey][engineProperty["name"]] = engineProperty
               
        return flowElementProperties

    def validate_response(
        self,
        cloud_response: requests.Response,
        check_for_error_messages=True,
    ):
        """!
        Validate the JSON response from the cloud service.
    
        @type: Response
        @param: Response returned from the cloud service.
        @rtype: Exception
        @return: Thrown if there are errors returned from the cloud service.
        """

        has_data = cloud_response.text and cloud_response.text.strip()
        messages = []

        if has_data and check_for_error_messages:
            try:
                json_response = cloud_response.json()
            except (JSONDecodeError, requests.exceptions.JSONDecodeError):
                raise CloudRequestException(
                    f'Cloud request engine properties list request returned code "{cloud_response.status_code}"'
                    f' with non-JSON content "{cloud_response.text}"'
                )
            except Exception as e:
                raise CloudRequestException(
                    f'Cloud request engine properties list request returned code "{cloud_response.status_code}"'
                    f' with content "{cloud_response.text}".\nError: "{type(e).__name__}: {e}"'
                )

            has_errors = "errors" in json_response and len(json_response["errors"])
            has_data = len(json_response) > (1 if has_errors else 0)

            if has_errors:
                messages.append(json.dumps(json_response["errors"]))

        # If there were no errors but there was also no other data
        # in the response then add an explanation to the list of
        # messages.
        if not messages and not has_data:
            message = Constants.MESSAGE_NO_DATA_IN_RESPONSE.format(cloud_response.url)
            messages.append(message)

        # If there were no errors returned but the response code was non
        # success then throw an exception.
        if not messages and cloud_response.status_code != 200:
            message = Constants.MESSAGE_ERROR_CODE_RETURNED.format(
                self.baseURL,
                cloud_response.status_code,
                cloud_response.json(),
            )
            messages.append(message)

        if not messages:
            return

        # If there are any errors returned from the cloud service
        # then throw an exception
        exception_message = (
            f"{Constants.EXCEPTION_CLOUD_ERRORS_MULTIPLE} {messages}" if len(messages) > 1
            else Constants.EXCEPTION_CLOUD_ERROR.format(messages[0])
        )

        raise CloudRequestException(
            exception_message,
            cloud_response.status_code,
            cloud_response.headers,
        )

    def make_cloud_request(self, type, url, content = None):

        """!    
        @type url: string
        @param url
        
        @rtype: dict
        @return Returns dict with data and error properties error contains any errors from the request, data contains the response
        """

        cloudResponse = self.http_client.request(type, url, content, self.cloud_request_origin)
 
        self.validate_response(cloudResponse)

        return cloudResponse.text           

    def process_internal(self, flowdata):

        """!
        Processing function for the CloudRequestEngine
        Makes a request to the cloud service with the supplied resource key
        and evidence and returns a JSON object that is then parsed by cloud engines
        placed later in the pipeline
        
        @type FlowData: FlowData
        @param FlowData: Returns a JSON object that is then parsed by cloud engines

        """
   
        # A resource key names the route, as it always has. A licence key
        # alone has no resource key to put there, so it uses the data
        # endpoint that takes none and travels in the body with the list
        # of properties wanted.
        if self.resource_key != "":
            url = self.baseURL + self.resource_key + ".json?"
        else:
            url = self.baseURL + Constants.LICENSE_DATA_PATH

        content = self.get_content(flowdata)
        content.update(self.get_credentials())
        if len(self.requested_properties) > 0:
            content[Constants.VALUES_PARAMETER] = ",".join(
                self.requested_properties)

        result = self.make_cloud_request('POST', url, content)

        if len(self.requested_properties) > 0:
            self.report_properties_not_covered(result)

        data = AspectDataDictionary(self, {"cloud" : result})

        flowdata.set_element_data(data)

        return

    def report_properties_not_covered(self, result):

        """!
        Compare the properties a request asked for with the ones its answer
        carries, and warn once about any it left out.

        The cloud service drops a property the licence key does not cover
        without naming it, whenever the request also asked for a property
        the key does cover, so the engine has to notice the difference
        itself. A property that is present but null counts as answered,
        because it carries a nullreason beside it saying why it has no
        value on this request, which is a different matter from
        entitlement. The answer cannot change while the key and the list
        stay the same, so each distinct list is reported once.

        @type result: string
        @param result: the JSON text the cloud service answered with
        """

        requested = frozenset(self.requested_properties)
        if requested in self.reported_not_covered:
            return

        try:
            answer = json.loads(result)
        except JSONDecodeError:
            # validate_response has already dealt with an answer that is
            # not JSON, so there is nothing to compare here.
            return

        not_covered = []
        for name in sorted(requested):
            section, _, property_name = name.partition(
                Constants.EVIDENCE_SEPERATOR)
            section_values = answer.get(section)
            if (isinstance(section_values, dict) == False
                    or property_name not in section_values):
                not_covered.append(name)

        self.reported_not_covered.add(requested)

        if len(not_covered) > 0:
            warnings.warn(
                Constants.MESSAGE_PROPERTIES_NOT_COVERED.format(
                    ", ".join(not_covered)))

    def get_content(self, flowData):

        """!
        Generate the Content to send in the POST request. The evidence keys
        e.g. 'query.' and 'header.' have an order of precedence. These are
        added to the evidence in reverse order, if there is conflict then 
        the queryData value is overwritten. 

        'query.' evidence should take precedence over all other evidence.
        If there are evidence keys other than 'query.' that conflict then
        this is unexpected so a warning will be logged.

        @param: flowData: FlowData
        @return: Evidence Dictionary
        """

        queryData = {}

        evidence = flowData.evidence.get_all()
        # Add evidence in reverse alphabetical order, excluding special keys. 
        self.add_query_data(queryData, evidence, self.get_selected_evidence(evidence, Constants.EVIDENCE_OTHER))
        # Add cookie evidence.
        self.add_query_data(queryData, evidence, self.get_selected_evidence(evidence, Constants.EVIDENCE_COOKIE_PREFIX))
        # Add header evidence.
        self.add_query_data(queryData, evidence, self.get_selected_evidence(evidence, Constants.EVIDENCE_HTTPHEADER_PREFIX))
        # Add query evidence.
        self.add_query_data(queryData, evidence, self.get_selected_evidence(evidence, Constants.EVIDENCE_QUERY_PREFIX))
        return queryData

    def add_query_data(self, query_data, all_evidence, evidence):

        """!
        Add query data to the evidence.

        @param: query_data: The destination dictionary to add query data to.
        @param all_evidence: All evidence in the flow data. This is used to report which evidence
        keys are conflicting.
        @param evidence: Evidence to add to the query Data.
        """        

        for evidenceKey, evidenceValue in evidence.items():

            # Get the key parts
            evidenceKeyParts = evidenceKey.split(Constants.EVIDENCE_SEPERATOR)
            prefix = evidenceKeyParts[0].lower()
            suffix = evidenceKeyParts[-1].lower()

            # The service reads its credentials and the list of requested
            # properties from these names, so evidence carrying one of them
            # would sit beside the engine's own values with no way to know
            # which one the service applied. Leave such evidence out, and
            # say so as the conflict case below does, so a caller who set
            # it expecting an effect can see why there was none. The value
            # is not logged, as it may be a credential.
            if suffix in Constants.RESERVED_EVIDENCE_SUFFIXES:
                warnings.warn(
                    Constants.WARNING_RESERVED_EVIDENCE.format(evidenceKey))
                continue

            # Check and add the evidence to the query parameters.
            if (not suffix in query_data.keys()):
                query_data[suffix] = evidenceValue
            # If the queryParameter exists already.
            else:
                # Get the conflicting pieces of evidence and then log a 
                # warning, if the evidence prefix is not query. Otherwise a
                # warning is not needed as query evidence is expected 
                # to overwrite any existing evidence with the same suffix.
                if (prefix.lower() != Constants.EVIDENCE_QUERY_PREFIX):
                    conflicts = {}
                    for key, value in all_evidence.items(): 
                        if(key.lower() != evidenceKey.lower() and suffix in key.lower()):
                            conflicts[key] = value

                    warningMessage = Constants.WARNING_MESSAGE \
                                        .format(evidenceKey, evidenceValue) 
                        
                    conflictStr = ', '.join('{}:{}'.format(key, value) \
                                for key, value in conflicts.items())
                    
                    if conflictStr:
                        warnings.warn(warningMessage + conflictStr)
                    
                # Overwrite the existing queryParameter value.
                query_data[suffix] = evidenceValue

    def get_selected_evidence(self, evidence, type):
        
        """!
        Get evidence with specified prefix.

        @param evidence: All evidence in the flow data.
        @param type: Required evidence key prefix
        """

        selected_evidence = {}

        if type == Constants.EVIDENCE_OTHER:
            for key, value in evidence.items():
                if (not self.key_has_prefix(key, Constants.EVIDENCE_QUERY_PREFIX) and \
                        not self.key_has_prefix(key, Constants.EVIDENCE_HTTPHEADER_PREFIX) and \
                            not self.key_has_prefix(key, Constants.EVIDENCE_COOKIE_PREFIX)):
                    selected_evidence[key] = value
            selected_evidence = dict(sorted(selected_evidence.items(), reverse=True))
            
        else:
            for key, value in evidence.items():
                if self.key_has_prefix(key, type):
                    selected_evidence[key] = value
            
        return selected_evidence
        
    def key_has_prefix(self, itemKey, prefix):

        """!
        Check that the key of a KeyValuePair has the given prefix.

        @param itemKey: Key to check
        @param prefix: The prefix to check for.
        @return: True if the key has the prefix.
        """

        key = itemKey.split(Constants.EVIDENCE_SEPERATOR)
        return key[0].lower() == prefix.lower()
