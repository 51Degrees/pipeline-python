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

"""!
Builds the pipeline the mixed examples share.
"""

from fiftyone_pipeline_cloudrequestengine.cloudrequestengine import \
    CloudRequestEngine
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

from fiftyone_pipeline_examples.cloud.engines import (
    CountriesTranslationCloud, DeviceDetectionCloud, IpIntelligenceCloud)

# The origin sent with each request to the cloud service when none is given.
CLOUD_REQUEST_ORIGIN = "51Degrees.example.com"


def build_pipeline(logger, values, resource_key=None, license_key=None,
                   cloud_endpoint=None, cloud_request_origin=None,
                   pipeline_settings=None, client_side=False):

    """!
    Create a pipeline that gets device detection and IP intelligence results
    from one request to the cloud service.

    The request is made with the licence key when there is one, and
    otherwise with the resource key. A licence key carries no list of
    properties, so the request names the ones in values. A resource key
    answers with the list it was created with.

    An engine is added for each section of the answer the key can fill, so
    a key carrying only one of the products still runs, and the properties
    of the other show as unknown.

    @param logger: where the pipeline logs
    @param values: the properties the example shows, each as
    "section.property", for example "device.devicetype"
    @param resource_key: a resource key
    @param license_key: a licence key, used in place of the resource key
    @param cloud_endpoint: the address of a cloud service other than the
    public one, including the api/v4 path
    @param cloud_request_origin: the origin to send with each request. A
    resource key limited to particular domains only answers a request
    whose origin is one of them
    @param pipeline_settings: settings for the PipelineBuilder
    @param client_side: True when a page will run the client-side script, so
    a licence key also asks for the properties that script needs
    @return the pipeline
    """

    cloud_settings = {
        "cloud_request_origin": cloud_request_origin or CLOUD_REQUEST_ORIGIN}
    if cloud_endpoint:
        cloud_settings["cloud_endpoint"] = cloud_endpoint

    # A licence key names no properties of its own, so the engine is told
    # which ones to ask for. A resource key answers with the list it was
    # created with, and the engine refuses a list beside one, because the
    # cloud service would ignore it.
    if license_key:
        cloud_settings["license_key"] = license_key
        cloud_settings["requested_properties"] = values
    else:
        cloud_settings["resource_key"] = resource_key
    request_engine = CloudRequestEngine(cloud_settings)

    # The cloud request engine asks the cloud service which properties the
    # key carries, by section.
    carried = request_engine.flow_element_properties

    if license_key and client_side:
        # A resource key made in the configurator carries the properties
        # that gather evidence in the browser and ask it for User-Agent
        # Client Hints. A licence key has to name them, so ask for every
        # one the licence entitles in the sections the example uses. The
        # engine reads its list on each request, so it can grow here.
        client_side_names = client_side_values(carried, values)
        values = values + client_side_names
        request_engine.add_requested_properties(client_side_names)

    wanted = {value.lower() for value in values}

    def can_fill(engine):
        section = engine.DATA_KEY
        properties = {name.lower() for name in carried.get(section, {})}
        if license_key:
            # Only the properties named in the request come back.
            return any(
                f"{section}.{name}" in wanted for name in properties)
        return len(properties) > 0

    if not (can_fill(DeviceDetectionCloud) or can_fill(IpIntelligenceCloud)):
        raise ValueError(
            "The key carries neither the device detection nor the IP "
            "intelligence properties this example shows. Create a resource "
            "key that carries them for free at "
            "https://configure.51degrees.com?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-src-fiftyone_pipeline_examples-cloud-mixed-pipeline.py&utm_term=key-carries-nothing")

    builder = PipelineBuilder(pipeline_settings or {}).add(request_engine)

    for engine in (IpIntelligenceCloud, CountriesTranslationCloud,
                   DeviceDetectionCloud):
        if can_fill(engine):
            builder.add(engine())

    return builder.add_logger(logger).build()


def client_side_values(carried, values):

    """!
    The properties a page's client-side script needs, each as
    "section.property", from the sections values already names. They are
    the JavaScript the browser runs to gather evidence, and the properties
    that say which User-Agent Client Hints to ask the browser for.
    """

    sections = {value.split(".", 1)[0].lower() for value in values}

    return [
        f"{section}.{name.lower()}"
        for section in sorted(sections)
        for name, metadata in carried.get(section, {}).items()
        if str(metadata.get("type", "")).lower() == "javascript"
        or name.lower().startswith("setheader")]
