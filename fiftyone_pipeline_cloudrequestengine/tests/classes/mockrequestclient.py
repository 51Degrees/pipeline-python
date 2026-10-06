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
from unittest.mock import Mock

from requests import Response
from fiftyone_pipeline_cloudrequestengine.requestclient import RequestClient

from .constants import Constants


class MockRequestClient(RequestClient):
    def __init__(self, **kwargs):
        self.server_unavailable = kwargs.get("server_unavailable", False)
        # The JSON text answered to a data request made with a licence key
        # alone, which goes to the "json" route rather than a resource key
        # route, so a test can shape the answer it checks against.
        self.license_json_response = kwargs.get(
            "license_json_response", Constants.jsonResponse)
        # Every request made, as (type, url, content) tuples, so a test can
        # check where each credential travelled.
        self.requests = []

    def request(self, type, url, content, originHeader):
        self.requests.append((type, url, content))

        response = Mock(spec=Response)
        response.status_code = 200
        response.json = lambda: json.loads(response.text)

        if self.server_unavailable:
            response.status_code = 503
            response.reason = "Service Unavailable"
            response.text = "503 Service Unavailable"

        elif "accessibleProperties" in url:
            if "subpropertieskey" in url:
                response.text = json.dumps(Constants.accessibleSubPropertiesResponse)
            elif Constants.invalidKey in url: 
                response.text = json.dumps(Constants.invalidKeyResponse)
                response.status_code = 400
                response.headers = {'header': 'value'}
            elif Constants.noDataKey in url: 
                response.text = json.dumps(Constants.noDataKeyResponse)
                response.url = url
                response.status_code = 400
                response.headers = {'header': 'value'} 
            elif Constants.noErrorNoSuccessKey in url:
                response.text = json.dumps(Constants.noErrorNoSuccessResponse)
                response.status_code = 400
                response.headers = {'header': 'value'}             
            else:
                response.text = json.dumps(Constants.accessiblePropertiesResponse)

        elif "evidencekeys" in url:
            response.text = Constants.evidenceKeysResponse

        elif "resource_key.json" in url:
            response.text = Constants.jsonResponse

        elif url.endswith("/json"):
            response.text = self.license_json_response

        else:
            response.text = f"this should not have been called with the URL '{url}'"
            response.status_code = 404

        response.content = response.text.encode("utf-8")

        return response
