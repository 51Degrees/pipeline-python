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

## @example cloud/mixed/gettingstarted_console.py
#
# This example uses device detection and IP intelligence from the 51Degrees
# cloud service in a single pipeline.
#
# You will learn:
#
# 1. How to create a pipeline that uses both 51Degrees cloud device
#    detection and IP intelligence
# 2. How to pass input data (a User-Agent and an IP address) to the pipeline
# 3. How to read device and IP intelligence results from one set of flow
#    data
#
# This example is available in full on [GitHub](https://github.com/51Degrees/pipeline-python/blob/main/fiftyone_pipeline_cloudrequestengine/examples/src/fiftyone_pipeline_examples/cloud/mixed/gettingstarted_console.py).
#
# To run this example you need a resource key or a licence key.
#
# A resource key carries the list of properties it returns. Create one
# carrying device detection and IP intelligence properties for free at
# https://configure.51degrees.com?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=header
# and set the _51DEGREES_RESOURCE_KEY environment variable to it, or pass it
# as the first argument.
#
# A licence key can be used on its own instead, by setting the
# _51DEGREES_LICENSE_KEY environment variable to it. A licence key carries
# no list of properties, so the example asks the cloud service for exactly
# the properties it prints. A licence key identifies an account, so keep it
# on the server and never put it in a page.
#
# The pipeline talks to cloud.51degrees.com unless the cloud_endpoint or
# FOD_CLOUD_API_URL environment variable names another cloud service. A
# resource key limited to particular domains needs one of them in the
# cloud_request_origin environment variable.
#
# Run it from the examples folder, once the requirements there are
# installed, with
# ```
# python -m fiftyone_pipeline_examples.cloud.mixed.gettingstarted_console
# ```
#
# Required PyPI dependencies:
# - [fiftyone_pipeline_cloudrequestengine](https://pypi.org/project/fiftyone-pipeline-cloudrequestengine/)

import sys

from fiftyone_pipeline_cloudrequestengine.cloudrequestexception import (
    CloudRequestException)
from fiftyone_pipeline_core.logger import Logger

from fiftyone_pipeline_examples.cloud.engines import (
    DeviceDetectionCloud, IpIntelligenceCloud)
from fiftyone_pipeline_examples.cloud.mixed.pipeline import build_pipeline
from fiftyone_pipeline_examples.example_utils import ExampleUtils


class GettingStartedConsole():

    # Each entry pairs a User-Agent, for device detection, with an IP
    # address, for IP intelligence.
    EVIDENCE = [
        # A desktop in the United Kingdom.
        {
            "header.user-agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36",
            "query.client-ip": "82.12.34.23",
        },
        # A mobile device with an address registered in China.
        {
            "header.user-agent":
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/14.0.3 Mobile/15E148 Safari/604.1",
            "query.client-ip": "1.3.32.31",
        },
        # A desktop in Brazil.
        {
            "header.user-agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36",
            "query.client-ip": "45.236.48.61",
        },
        # A tablet with an IPv6 address from the range kept for
        # documentation.
        {
            "header.user-agent":
                "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "CriOS/91.0.4472.80 Mobile/15E148 Safari/604.1",
            "query.client-ip": "2001:0db8:085a:0000:0000:8a2e:0370:7334",
        },
        # An Android device with a Google address, registered in the
        # United States.
        {
            "header.user-agent":
                "Mozilla/5.0 (Linux; Android 11; SM-G973F) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.120 Mobile Safari/537.36",
            "query.client-ip": "8.8.8.8",
        },
    ]

    # The device detection properties to show, as label and property name.
    # See the property dictionary at
    # https://51degrees.com/developers/property-dictionary?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=device-properties
    # for every property available.
    DEVICE_PROPERTIES = [
        ("Mobile Device", "ismobile"),
        ("Platform Name", "platformname"),
        ("Platform Version", "platformversion"),
        ("Browser Name", "browsername"),
        ("Browser Version", "browserversion"),
        ("Hardware Name", "hardwarename"),
        ("Hardware Vendor", "hardwarevendor"),
        ("Device Type", "devicetype"),
        ("Screen Width", "screenpixelswidth"),
        ("Screen Height", "screenpixelsheight"),
    ]

    # The IP intelligence properties to show, as label and property name.
    IP_PROPERTIES = [
        ("Country", "country"),
        ("Country Code", "countrycode"),
        ("Region", "region"),
        ("State", "state"),
        ("Town", "town"),
        ("Latitude", "latitude"),
        ("Longitude", "longitude"),
        ("Registered Name", "registeredname"),
        ("Registered Owner", "registeredowner"),
        ("Registered Country", "registeredcountry"),
        ("IP Range Start", "iprangestart"),
        ("IP Range End", "iprangeend"),
        ("Accuracy Radius", "accuracyradiusmin"),
        ("Time Zone Offset", "timezoneoffset"),
    ]

    # Where to go next, printed after the results.
    FIND_OUT_MORE = [
        ("Device detection",
         "https://51degrees.com/device-detection?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=find-out-more-device-detection"),
        ("IP intelligence",
         "https://51degrees.com/ip-intelligence?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=find-out-more-ip-intelligence"),
        ("Resource keys",
         "https://51degrees.com/documentation/_services__cloud__resource_keys.html?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=find-out-more-resource-keys"),
        ("Pricing",
         "https://51degrees.com/pricing?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=find-out-more-pricing"),
        ("Pipeline API for Python",
         "https://github.com/51Degrees/pipeline-python"),
        ("Device detection for Python",
         "https://github.com/51Degrees/device-detection-python"),
        ("IP intelligence engine",
         "https://github.com/51Degrees/ip-intelligence-cxx"),
    ]

    @classmethod
    def values(cls):

        """!
        The properties the example prints, as the cloud service names them.
        A request made with a licence key asks for these.
        """

        return (
            ExampleUtils.name_values(
                DeviceDetectionCloud.DATA_KEY,
                [name for _, name in cls.DEVICE_PROPERTIES]) +
            ExampleUtils.name_values(
                IpIntelligenceCloud.DATA_KEY,
                [name for _, name in cls.IP_PROPERTIES]))

    def run(self, pipeline, output):

        # Carry out some sample detections.
        for evidence in self.EVIDENCE:
            self.analyse_evidence(evidence, pipeline, output)

        message = ["=" * 79, "Find out more:"]
        for label, url in self.FIND_OUT_MORE:
            message.append(f"\t{label}: {url}")
        output("\n".join(message) + "\n")

    def analyse_evidence(self, evidence, pipeline, output):

        # Flow data carries the evidence into the pipeline and the results
        # out of it.
        data = pipeline.create_flowdata()

        # List the evidence.
        message = ["=" * 79, "Input values:"]
        for key, value in evidence.items():
            message.append(f"\t{key}: {value}")
        output("\n".join(message) + "\n")

        # Add the evidence to the flow data.
        data.evidence.add_from_dict(evidence)

        # Process the flow data. One request to the cloud service returns
        # the device detection and the IP intelligence results together.
        data.process()

        message = []
        self.append_results(
            "Device Detection Results:",
            ExampleUtils.get_element(data, "device"),
            self.DEVICE_PROPERTIES,
            message)
        message.append("")
        self.append_results(
            "IP Intelligence Results:",
            ExampleUtils.get_element(data, "ip"),
            self.IP_PROPERTIES,
            message)
        output("\n".join(message) + "\n")

    @staticmethod
    def append_results(heading, element_data, properties, message):

        message.append(heading)
        message.append("-" * len(heading))
        for label, property_name in properties:
            value = ExampleUtils.get_human_readable(element_data, property_name)
            message.append(f"\t{label}: {value}")


