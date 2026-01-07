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

import requests_mock
import requests
import unittest
from parameterized import parameterized

from fiftyone_pipeline_core.messages import Messages
from fiftyone_pipeline_core.web import *
from fiftyone_pipeline_core.aspectproperty_value import AspectPropertyValue
from fiftyone_pipeline_core.setheaderelement import SetHeaderElement

from .classes.testpipeline import TestPipeline
from .classes.constants import Constants


unknown_value = AspectPropertyValue(value = Constants.UNKNOWN)
browser_value = AspectPropertyValue(value = Constants.ACCEPTCH_BROWSER_VALUE)
platform_value = AspectPropertyValue(value = Constants.ACCEPTCH_PLATFORM_VALUE)
hardware_value = AspectPropertyValue(value = Constants.ACCEPTCH_HARDWARE_VALUE)

setHeader_properties_dict = {'device': ['SetHeaderBrowserAccept-CH', 'SetHeaderHardwareAccept-CH', 'SetHeaderPlatformAccept-CH']}


class SetHeaderUACHTests(unittest.TestCase):
    # Test response header value to be set for UACH
    @parameterized.expand([
        ({"device" : { "setheaderbrowseraccept-ch": unknown_value}}, ""),
        ({"device" : { "setheaderbrowseraccept-ch": browser_value}}, "SEC-CH-UA,SEC-CH-UA-Full-Version"),
        ({"device" : { "setheaderplatformaccept-ch": platform_value, "setheaderhardwareaccept-ch": hardware_value}}, "SEC-CH-UA-Model,SEC-CH-UA-Mobile,SEC-CH-UA-Arch,SEC-CH-UA-Platform,SEC-CH-UA-Platform-Version"),
        ({"device" : { "setheaderhardwareaccept-ch": hardware_value}}, "SEC-CH-UA-Model,SEC-CH-UA-Mobile,SEC-CH-UA-Arch"),
        ({"device" : { "setheaderbrowseraccept-ch": browser_value, "setheaderplatformaccept-ch": platform_value, "setheaderhardwareaccept-ch": hardware_value}}, "SEC-CH-UA,SEC-CH-UA-Full-Version,SEC-CH-UA-Model,SEC-CH-UA-Mobile,SEC-CH-UA-Arch,SEC-CH-UA-Platform,SEC-CH-UA-Platform-Version")
    ])
    def test_get_response_header_value(self, device, expected_value):
        testPipeline = TestPipeline()
        setHeaderElement = SetHeaderElement()
        flowdata = testPipeline.flowdata
        flowdata.data = device
        actual_value = setHeaderElement.get_response_header_value(flowdata, setHeader_properties_dict)
        self.assertEqual(expected_value, actual_value[Constants.ACCEPTCH_HEADER])

    # Test set response header function with empty string and with a value.
    # UACH response header should not be set in empty string case.

    @parameterized.expand([
        ({"set-headers" : {"responseheaderdictionary" : {"Accept-CH": ""}}}, False),
        ({"set-headers" : {"responseheaderdictionary" : {"Accept-CH": "SEC-CH-UA,SEC-CH-UA-Full-Version"}}}, True)
        ])
    def test_set_response_header(self, data, expected_value):
        adapter = requests_mock.Adapter()
        session = requests.Session()
        session.mount('mock', adapter) 
        adapter.register_uri('GET',
                        'mock://test.com/3',
                        headers={},
                        status_code=200)
        response = session.get('mock://test.com/3')

        testPipeline = TestPipeline()
        flowdata = testPipeline.flowdata
        flowdata.data = data

        response = set_response_header(flowdata, response)
        self.assertEqual(expected_value, Constants.ACCEPTCH_HEADER in response.headers)

    # Test get response header function for valid formats.
    @parameterized.expand([
        ("SetHeaderBrowserAccept-CH", "Accept-CH"),
        ("SetHeaderBrowserCritical-CH", "Critical-CH"),
        ("SetHeaderUnknownAccept-CH", "Accept-CH")
        ])
    def test_get_response_header_name(self, property_key, expected_value):
        setHeaderElement = SetHeaderElement()
        actual_value = setHeaderElement.get_response_header_name(property_key)
        self.assertEqual(expected_value, actual_value)

    # Test get response header function raises exception 
    # for invalid property formats.
    @parameterized.expand([
    ("TestBrowserAccept-CH", Messages.PROPERTY_NOT_SET_HEADER),
    ("SetHeaderbrowserAccept-CH", Messages.WRONG_PROPERTY_FORMAT),
    ("SetHeaderBrowseraccept-ch", Messages.WRONG_PROPERTY_FORMAT)
    ])
    def test_get_response_header_name(self, property_value, expected_message):

        setHeaderElement = SetHeaderElement()
        try:
            setHeaderElement.get_response_header_name(property_value)
        except Exception as e:
            message = str(e)

        self.assertEqual(expected_message.format(property_value), message)
