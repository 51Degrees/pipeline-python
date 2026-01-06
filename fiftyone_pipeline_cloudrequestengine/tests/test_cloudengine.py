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
import os
import unittest
from urllib.parse import urlencode

from fiftyone_pipeline_cloudrequestengine.cloudrequestengine import CloudRequestEngine
from fiftyone_pipeline_cloudrequestengine.cloudrequestexception import CloudRequestException
from fiftyone_pipeline_cloudrequestengine.cloudengine import CloudEngine
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder


class CloudEngineTests(unittest.TestCase):
    def setUp(self):
        self.resource_key = os.environ.get("resource_key")

        self.assertIsNotNone(
            self.resource_key,
            "You need to create a resource key at"
            " https://configure.51degrees.com and paste it"
            " into the code, replacing !!YOUR_RESOURCE_KEY!!."
            " Please make sure to include IsMobile property."
        )

    def test_cloud_engine(self):
        """!
        Verify that cloud engine returns isMobile property in response.
        This is an integration test that uses the live cloud service
        so any problems with that service could affect the result
        of this test.
        """
        cloud = CloudRequestEngine({"resource_key": self.resource_key})

        engine = CloudEngine()
        engine.datakey = "device"

        pipeline = PipelineBuilder()
        pipeline = pipeline.add(cloud).add(engine).build()

        fd = pipeline.create_flowdata()
        fd.evidence.add(
            "header.user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) Gecko/20100101 Firefox/78.0",
        )

        result = fd.process()
        self.assertTrue(result.device.ismobile.has_value())

    def test_cloud_post_request_with_sequence_evidence(self):
        """!
        Verify that making POST request with SequenceElement evidence
        will not return any errors from cloud.
        This is an integration test that uses the live cloud service
        so any problems with that service could affect the result
        of this test.
        """
        cloud = CloudRequestEngine({"resource_key": self.resource_key})

        engine = CloudEngine()
        engine.datakey = "device"

        pipeline = PipelineBuilder()
        pipeline = pipeline.add(cloud).add(engine).build()

        fd = pipeline.create_flowdata()
        fd.evidence.add("query.session-id", "8b5461ac-68fc-4b18-a660-7bd463b2537a")
        fd.evidence.add("query.sequence", 1)

        result = fd.process()
        self.assertTrue(len(result.errors) == 0)

    def test_cloud_get_request_with_sequence_evidence(self):
        """!
        Verify that making GET request with SequenceElement evidence
        in query params will not return an error from cloud
        This is an integration test that uses the live cloud service
        so any problems with that service could affect the result
        of this test.
        """
        cloud = CloudRequestEngine({"resource_key": self.resource_key})

        engine = CloudEngine()
        engine.datakey = "device"

        pipeline = PipelineBuilder()
        pipeline = pipeline.add(cloud).add(engine).build()

        fd = pipeline.create_flowdata()

        fd.evidence.add("query.session-id", "8b5461ac-68fc-4b18-a660-7bd463b2537a")
        fd.evidence.add("query.sequence", 1)

        url = cloud.baseURL + cloud.resource_key + ".json?"

        evidence = fd.evidence.get_all()

        # Remove prefix from evidence

        evidence_without_prefix = {}

        for key, value in evidence.items():       
            key_split = key.split(".")
            try:
                key_split[1]
            except Exception:  # noqa
                continue
            else:
                evidence_without_prefix[key_split[1]] = value
        url += urlencode(evidence_without_prefix)

        json_response = cloud.make_cloud_request('GET', url, content=None)
        json_response = json.loads(json_response)
        self.assertNotIn("errors", json_response)

    def test_HttpDataSetInException(self):
        """!
        Check that errors from the cloud service will cause the
        appropriate data to be set in the CloudRequestException.
        """
        with self.assertRaises(CloudRequestException) as context:
            engine = CloudRequestEngine({"resource_key": "resource_key"})
            # trigger the lazy load of the properties
            engine.flow_element_properties  # noqa

        self.assertNotEqual(context.exception.httpStatusCode, 0, "Status code should not be 0")
        self.assertIsNotNone(context.exception.responseHeaders, "Response headers are not populated")
        self.assertGreater(len(context.exception.responseHeaders), 0, "Response headers are not populated")
