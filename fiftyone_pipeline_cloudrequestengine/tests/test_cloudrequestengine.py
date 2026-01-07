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

import os
import warnings
from parameterized import parameterized

from fiftyone_pipeline_cloudrequestengine.cloudrequestexception import CloudRequestException
from fiftyone_pipeline_cloudrequestengine.cloudrequestengine import CloudRequestEngine
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder
from fiftyone_pipeline_cloudrequestengine.constants import Constants

from .classes.constants import Constants as TestConstants
from .classes.cloudrequestengine_testbase import CloudRequestEngineTestsBase


class TestCloudRequestEngine(CloudRequestEngineTestsBase):
    """!
    Test cloud request engine adds correct information to post request
    following the order of precedence when processing evidence and 
    returns the response in the ElementData. Evidence parameters 
    should be added in descending order of precedence.
    """

    testResourceKey = "resource_key"
    testEndPoint = "http://testEndPoint/"
    testEnvVarEndPoint = "http://testEnvVarEndPoint/"

    def setUp(self):
        if os.environ.get(Constants.FOD_CLOUD_API_URL) is not None:
            del os.environ[Constants.FOD_CLOUD_API_URL]

    def testConfigEndPoint_ExplicitSetting(self):
        """!
        Check that the explicitly setting the cloud endpoint via 
        method interface take precedence over everything else
        """

        os.environ[Constants.FOD_CLOUD_API_URL] = TestCloudRequestEngine.testEnvVarEndPoint
        cloud_request_engine = CloudRequestEngine({
            "resource_key": TestCloudRequestEngine.testResourceKey,
            "cloud_endpoint": TestCloudRequestEngine.testEndPoint,
            "http_client": self.mock_http()
        })
        self.assertEqual(TestCloudRequestEngine.testEndPoint, cloud_request_engine.baseURL)

    def testConfigEndPoint_EnvironmentVariableSetting(self):
        """!
        Check that the setting the cloud endpoint via environment 
        variable take precedence over the default value
        """

        os.environ[Constants.FOD_CLOUD_API_URL] = TestCloudRequestEngine.testEnvVarEndPoint
        cloud_request_engine = CloudRequestEngine({
            "resource_key": TestCloudRequestEngine.testResourceKey,
            "http_client": self.mock_http()
        })
        self.assertEqual(TestCloudRequestEngine.testEnvVarEndPoint, cloud_request_engine.baseURL)

    def testConfigEndPoint_DefaultSetting(self):
        """!
        Check that if nothing else is set the default value should be used
        """

        cloud_request_engine = CloudRequestEngine({
            "resource_key": TestCloudRequestEngine.testResourceKey,
            "http_client": self.mock_http()
        })
        self.assertEqual(Constants.BASE_URL_DEFAULT, cloud_request_engine.baseURL)

    @parameterized.expand([
        (False, "query.User-Agent=iPhone", "header.User-Agent=iPhone"),
        (False, "query.User-Agent=iPhone", "cookie.User-Agent=iPhone"),
        (True, "header.User-Agent=iPhone", "cookie.User-Agent=iPhone"),
        (False, "query.value=1", "a.value=1"),
        (True, "a.value=1", "b.value=1"),
        (True, "e.value=1", "f.value=1")
    ])
    def test_evidence_precedence(self, warn, evidence1, evidence2):
        """!
        Test cloud request engine adds correct information to post request
        following the order of precedence when processing evidence and 
        returns the response in the ElementData. Evidence parameters 
        should be added in descending order of precedence.
        """

        evidence1_parts = evidence1.split("=")
        evidence2_parts = evidence2.split("=")
        
        engine = CloudRequestEngine({
            "resource_key": TestConstants.resourceKey,
            "http_client": self.mock_http(),
        })

        builder = PipelineBuilder()
        pipeline = builder.add(engine).build()

        data = pipeline.create_flowdata()

        data.evidence.add(evidence1_parts[0], evidence1_parts[1])
        data.evidence.add(evidence2_parts[0], evidence2_parts[1])

        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")
            # Trigger warning.
            data.process()

        # If warn is expected then check for warnings from cloud request 
        # engine.
        if warn:
            # Verify warning is thrown.
            self.assertTrue(len(w) == 1)
            self.assertTrue(issubclass(w[-1].category, UserWarning))
            self.assertIn(
                TestConstants.PRECENDENCE_WARNING.format(
                    evidence1_parts[0],
                    evidence1_parts[1],
                    evidence2_parts[0],
                    evidence2_parts[1]
                ),
                str(w[-1].message),
            )
        else:
            self.assertTrue(len(w) == 0)

    @parameterized.expand([
        (
            {"query.User-Agent": "iPhone", "header.User-Agent": "iPhone"},
            "query",
            {"query.User-Agent": "iPhone"},
        ),
        (
            {"header.User-Agent": "iPhone", "a.User-Agent": "iPhone", "z.User-Agent": "iPhone"},
            "other",
            {"z.User-Agent": "iPhone", "a.User-Agent": "iPhone"},
        ),
    ])
    def test_get_selected_evidence(self, evidence, ev_type, expected_value):
        """!
        Test evidence of specific type is returned from all 
        the evidence passed, if type is not from query, header
        or cookie then evidences are returned sorted in descensing order
        """

        engine = CloudRequestEngine({
            "resource_key": TestConstants.resourceKey,
            "http_client": self.mock_http(),
        })

        result = engine.get_selected_evidence(evidence, ev_type)
        self.assertEqual(expected_value, result)

    @parameterized.expand([
        ({"query.User-Agent": "query-iPhone", "header.User-Agent": "header-iPhone"},  "query-iPhone"),
        ({"header.User-Agent": "header-iPhone", "cookie.User-Agent": "cookie-iPhone"}, "header-iPhone"),
        ({"a.User-Agent": "a-iPhone", "b.User-Agent": "b-iPhone", "z.User-Agent": "z-iPhone"}, "a-iPhone")
    ])
    def test_get_content(self, evidence, expected_value):
        """!
        Test Content to send in the POST request is generated as
        per the precedence rule of The evidence keys. These are
        added to the evidence in reverse order, if there is conflict then 
        the queryData value is overwritten.
        """

        engine = CloudRequestEngine({
            "resource_key": TestConstants.resourceKey,
            "http_client": self.mock_http(),
        })

        builder = PipelineBuilder()
        pipeline = builder.add(engine).build()

        data = pipeline.create_flowdata()

        for key, value in evidence.items():
            data.evidence.add(key, value)

        result = engine.get_content(data)

        self.assertEqual(expected_value, result["user-agent"])

    def test_no_exception_on_cloud_request_engine_init(self):
        """
        Test no exception is thrown when cloud request engine is
        initialised and server is down
        """

        CloudRequestEngine({
            "resource_key": TestConstants.resourceKey,
            "http_client": self.mock_http(server_unavailable=True),
        })

    def test_exception_on_server_down_without_suppression(self):
        evidence = {"query.User-Agent": "query-iPhone", "header.User-Agent": "header-iPhone"}

        engine = CloudRequestEngine({
            "resource_key": TestConstants.resourceKey,
            "http_client": self.mock_http(server_unavailable=True),
        })

        builder = PipelineBuilder()
        pipeline = builder.add(engine).build()
        pipeline.suppress_process_exceptions = False

        data = pipeline.create_flowdata()

        for key, value in evidence.items():
            data.evidence.add(key, value)

        with self.assertRaises(CloudRequestException):
            data.process()

    def test_no_exception_on_server_down_with_suppression(self):
        evidence = {"query.User-Agent": "query-iPhone", "header.User-Agent": "header-iPhone"}

        engine = CloudRequestEngine({
            "resource_key": TestConstants.resourceKey,
            "http_client": self.mock_http(server_unavailable=True),
        })

        builder = PipelineBuilder()
        pipeline = builder.add(engine).build()
        pipeline.suppress_process_exceptions = True

        data = pipeline.create_flowdata()

        for key, value in evidence.items():
            data.evidence.add(key, value)

        data.process()