def create_pipeline(logger, resource_key=None, license_key=None,
                    cloud_endpoint=None, cloud_request_origin=None):

    """!
    The pipeline the example uses. For more information about building
    pipelines see the documentation at
    https://51degrees.com/documentation/_pipeline_api__concepts__configuration__builders__index.html?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=create-pipeline
    """

    return build_pipeline(
        logger,
        GettingStartedConsole.values(),
        resource_key=resource_key,
        license_key=license_key,
        cloud_endpoint=cloud_endpoint,
        cloud_request_origin=cloud_request_origin,
        # A console has no page, so leave out the elements that write the
        # client-side script and set response headers.
        pipeline_settings={
            "add_javascript_builder": False,
            "use_setheader_properties": False,
        })


def main(argv):

    # A resource key given on the command line is used as it is. Otherwise
    # the keys come from the environment, where a licence key is used in
    # place of a resource key.
    if len(argv) > 0:
        resource_key, license_key = argv[0], ""
    else:
        resource_key = ExampleUtils.get_resource_key()
        license_key = ExampleUtils.get_license_key()

    # Configure a logger to output to the console.
    logger = Logger(min_level="info")

    if not (resource_key or license_key):
        logger.log("error",
            "No key specified in the environment variable "
            f"'{ExampleUtils.RESOURCE_KEY_ENV_VAR}' or "
            f"'{ExampleUtils.LICENSE_KEY_ENV_VAR}'. The 51Degrees cloud "
            "service is accessed using a resource key or a licence key. For "
            "more information see "
            "https://51degrees.com/documentation/_services__cloud__resource_keys.html?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=resource-key-required. "
            "A resource key carrying the device detection and IP "
            "intelligence properties this example uses can be created for "
            "free at "
            "https://configure.51degrees.com?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_console.py&utm_term=resource-key-required. "
            "Once complete, set the first environment variable named at "
            "the start of this message to the key.")
        return

    try:
        pipeline = create_pipeline(
            logger, resource_key, license_key,
            ExampleUtils.get_cloud_endpoint(),
            ExampleUtils.get_cloud_request_origin())
    except (ValueError, CloudRequestException) as error:
        # The key carries nothing the example shows, or the cloud service
        # refused it, for example because the key is limited to domains
        # that do not include the origin sent.
        logger.log("error", str(error))
        return

    GettingStartedConsole().run(pipeline, print)


if __name__ == "__main__":
    main(sys.argv[1:])
