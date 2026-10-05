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

"""
Runs the mixed web example against a stand-in for the cloud service, so the
page is checked with known values and without a key. The stand-in answers
in the shapes the cloud service uses.
"""

import json

import pytest
import requests

from fiftyone_pipeline_core.logger import Logger

from fiftyone_pipeline_examples.cloud.mixed.gettingstarted_web.app import (
    create_app, create_pipeline)

from helpers import cell_after, country_options

# The properties of each section of the cloud response, as name and type.
PROPERTIES = {
    "device": [
        ("DeviceType", "String"),
        ("DeviceId", "String"),
        ("HardwareVendor", "String"),
        # Two of the properties a page's client-side script needs.
        ("ScreenPixelsWidthJavaScript", "JavaScript"),
        ("SetHeaderBrowserAccept-CH", "String"),
    ],
    "ip": [
        ("RegisteredCountry", "String"),
        ("Latitude", "Single"),
        ("Areas", "WktString"),
        ("CountryCodesGeographical", "WeightedString"),
    ],
    "countrynamestranslated": [
        ("CountryCodesGeographicalAll", "Array"),
        ("CountryNamesGeographicalAllTranslated", "Array"),
    ],
}

# The values of each section. A property with no value carries the reason
# under its own name followed by "nullreason".
RESULTS = {
    "device": {
        "devicetype": "Desktop",
        "deviceid": "15364-38914-130366-18092",
        "hardwarevendor": None,
        "hardwarevendornullreason": "The hardware vendor is not known.",
    },
    "ip": {
        "registeredcountry": "US",
        "latitude": 51.415,
        "areas": {"value": "POLYGON((0 0,1 0,1 1,0 0))"},
        "countrycodesgeographical": [
            {"rawweighting": 49151, "value": "GB"},
            {"rawweighting": 16384, "value": "IE"},
        ],
    },
    "countrynamestranslated": {
        "countrycodesgeographicalall": ["GB", "IE"],
        "countrynamesgeographicalalltranslated": [
            "United Kingdom", "Ireland"],
    },
}

EVERY_SECTION = ["device", "ip", "countrynamestranslated"]


class StubResponse:

    status_code = 200
    headers = {}
    url = ""

    def __init__(self, body):
        self.text = json.dumps(body)

    def json(self):
        return json.loads(self.text)


class StubCloud:
    """
    Answers as the cloud service does for a key carrying the named sections,
    and keeps the requests it was sent.
    """

    def __init__(self, sections):
        self.sections = sections
        self.requests = []

    def request(self, method, url, data=None, headers=None):
        headers = dict(headers or {})
        self.requests.append((url, headers))

        if "accessibleproperties" in url.lower():
            return StubResponse({"Products": {
                section: {"Properties": [
                    {"Name": name, "Type": type_name}
                    for name, type_name in PROPERTIES[section]]}
                for section in self.sections}})

        if "evidencekeys" in url:
            return StubResponse(["header.user-agent", "query.client-ip"])

        # A request that names the properties it wants gets those alone,
        # and no section it named nothing from.
        named = headers.get("X-51D-Values")
        answer = {}
        for section in self.sections:
            values = {
                name: value for name, value in RESULTS[section].items()
                if named is None
                or f"{section}.{name}" in named.split(",")
                or name.endswith("nullreason")}
            if any(not name.endswith("nullreason") for name in values):
                answer[section] = values
        return StubResponse(answer)


@pytest.fixture
def cloud(monkeypatch):
    """Makes a stand-in for the cloud service answer every request."""

    def stand_in(sections):
        stub = StubCloud(sections)
        monkeypatch.setattr(requests, "request", stub.request)
        return stub

    return stand_in


def page_for(**key):
    pipeline = create_pipeline(Logger(min_level="info"), **key)
    response = create_app(pipeline).test_client().get("/?client-ip=8.8.8.8")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_page_shows_values_in_the_forms_the_cloud_sends(cloud):
    cloud(EVERY_SECTION)
    html = page_for(resource_key="a-resource-key")

    assert cell_after(html, "Device Type:") == "Desktop"
    assert cell_after(html, "Device Id:") == "15364-38914-130366-18092"
    assert cell_after(html, "Registered Country:") == "US"
    # A number is shown to four decimal places.
    assert cell_after(html, "Latitude:") == "51.4150"
    # An area arrives inside an object, and the page shows its text.
    assert cell_after(html, "Areas:") == "POLYGON((0 0,1 0,1 1,0 0))"
    # A raw weighting from 0 to 65535 is shown as a percentage.
    assert cell_after(html, "Country Codes Geographical:") == \
        "GB (75%) IE (25%)"
    assert country_options(html) == [
        ("GB", "United Kingdom"), ("IE", "Ireland")]


