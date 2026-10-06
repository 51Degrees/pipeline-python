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

## @example cloud/mixed/gettingstarted_web/app.py
#
# This example uses device detection and IP intelligence from the 51Degrees
# cloud service within a single Flask web application. It shows device
# detection from the User-Agent and User-Agent Client Hints, the location
# and network of an IP address, the list of countries translated by the
# cloud service, and client-side evidence refining the device results.
#
# Each time the pipeline processes a request, one request to the cloud
# service returns the results of every engine in it.
#
# This example is available in full on [GitHub](https://github.com/51Degrees/pipeline-python/blob/main/examples/src/fiftyone_pipeline_examples/cloud/mixed/gettingstarted_web/app.py).
#
# To run this example you need a resource key or a licence key.
#
# A resource key carries the list of properties it returns. Create one
# carrying device detection and IP intelligence properties for free at
# https://configure.51degrees.com?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_web-app.py&utm_term=header
# and set the _51DEGREES_RESOURCE_KEY environment variable to it, or pass it
# as the first argument.
#
# A licence key can be used on its own instead, by setting the
# _51DEGREES_LICENSE_KEY environment variable to it. A licence key carries
# no list of properties, so the example asks the cloud service for exactly
# the properties the page shows. A licence key identifies an account, so it
# stays on this server. The page and its script only ever talk to this
# server, never to the cloud service.
#
# The pipeline talks to cloud.51degrees.com unless the cloud_endpoint or
# FOD_CLOUD_API_URL environment variable names another cloud service. A
# resource key limited to particular domains needs one of them in the
# cloud_request_origin environment variable.
#
# Run it from the examples folder, once the requirements there are
# installed, with
# ```
# python -m fiftyone_pipeline_examples.cloud.mixed.gettingstarted_web
# ```
# and open http://localhost:5000, or the port named by the PORT environment
# variable. Use the form on the page, or add ?client-ip=8.8.8.8 to the
# address, to look up an IP address other than your own.
#
# Results are also available to the page's own JavaScript through the `fod`
# object, which the client-side script creates.
# ```{js}
# fod.complete(function (data) {
#     alert(data.device.browsername + " in " + data.ip.country);
# });
# ```
#
# Required PyPI dependencies:
# - [fiftyone_pipeline_cloudrequestengine](https://pypi.org/project/fiftyone-pipeline-cloudrequestengine/)
# - [flask](https://pypi.org/project/flask/)

import json
import os
import sys

from flask import Flask, make_response, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from fiftyone_pipeline_cloudrequestengine.cloudrequestexception import (
    CloudRequestException)
from fiftyone_pipeline_core.logger import Logger
from fiftyone_pipeline_core.web import set_response_header, webevidence

from fiftyone_pipeline_examples.cloud.engines import (
    CountriesTranslationCloud, DeviceDetectionCloud, IpIntelligenceCloud)
from fiftyone_pipeline_examples.cloud.mixed.pipeline import build_pipeline
from fiftyone_pipeline_examples.example_utils import ExampleUtils

# The device detection properties the page shows, as label and property
# name. The browser tests every language's example shares read the "Device
# Type:" and "Device Id:" rows, so those labels stay as they are.
DEVICE_PROPERTIES = [
    ("Hardware Vendor:", "hardwarevendor"),
    ("Hardware Name:", "hardwarename"),
    ("Device Type:", "devicetype"),
    ("Platform Vendor:", "platformvendor"),
    ("Platform Name:", "platformname"),
    ("Platform Version:", "platformversion"),
    ("Browser Vendor:", "browservendor"),
    ("Browser Name:", "browsername"),
    ("Browser Version:", "browserversion"),
    ("Screen width (pixels):", "screenpixelswidth"),
    ("Screen height (pixels):", "screenpixelsheight"),
    ("Device Id:", "deviceid"),
]

# The IP intelligence properties the page shows as text, as label, property
# name and the number of decimal places to show a number to.
IP_PROPERTIES = [
    ("Registered Name:", "registeredname", None),
    ("Registered Owner:", "registeredowner", None),
    ("Registered Country:", "registeredcountry", None),
    ("IP Range Start:", "iprangestart", None),
    ("IP Range End:", "iprangeend", None),
    ("Country:", "country", None),
    ("Country Code:", "countrycode", None),
    ("Country Code 3:", "countrycode3", None),
    ("Region:", "region", None),
    ("State:", "state", None),
    ("Town:", "town", None),
    ("Latitude:", "latitude", 4),
    ("Longitude:", "longitude", 4),
    ("Areas:", "areas", None),
    ("Accuracy Radius:", "accuracyradiusmin", None),
    ("Time Zone Offset:", "timezoneoffset", None),
]

