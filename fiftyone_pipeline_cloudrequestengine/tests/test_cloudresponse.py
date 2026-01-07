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

from fiftyone_pipeline_cloudrequestengine.cloudrequestengine import CloudRequestEngine
from fiftyone_pipeline_cloudrequestengine.cloudrequestexception import CloudRequestException
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

from .classes.cloudrequestengine_testbase import CloudRequestEngineTestsBase
from .classes.constants import *


class TestCloudResponse(CloudRequestEngineTestsBase):
    def setUp(self):
        self.http_client = self.mock_http()

    def test_process(self):
        """
            Test cloud request engine adds correct information to post request
            and returns the response in the ElementData
        """
        engine = CloudRequestEngine({
            "resource_key": Constants.resourceKey,
            "http_client": self.http_client,
        })

        builder = PipelineBuilder()
        pipeline = builder.add(engine).build()

        data = pipeline.create_flowdata()
        data.evidence.add("query.User-Agent", Constants.userAgent)

        data.process()

        result = data.get_from_element(engine)["cloud"]

        self.assertEqual(Constants.jsonResponse, result)

        json_obj = json.loads(result)
        self.assertEqual(json_obj["device"]["value"], 1)

    def test_sub_properties(self):
        """
            Verify that the CloudRequestEngine can correctly parse a
            response from the accessible properties endpoint that contains
            meta-data for sub-properties.
        """
        engine = CloudRequestEngine({
            "resource_key": "subpropertieskey",
            "http_client": self.http_client,
        })

        self.assertEqual(len(engine.flow_element_properties), 2)

        device_properties = engine.flow_element_properties["device"]
        self.assertEqual(len(device_properties), 2)
        self.assertTrue(self.properties_contain_name(device_properties, "IsMobile"))
        self.assertTrue(self.properties_contain_name(device_properties, "IsTablet"))

        devices_properties = engine.flow_element_properties["devices"]
        self.assertFalse(devices_properties is None)
        self.assertEqual(len(devices_properties), 1)
        self.assertTrue(
            self.properties_contain_name(
                devices_properties["Devices"]["itemproperties"],
                "IsMobile",
            )
        )
        self.assertTrue(
            self.properties_contain_name(
                devices_properties["Devices"]["itemproperties"],
                "IsTablet",
            )
        )

    def test_validate_error_handling_invalid_resourceKey(self):
        """ 
            Test cloud request engine handles errors from the cloud service 
            as expected.
            An exception should be thrown by the cloud request engine
            containing the errors from the cloud service when resource key
            is invalid.
        """
        with self.assertRaises(CloudRequestException) as context:
            engine = CloudRequestEngine({
                "resource_key": Constants.invalidKey,
                "http_client": self.http_client,
            })
            # trigger the lazy load of the properties
            engine.flow_element_properties  # noqa

        self.assertEqual(Constants.invalidKeyMessageComplete, context.exception.message)

    def test_validate_error_handling_nodata(self):
        """ 
            Test cloud request engine handles a lack of data from the 
            cloud service as expected.
            An exception should be thrown by the cloud request engine.
        """
        with self.assertRaises(CloudRequestException) as context:
            engine = CloudRequestEngine({
                "resource_key": Constants.noDataKey,
                "http_client": self.http_client,
            })
            # trigger the lazy load of the properties
            engine.flow_element_properties  # noqa

        self.assertEqual(Constants.noDataKeyMessageComplete, context.exception.message)

    def test_validate_error_handling_noerror_nosuccess(self):
        """ 
            Test cloud request engine handles no success error from the 
            cloud service as expected.
            An exception should be thrown by the cloud request engine.
        """ 
        with self.assertRaises(CloudRequestException) as context:
            engine = CloudRequestEngine({
                "resource_key": Constants.noErrorNoSuccessKey,
                "http_client": self.http_client,
            })
            # trigger the lazy load of the properties
            engine.flow_element_properties  # noqa

        self.assertEqual(Constants.noErrorNoSuccessMessage, context.exception.message)
