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

import unittest

from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

from .classes.testpipeline import TestPipeline
from .classes.memorylogger import MemoryLogger
from .classes.exampleflowelement1 import ExampleFlowElement1
# from .classes.exampleflowelement2 import ExampleFlowElement2
# from .classes.stopflowdata import StopFlowData
# from .classes.errorflowdata import ErrorFlowData

######################################
# The Tests


class CoreTests(unittest.TestCase):
    # Test logging works
    def testLogger(self):
    
        testPipeline = TestPipeline().pipeline

        loggerMessage = testPipeline.logger.memory_log[0]["message"]
        self.assertTrue(loggerMessage == "test")

    # Test getting evidence
    def testEvidence(self):

        testPipeline = TestPipeline()
        userAgent = testPipeline.flowdata.evidence.get("header.user-agent")
        self.assertTrue(userAgent == "test")

    # Test filtering evidence
    def testEvidenceKeyFilter(self):

        testPipeline = TestPipeline()
        nullEvidence = testPipeline.flowdata.evidence.get("header.other-evidence")
        self.assertTrue(nullEvidence == None)

    # Test Getter methods
    def testGet(self):
 
        testPipeline = TestPipeline()
        getValue = testPipeline.flowdata.get("example1").get("integer")
        self.assertTrue(getValue == 5)

    def testGetWhere(self):

        testPipeline = TestPipeline()
        getValue = len(testPipeline.flowdata.get_where("type", "int"))
        self.assertTrue(getValue == 1)

    def testGetFromElement(self):

        testPipeline = TestPipeline()
        getValue = testPipeline.flowdata.get_from_element(testPipeline.flowElement1).get("integer")
        self.assertTrue(getValue == 5)

    # # Test check stop FlowData works
    def testStopFlowData(self):
        testPipeline = TestPipeline()
        try:
            testPipeline.flowdata.get("example2")
        except Exception as e:
            message = str(e)

        self.assertEqual(message, "There is no element data for example2 against this flow data. Available element data keys are: ['example1', 'error', 'apv', 'stop', 'example2']")

    # Test exception is thrown when not suppressed.
    def testErrors_dont_suppress_exception(self):
        try:
            testPipeline = TestPipeline(False)
            self.assertFalse("Exception is expected.")
        except Exception as e:
            self.assertTrue(str(e) is not None)

    # Test errors are returned
    def testErrors(self):
        testPipeline = TestPipeline()
        getValue = testPipeline.flowdata.errors["error"]
        self.assertTrue(getValue.flow_element == "error")
        self.assertTrue(getValue.exception_instance is not None)
        self.assertTrue(getValue.exception_traceback is not None)

    # Test Already Processed FlowData
    def testErrors_already_processed(self):
        flowElement1 = ExampleFlowElement1()
        logger = MemoryLogger("info")
        pipeline = (PipelineBuilder())\
            .add(flowElement1)\
            .add_logger(logger)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.process()

        try:
            flowdata.process()
            self.assertFalse("Exception is expected.")
        except Exception as e:
            self.assertEqual("FlowData already processed", str(e))

    # Test aspectPropertyValue wrapper
    def testAPV(self):
        testPipeline = TestPipeline()
        yes = testPipeline.flowdata.get("apv").get("yes")

        self.assertTrue(yes.has_value())
        self.assertTrue(yes.value() == "yes")

        no = testPipeline.flowdata.get("apv").get("no")

        self.assertFalse(no.has_value())
        self.assertTrue(no.no_value_message() == "no")

    def test_build_from_config(self):
        config = {
            "PipelineOptions": {
                "Elements": [
                    {
                        "elementName": "ExampleFlowElement1",
                        "elementPath": "tests.classes.exampleflowelement1",
                        "elementParameters": {
                            "example_param": "hello"
                        }
                    }
                ]
            }
        }

        pipeline = PipelineBuilder().build_from_configuration(config)

        fd = pipeline.create_flowdata()

        fd.evidence.add("header.user-agent", "test")
        
        fd.process()

        getValue = fd.get("example1").get("integer")
        self.assertTrue(getValue == 5)