# The weighted IP intelligence properties, each shown as a list of values
# with their weightings.
WEIGHTED_IP_PROPERTIES = [
    ("Country Codes Geographical:", "countrycodesgeographical"),
    ("Country Codes Population:", "countrycodespopulation"),
]

# The lists the country choice is built from. The code at a position in the
# first names the same country as the translated name at that position in
# the second.
COUNTRY_CODES_PROPERTY = "countrycodesgeographicalall"
COUNTRY_NAMES_PROPERTY = "countrynamesgeographicalalltranslated"

# Evidence values longer than this are shortened on the page.
EVIDENCE_DISPLAY_LENGTH = 100


def values():

    """!
    The properties the page shows, as the cloud service names them. A
    request made with a licence key asks for these.
    """

    return (
        ExampleUtils.name_values(
            DeviceDetectionCloud.DATA_KEY,
            [name for _, name in DEVICE_PROPERTIES]) +
        ExampleUtils.name_values(
            IpIntelligenceCloud.DATA_KEY,
            [name for _, name, _ in IP_PROPERTIES] +
            [name for _, name in WEIGHTED_IP_PROPERTIES]) +
        ExampleUtils.name_values(
            CountriesTranslationCloud.DATA_KEY,
            [COUNTRY_CODES_PROPERTY, COUNTRY_NAMES_PROPERTY]))


def create_pipeline(logger, resource_key=None, license_key=None,
                    cloud_endpoint=None, cloud_request_origin=None):

    """!
    Create the pipeline. A cloud request engine makes one request to the
    cloud service each time flow data is processed, and the engines after
    it read the IP intelligence, translated country names and device
    detection results from the answer. The PipelineBuilder adds the
    elements that write the client-side JavaScript and set the response
    headers.

    The key in use has to carry device detection or IP intelligence
    properties. The page shows as unknown whatever the key does not carry,
    and shows no country list without the translated country names.
    """

    pipeline_settings = {
        "javascript_builder_settings": {
            # The client-side script posts the evidence it gathers to this
            # route of the example, which answers with refined results.
            "endpoint": "/json",
            "minify": True,
            # Store the client-side results as cookies, so later requests
            # carry them to the server and server-side detection uses them,
            # for example to tell the precise model of an Apple device.
            "enable_cookies": True,
        },
        # Record a processing failure in the flow data instead of raising
        # it, so the page still renders. Set to False while developing to
        # see failures straight away.
        "suppress_process_exceptions": True,
    }

    return build_pipeline(
        logger,
        values(),
        resource_key=resource_key,
        license_key=license_key,
        cloud_endpoint=cloud_endpoint,
        cloud_request_origin=cloud_request_origin,
        pipeline_settings=pipeline_settings,
        # The page runs the client-side script, so a licence key also asks
        # for the properties that script needs.
        client_side=True)


def create_app(pipeline):

    """!
    Create the Flask application that serves the example page, the
    client-side script and the client-side callback.
    """

    # Serve the files in the static folder from the root, so the stylesheet
    # is at /css and the script at /js, as in the examples for the other
    # languages.
    app = Flask(__name__, static_url_path="")

    # Take the visitor's address from the X-Forwarded-For header a reverse
    # proxy adds (for example ngrok, a load balancer or nginx), so IP
    # intelligence looks up the visitor rather than the proxy. Only do this
    # when a proxy you control sits in front of the application, as anyone
    # else can set the header to any address.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    def process():

        flowdata = pipeline.create_flowdata()

        # Add the evidence from the request, being its headers, cookies,
        # query parameters and client address, along with any form fields
        # the client-side script posts.
        flowdata.evidence.add_from_dict(webevidence(request))

        flowdata.process()

        return flowdata

    @app.route("/")
    def index():

        flowdata = process()

        response = make_response()

        # Some browsers only send User-Agent Client Hints that are asked for,
        # so set the Accept-CH header the results call for. More about this
        # at https://51degrees.com/blog/user-agent-client-hints?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_web-app.py&utm_term=index
        set_response_header(flowdata, response)

        response.set_data(render_template(
            "index.html", **page_model(flowdata)))

        return response

    # The other Pipeline APIs ship web integrations that serve the
    # client-side script at '/51Degrees.core.js', so the page refers to it by
    # that name. There is no such integration for Flask, so the example adds
    # the route itself.
    @app.route("/51Degrees.core.js")
    def core_js():

        flowdata = process()

        response = make_response(flowdata.javascriptbuilder.javascript)
        response.headers["Content-Type"] = "application/x-javascript"

        return response

    # The client-side script posts the evidence it gathers here, and gets
    # back the results of processing it as JSON.
    @app.route("/json", methods=["POST"])
    def json_results():

        flowdata = process()

        return app.response_class(
            json.dumps(flowdata.jsonbundler.json),
            mimetype="application/json")

    return app


