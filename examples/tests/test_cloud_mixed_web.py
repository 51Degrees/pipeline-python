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
Runs the mixed web example against the cloud service through Flask's test
client, once with a resource key and once with a licence key. Either key
has to carry every device detection and IP intelligence property the page
shows, and the translated country names.
"""

import re

import pytest

from fiftyone_pipeline_core.logger import Logger

from fiftyone_pipeline_examples.cloud.mixed.gettingstarted_web.app import (
    create_app, create_pipeline)
from fiftyone_pipeline_examples.example_utils import ExampleUtils

from helpers import KEYS, cell_after, country_options

DESKTOP_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HEADERS = {"User-Agent": DESKTOP_CHROME}

# Google's public DNS address, registered in the United States.
LOOKUP_IP = "8.8.8.8"


@pytest.fixture(scope="module", params=KEYS)
def key(request):
    return request.param


@pytest.fixture(scope="module")
def client(key):
    pipeline = create_pipeline(
        Logger(min_level="info"),
        cloud_endpoint=ExampleUtils.get_cloud_endpoint(),
        **key)
    return create_app(pipeline).test_client()


@pytest.fixture(scope="module")
def page(client):
    response = client.get(f"/?client-ip={LOOKUP_IP}", headers=HEADERS)
    assert response.status_code == 200
    return response


def test_page_shows_both_sets_of_results(page):
    html = page.get_data(as_text=True)
    assert "Combined device detection and IP intelligence example" in html
    assert "Device detection results" in html
    assert "IP intelligence results" in html
    assert f"Showing location data for: {LOOKUP_IP}" in html
    assert "(Property Not Found)" not in html, (
        "The key does not carry every property the page shows.")


def test_page_shows_a_real_device(page):
    html = page.get_data(as_text=True)
    assert cell_after(html, "Device Type:") == "Desktop"
    device_id = cell_after(html, "Device Id:")
    assert re.fullmatch(r"\d+(-\d+)+", device_id), device_id
    assert set(device_id.split("-")) != {"0"}, (
        "The device id is all zeros, so no profile was matched.")


def test_page_shows_the_looked_up_address(page):
    html = page.get_data(as_text=True)
    assert cell_after(html, "Registered Country:") == "US"
    assert re.fullmatch(
        r"[A-Z]{2} \(\d+(\.\d+)?%\)( [A-Z]{2} \(\d+(\.\d+)?%\))*",
        cell_after(html, "Country Codes Geographical:"))


def test_page_lists_the_translated_countries(page):
    assert len(country_options(page.get_data(as_text=True))) > 200


def test_page_asks_for_client_hints(page):
    assert "Sec-CH-UA" in page.headers.get("Accept-CH", "")


def test_client_side_script_is_served(client):
    response = client.get("/51Degrees.core.js", headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/x-javascript"
    assert b"fiftyoneDegreesManager" in response.data


def test_client_side_script_gathers_the_screen_size(client):
    response = client.get("/51Degrees.core.js", headers=HEADERS)
    assert b"51D_ScreenPixelsWidth" in response.data


def test_client_side_callback_returns_both_sets_of_results(client):
    response = client.post(
        "/json", data={"client-ip": LOOKUP_IP}, headers=HEADERS)
    assert response.status_code == 200
    results = response.get_json()
    assert results["device"]["devicetype"] == "Desktop"
    assert results["ip"]["registeredcountry"] == "US"


def test_key_never_reaches_the_browser(client, page, key):
    responses = [
        page,
        client.get("/51Degrees.core.js", headers=HEADERS),
        client.post("/json", data={"client-ip": LOOKUP_IP}, headers=HEADERS),
    ]
    for secret in key.values():
        for response in responses:
            assert secret.encode() not in response.data
