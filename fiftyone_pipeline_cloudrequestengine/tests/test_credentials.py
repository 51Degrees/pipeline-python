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

import warnings

from fiftyone_pipeline_cloudrequestengine.cloudengine import CloudEngine
from fiftyone_pipeline_cloudrequestengine.cloudrequestengine import \
    CloudRequestEngine
from fiftyone_pipeline_cloudrequestengine.constants import Constants
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

from .classes.cloudrequestengine_testbase import CloudRequestEngineTestsBase

RESOURCE_KEY = "resource_key"
LICENSE_KEY = "a-licence-key"
REQUESTED = ["device.ismobile", "device.istablet"]


class TestCredentials(CloudRequestEngineTestsBase):
    """!
    Checks every combination of resource key, licence key and requested
    properties in the Credentials table of the cloud request engine
    specification, and where each credential travels in the requests the
    engine makes.
    """

    def process(self, engine):
        """
        Run one flow data through a pipeline holding the engine, and give
        back the requests the mock client saw.
        """

        # The accessible properties are fetched on first use, which a
        # cloud engine after this one would trigger when it registers, so
        # trigger it here as that engine would.
        engine.flow_element_properties  # noqa

        pipeline = PipelineBuilder().add(engine).build()
        data = pipeline.create_flowdata()
        data.evidence.add("query.User-Agent", "iPhone")
        data.process()
        return engine.http_client.requests

    def data_request(self, requests):
        """The last request, being the one for data."""

        return requests[-1]

    def test_resource_key_alone_is_accepted(self):
        """
        Row one of the table. The resource key names the route and the
        body carries the resource key and the evidence, with no licence
        key and no list of properties.
        """

        engine = CloudRequestEngine({
            "resource_key": RESOURCE_KEY,
            "http_client": self.mock_http(),
        })

        request_type, url, content = self.data_request(
            self.process(engine))

        self.assertEqual("POST", request_type)
        self.assertTrue(url.endswith(RESOURCE_KEY + ".json?"), url)
        self.assertEqual(RESOURCE_KEY, content[Constants.RESOURCE_PARAMETER])
        self.assertNotIn(Constants.LICENSE_PARAMETER, content)
        self.assertNotIn(Constants.VALUES_PARAMETER, content)
        self.assertEqual("iPhone", content["user-agent"])

    def test_resource_key_with_licence_key_is_accepted(self):
        """
        Row two of the table. The licence key adds the products it grants,
        so it travels in the body of the data request and of the accessible
        properties request, and no list of properties is sent.
        """

        engine = CloudRequestEngine({
            "resource_key": RESOURCE_KEY,
            "license_key": LICENSE_KEY,
            "http_client": self.mock_http(),
        })

        requests = self.process(engine)

        properties_requests = [
            request for request in requests
            if "accessibleProperties" in request[1]]
        self.assertEqual(1, len(properties_requests))
        request_type, url, content = properties_requests[0]
        self.assertEqual("POST", request_type)
        self.assertNotIn(LICENSE_KEY, url)
        self.assertEqual(RESOURCE_KEY, content[Constants.RESOURCE_PARAMETER])
        self.assertEqual(LICENSE_KEY, content[Constants.LICENSE_PARAMETER])

        request_type, url, content = self.data_request(requests)
        self.assertTrue(url.endswith(RESOURCE_KEY + ".json?"), url)
        self.assertEqual(RESOURCE_KEY, content[Constants.RESOURCE_PARAMETER])
        self.assertEqual(LICENSE_KEY, content[Constants.LICENSE_PARAMETER])
        self.assertNotIn(Constants.VALUES_PARAMETER, content)

    def test_licence_key_with_properties_is_accepted(self):
        """
        Row three of the table. With no resource key the data request goes
        to the route that takes none, and the body names the licence key
        and the properties wanted. The licence key never appears in a URL.
        """

        engine = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": REQUESTED,
            "http_client": self.mock_http(),
        })

        requests = self.process(engine)

        for request_type, url, content in requests:
            self.assertNotIn(LICENSE_KEY, url)

        request_type, url, content = self.data_request(requests)
        self.assertEqual("POST", request_type)
        self.assertEqual(Constants.BASE_URL_DEFAULT + "json", url)
        self.assertNotIn(Constants.RESOURCE_PARAMETER, content)
        self.assertEqual(LICENSE_KEY, content[Constants.LICENSE_PARAMETER])
        self.assertEqual(
            "device.ismobile,device.istablet",
            content[Constants.VALUES_PARAMETER])

    def test_licence_key_discovers_properties_with_the_key_in_the_body(self):
        """
        The accessible properties request made with a licence key alone
        posts the key in the body, and the engine builds with the metadata
        the service answers.
        """

        engine = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": REQUESTED,
            "http_client": self.mock_http(),
        })

        self.assertIn("device", engine.flow_element_properties)

        request_type, url, content = engine.http_client.requests[-1]
        self.assertEqual("POST", request_type)
        self.assertEqual(
            Constants.BASE_URL_DEFAULT + "accessibleProperties", url)
        self.assertEqual({Constants.LICENSE_PARAMETER: LICENSE_KEY}, content)

    def test_licence_key_without_properties_is_refused(self):
        """
        Row four of the table. The service answers 400 to every such
        request, so the engine refuses to build and says why.
        """

        with self.assertRaises(ValueError) as context:
            CloudRequestEngine({
                "license_key": LICENSE_KEY,
                "http_client": self.mock_http(),
            })

        self.assertIn("400", str(context.exception))
        self.assertIn("requested_properties", str(context.exception))

    def test_properties_with_resource_key_are_refused(self):
        """
        Row five of the table, with and without a licence key beside the
        resource key. The service ignores the list, so the engine refuses
        to build and says the response would not narrow.
        """

        for license_key in ("", LICENSE_KEY):
            with self.assertRaises(ValueError) as context:
                CloudRequestEngine({
                    "resource_key": RESOURCE_KEY,
                    "license_key": license_key,
                    "requested_properties": REQUESTED,
                    "http_client": self.mock_http(),
                })

            self.assertIn("ignores the list", str(context.exception))

    def test_no_credential_is_refused(self):
        """
        Row six of the table, with and without a list of properties. There
        is nothing to authenticate with.
        """

        for requested_properties in ([], REQUESTED):
            with self.assertRaises(ValueError) as context:
                CloudRequestEngine({
                    "requested_properties": requested_properties,
                    "http_client": self.mock_http(),
                })

            self.assertIn("401", str(context.exception))

    def test_whitespace_counts_as_absent(self):
        """
        A credential read from the environment often carries a trailing
        newline, and a value that is only whitespace is a mistake rather
        than a key. Each is trimmed, and an empty one is treated as absent
        in the rules, so whitespace alone cannot satisfy them.
        """

        engine = CloudRequestEngine({
            "resource_key": " " + RESOURCE_KEY + "\n",
            "license_key": "   ",
            "requested_properties": [" ", ""],
            "http_client": self.mock_http(),
        })

        self.assertEqual(RESOURCE_KEY, engine.resource_key)
        self.assertEqual("", engine.license_key)
        self.assertEqual([], engine.requested_properties)

        with self.assertRaises(ValueError):
            CloudRequestEngine({
                "license_key": "\t",
                "requested_properties": REQUESTED,
                "http_client": self.mock_http(),
            })

    def test_properties_may_be_one_comma_separated_string(self):
        """
        A configuration file holds the list as one string, so that form is
        accepted and each name is trimmed and lower-cased to match the
        case the service answers in.
        """

        engine = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": " Device.IsMobile , device.IsTablet,",
            "http_client": self.mock_http(),
        })

        self.assertEqual(REQUESTED, engine.requested_properties)

    def test_reserved_evidence_is_left_out_of_the_body(self):
        """
        The service advertises values, resource and license among its
        accepted evidence keys. Evidence carrying one of them would sit in
        the body beside the engine's own credentials, so it is dropped
        whatever its prefix.
        """

        engine = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": REQUESTED,
            "http_client": self.mock_http(),
        })

        pipeline = PipelineBuilder().add(engine).build()
        data = pipeline.create_flowdata()
        data.evidence.add("query.license", "another-key")
        data.evidence.add("header.resource", "another-key")
        data.evidence.add("cookie.values", "device.iscrawler")
        data.evidence.add("query.User-Agent", "iPhone")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            data.process()

        request_type, url, content = engine.http_client.requests[-1]
        self.assertEqual(LICENSE_KEY, content[Constants.LICENSE_PARAMETER])
        self.assertNotIn(Constants.RESOURCE_PARAMETER, content)
        self.assertEqual(
            "device.ismobile,device.istablet",
            content[Constants.VALUES_PARAMETER])
        self.assertEqual("iPhone", content["user-agent"])

        # Each piece of evidence left out is named once, without its
        # value, as the value may be a credential.
        messages = [
            str(warning.message) for warning in caught
            if "is not sent" in str(warning.message)]
        self.assertEqual(3, len(messages), messages)
        for evidence_key in (
                "query.license", "header.resource", "cookie.values"):
            self.assertTrue(
                any(evidence_key in message for message in messages),
                evidence_key)
        for message in messages:
            self.assertNotIn("another-key", message)

    def test_properties_added_later_are_normalised_and_checked(self):
        """
        A caller may add to the list after the engine is built, once the
        accessible properties say which client-side properties the key
        carries. The names added are trimmed and lower-cased as the
        constructor's are, so they match the answer, and the rule that a
        list only goes with a licence key alone is checked again, because
        the constructor cannot see a list added after it ran.
        """

        engine = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": REQUESTED,
            "http_client": self.mock_http(),
        })

        engine.add_requested_properties([" Device.IsCrawler ", ""])
        engine.add_requested_properties("device.hardwarename, ")

        self.assertEqual(
            REQUESTED + ["device.iscrawler", "device.hardwarename"],
            engine.requested_properties)

        request_type, url, content = self.data_request(
            self.process(engine))
        self.assertEqual(
            ",".join(engine.requested_properties),
            content[Constants.VALUES_PARAMETER])

        engine = CloudRequestEngine({
            "resource_key": RESOURCE_KEY,
            "http_client": self.mock_http(),
        })

        with self.assertRaises(ValueError) as context:
            engine.add_requested_properties(REQUESTED)

        self.assertIn("ignores the list", str(context.exception))

    def test_properties_the_answer_leaves_out_are_reported_once(self):
        """
        The service drops a property the licence key does not cover
        without naming it. The engine compares the list it sent with the
        answer, warns once naming the missing property, and does not warn
        again on the next request. A property present but null counts as
        answered, because its nullreason explains it.
        """

        engine = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": [
                "Device.IsMobile", "device.istablet", "device.iscrawler"],
            "http_client": self.mock_http(license_json_response=(
                '{"device":{"ismobile":true,"istablet":null,'
                '"istabletnullreason":"No value on this request"}}')),
        })

        pipeline = PipelineBuilder().add(engine).build()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for _ in range(2):
                data = pipeline.create_flowdata()
                data.evidence.add("query.User-Agent", "iPhone")
                data.process()

        messages = [
            str(warning.message) for warning in caught
            if "not covered" in str(warning.message)]
        self.assertEqual(1, len(messages), messages)
        self.assertIn("device.iscrawler", messages[0])
        self.assertNotIn("device.istablet", messages[0])
        self.assertNotIn("device.ismobile", messages[0])

    def test_no_report_when_every_property_came_back(self):
        """
        An answer carrying every requested property raises no warning, and
        an engine on a resource key sends no list so there is nothing to
        compare.
        """

        for settings in (
                {"license_key": LICENSE_KEY,
                 "requested_properties": ["device.value"]},
                {"resource_key": RESOURCE_KEY}):
            settings["http_client"] = self.mock_http()
            engine = CloudRequestEngine(settings)
            pipeline = PipelineBuilder().add(engine).build()

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                data = pipeline.create_flowdata()
                data.evidence.add("query.User-Agent", "iPhone")
                data.process()

            self.assertEqual([], [
                str(warning.message) for warning in caught
                if "not covered" in str(warning.message)])

    def test_missing_property_message_names_both_causes(self):
        """
        With a licence key the accessible properties list everything the
        licence entitles, so a property can be listed as carried and still
        be absent from an answer because it was not requested. The message
        for a property that is not in the data says so, and names the
        element it looked in rather than assuming device.
        """

        engine = CloudRequestEngine({
            "license_key": LICENSE_KEY,
            "requested_properties": ["device.value"],
            "http_client": self.mock_http(),
        })
        device = CloudEngine()
        device.datakey = "device"

        pipeline = PipelineBuilder().add(engine).add(device).build()
        data = pipeline.create_flowdata()
        data.evidence.add("query.User-Agent", "iPhone")
        data.process()

        with self.assertRaises(Exception) as context:
            data.device.get("other")

        message = str(context.exception)
        self.assertIn("Property other not found", message)
        self.assertIn("requested_properties", message)
        self.assertIn("under device are value", message)
        self.assertNotIn("your resource key", message)
