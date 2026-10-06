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
import unittest
import warnings

from fiftyone_pipeline_cloudrequestengine.cloudrequestengine import \
    CloudRequestEngine
from fiftyone_pipeline_cloudrequestengine.cloudengine import CloudEngine
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

# The licence key the live tests authenticate with, read from either of
# the variables the other live tests and the examples in this repository
# accept, so an environment set up for them runs these tests too.
LICENSE_KEY = (
    os.environ.get("license_key")
    or os.environ.get("_51DEGREES_LICENSE_KEY")
    or "").strip()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) "
    "Gecko/20100101 Firefox/78.0")


@unittest.skipUnless(
    LICENSE_KEY != "",
    "Set license_key to a licence key entitled to device detection to run "
    "the live licence key tests.")
class LicenseKeyLiveTests(unittest.TestCase):
    """!
    Runs a pipeline that authenticates on a licence key alone against the
    live cloud service, end to end, which is the test that matters: the
    engine building is not enough, because the cloud engines after it have
    to find the metadata and the data they need.
    """

    def test_licence_key_alone_processes_a_request(self):
        cloud = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": ["device.ismobile"],
        })

        engine = CloudEngine()
        engine.datakey = "device"

        pipeline = PipelineBuilder().add(cloud).add(engine).build()

        # The accessible properties came back for the licence key alone, so
        # the cloud engine registered with metadata. The metadata is keyed
        # by the name as the service spells it, "IsMobile", so look it up
        # through get_properties, which lower-cases the keys as every other
        # reader of the metadata does.
        self.assertIn("ismobile", engine.get_properties())

        data = pipeline.create_flowdata()
        data.evidence.add("header.user-agent", USER_AGENT)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            data.process()

        self.assertEqual(0, len(data.errors), data.errors)
        self.assertTrue(data.device.ismobile.has_value())
        self.assertFalse(data.device.ismobile.value())

        # Every property asked for came back, so nothing was reported.
        self.assertEqual([], [
            str(warning.message) for warning in caught
            if "not covered" in str(warning.message)])

    def test_property_the_licence_does_not_cover_is_reported(self):
        """
        A property asked for beside a covered one is dropped silently by
        the service, and the engine says so once.
        """

        cloud = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": [
                "device.ismobile", "device.nosuchproperty"],
        })

        pipeline = PipelineBuilder().add(cloud).build()
        data = pipeline.create_flowdata()
        data.evidence.add("header.user-agent", USER_AGENT)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            data.process()

        messages = [
            str(warning.message) for warning in caught
            if "not covered" in str(warning.message)]
        self.assertEqual(1, len(messages), messages)
        self.assertIn("device.nosuchproperty", messages[0])