def test_page_says_why_a_value_is_missing(cloud):
    cloud(EVERY_SECTION)
    html = page_for(resource_key="a-resource-key")

    assert cell_after(html, "Hardware Vendor:") == \
        "Unknown (The hardware vendor is not known.)"
    assert cell_after(html, "Platform Name:") == (
        "Unknown (the property 'platformname' is not in the results, so "
        "the key in use does not include it)")


def test_page_works_without_the_translated_country_names(cloud):
    cloud(["device", "ip"])
    html = page_for(resource_key="a-resource-key")

    assert cell_after(html, "Device Type:") == "Desktop"
    assert cell_after(html, "Registered Country:") == "US"
    assert cell_after(html, "Countries (geographical):") == \
        "(no country list available)"
    assert country_options(html) == []


def test_page_works_with_only_one_of_the_products(cloud):
    cloud(["device"])
    html = page_for(resource_key="a-resource-key")

    assert cell_after(html, "Device Type:") == "Desktop"
    assert cell_after(html, "Registered Country:") == (
        "Unknown (the property 'registeredcountry' is not in the results, "
        "so the key in use does not include it)")


def test_key_carrying_neither_product_is_refused(cloud):
    cloud(["countrynamestranslated"])
    with pytest.raises(ValueError, match="neither the device detection"):
        page_for(resource_key="a-resource-key")


def test_resource_key_goes_in_the_address(cloud):
    stub = cloud(EVERY_SECTION)
    page_for(resource_key="a-resource-key")

    url, headers = stub.requests[-1]
    assert url.endswith("/a-resource-key.json?")
    assert "X-51D-License-Key" not in headers
    assert "X-51D-Values" not in headers


def test_origin_can_be_set_for_a_key_limited_to_particular_domains(cloud):
    stub = cloud(EVERY_SECTION)
    page_for(resource_key="a-resource-key", cloud_request_origin="example.org")

    assert all(
        headers.get("Origin") == "example.org"
        for _, headers in stub.requests)


def test_licence_key_names_the_properties_it_wants(cloud):
    stub = cloud(EVERY_SECTION)
    html = page_for(license_key="a-licence-key")

    assert cell_after(html, "Device Type:") == "Desktop"
    assert cell_after(html, "Registered Country:") == "US"
    assert country_options(html) == [
        ("GB", "United Kingdom"), ("IE", "Ireland")]

    # The licence key travels in a header of every request, and the request
    # for results goes to the address that takes no key.
    assert all(
        headers.get("X-51D-License-Key") == "a-licence-key"
        for _, headers in stub.requests)
    url, headers = stub.requests[-1]
    assert url.endswith("/json")
    assert "a-licence-key" not in url
    named = headers["X-51D-Values"].split(",")
    # The properties the page shows.
    for value in ("device.devicetype", "device.deviceid",
                  "ip.registeredcountry", "ip.countrycodesgeographical",
                  "countrynamestranslated.countrycodesgeographicalall"):
        assert value in named
    # The properties the client-side script needs, which the licence
    # entitles and the page does not show.
    assert "device.screenpixelswidthjavascript" in named
    assert "device.setheaderbrowseraccept-ch" in named


def test_licence_key_gets_an_engine_only_for_what_it_asks_for(cloud):
    # The licence is entitled to the device section alone, so nothing is
    # asked of the others and the page shows them as unknown.
    cloud(["device"])
    html = page_for(license_key="a-licence-key")

    assert cell_after(html, "Device Type:") == "Desktop"
    assert cell_after(html, "Registered Country:").startswith("Unknown (")
    assert country_options(html) == []


def test_licence_key_never_reaches_the_page(cloud):
    cloud(EVERY_SECTION)
    assert "a-licence-key" not in page_for(license_key="a-licence-key")