def page_model(flowdata):

    """!
    The values the page template shows.
    """

    device = ExampleUtils.get_element(flowdata, DeviceDetectionCloud.DATA_KEY)
    ip = ExampleUtils.get_element(flowdata, IpIntelligenceCloud.DATA_KEY)
    countries = ExampleUtils.get_element(
        flowdata, CountriesTranslationCloud.DATA_KEY)

    # Look up the address the visitor typed into the form, or else the
    # visitor's own address.
    client_ip = request.args.get("client-ip", "").strip()
    if client_ip:
        lookup_ip = client_ip
        ip_message = f"Showing location data for: {client_ip}"
    else:
        lookup_ip = request.remote_addr
        ip_message = "Showing location data for your IP address"

    device_message = None
    if device is not None:
        device_message = (
            "You are using "
            f"{ExampleUtils.get_value_or_unknown(device, 'browsername')} on "
            f"{ExampleUtils.get_value_or_unknown(device, 'platformname')} "
            f"({ExampleUtils.get_value_or_unknown(device, 'devicetype')})")

    # A cell shows "Unknown" for a property with no value, whatever the
    # reason, which keeps the tables easy to read. The console example
    # prints the reason.
    ip_rows = [
        ip_row(label,
               text=ExampleUtils.get_value_or_unknown(ip, name, decimals))
        for label, name, decimals in IP_PROPERTIES]
    ip_rows += [
        weighted_row(label, ip, name)
        for label, name in WEIGHTED_IP_PROPERTIES]
    ip_rows.append(ip_row(
        "Countries (geographical):", options=country_options(countries)))

    return {
        "device_message": device_message,
        "device_rows": [
            (label, ExampleUtils.get_value_or_unknown(device, name))
            for label, name in DEVICE_PROPERTIES],
        "ip_message": ip_message,
        "lookup_ip": lookup_ip,
        "ip_rows": ip_rows,
        "evidence_rows": evidence_rows(flowdata),
    }


def ip_row(label, text=None, entries=None, options=None, not_found=False):

    """!
    One row of the IP intelligence table. The template shows whichever of
    text, the entries of a weighted property and the country options the
    row holds. It says so when the results do not include a weighted
    property, and when the list of country options is empty.
    """

    return {
        "label": label,
        "text": text,
        "entries": entries,
        "options": options,
        "not_found": not_found,
    }


def weighted_row(label, element_data, property_name):

    """!
    The row for a weighted property, holding its entries as (value,
    percentage) pairs when it has a value, and the reason the cloud service
    gave when it has none.
    """

    value = ExampleUtils.get_value(element_data, property_name)
    if value is None:
        return ip_row(label, not_found=True)
    if not value.has_value():
        return ip_row(label, text=value.no_value_message() or "(no value)")
    return ip_row(label, entries=[
        (item.get("value"), ExampleUtils.as_percentage(item["weighting"]))
        for item in value.value()
        if isinstance(item, dict) and "weighting" in item])


def country_options(countries):

    """!
    Every country as a (code, translated name) pair, in the order of the
    country code list, or an empty list when the cloud service returned no
    list. The code and name lists are aligned by position.
    """

    codes = ExampleUtils.get_value(countries, COUNTRY_CODES_PROPERTY)
    names = ExampleUtils.get_value(countries, COUNTRY_NAMES_PROPERTY)
    if (codes is None or names is None or
            not codes.has_value() or not names.has_value()):
        return []
    codes, names = codes.value(), names.value()
    if not codes or len(codes) != len(names):
        return []
    return list(zip(codes, names))


def evidence_rows(flowdata):

    """!
    The evidence the request supplied, as key and value pairs, with long
    values shortened.
    """

    rows = []
    for key, value in flowdata.evidence.get_all().items():
        text = str(value)
        if len(text) > EVIDENCE_DISPLAY_LENGTH:
            text = text[:EVIDENCE_DISPLAY_LENGTH] + "..."
        rows.append((key, text))
    return rows


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
            "https://51degrees.com/documentation/_services__cloud__resource_keys.html?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_web-app.py&utm_term=resource-key-required. "
            "A resource key carrying the device detection and IP "
            "intelligence properties this example uses can be created for "
            "free at "
            "https://configure.51degrees.com?utm_source=code&utm_medium=example&utm_campaign=pipeline-python&utm_content=examples-src-fiftyone_pipeline_examples-cloud-mixed-gettingstarted_web-app.py&utm_term=resource-key-required. "
            "Once complete, set the first environment variable named at "
            "the start of this message to the key.")
        sys.exit(1)

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
        sys.exit(1)

    create_app(pipeline).run(port=int(os.environ.get("PORT", 5000)))


if __name__ == "__main__":
    main(sys.argv[1:])
