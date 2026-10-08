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

"""Helpers the example tests share."""

import html
import re

import pytest

from fiftyone_pipeline_examples.example_utils import ExampleUtils

# The ways a test can reach the cloud service, as the keyword arguments the
# examples' create_pipeline takes. Each is skipped when its key is not set.
KEYS = [
    pytest.param(
        {"resource_key": ExampleUtils.get_resource_key()},
        id="resource key",
        marks=pytest.mark.skipif(
            not ExampleUtils.get_resource_key(),
            reason=f"Set {ExampleUtils.RESOURCE_KEY_ENV_VAR} to a resource "
                   "key carrying device detection and IP intelligence "
                   "properties to run the cloud tests with a resource "
                   "key.")),
    pytest.param(
        {"license_key": ExampleUtils.get_license_key()},
        id="licence key",
        marks=pytest.mark.skipif(
            not ExampleUtils.get_license_key(),
            reason=f"Set {ExampleUtils.LICENSE_KEY_ENV_VAR} to a licence "
                   "key entitled to device detection and IP intelligence "
                   "properties to run the cloud tests with a licence "
                   "key.")),
]


def cell_after(page, label):
    """
    The text a browser shows in the table cell after the one holding label,
    or None when the page has no such row.
    """

    match = re.search(
        rf"<td[^>]*>{re.escape(label)}</td>\s*<td[^>]*>(.*?)</td>", page,
        re.S)
    if match is None:
        return None
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def country_options(page):
    """The (code, name) pairs of the country list on the page."""

    return re.findall(r'<option value="([A-Z]{2})">([^<]+)</option>', page)
