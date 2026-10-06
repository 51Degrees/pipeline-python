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
Runs the mixed console example against the cloud service, once with a
resource key and once with a licence key. Either key has to carry every
device detection and IP intelligence property the example prints.
"""

import pytest

from fiftyone_pipeline_core.logger import Logger

from fiftyone_pipeline_examples.cloud.mixed.gettingstarted_console import (
    GettingStartedConsole, create_pipeline)
from fiftyone_pipeline_examples.example_utils import ExampleUtils

from helpers import KEYS

SEPARATOR = "=" * 79


@pytest.fixture(scope="module", params=KEYS)
def output(request):
    lines = []
    pipeline = create_pipeline(
        Logger(min_level="info"),
        cloud_endpoint=ExampleUtils.get_cloud_endpoint(),
        **request.param)
    GettingStartedConsole().run(pipeline, lines.append)
    return "\n".join(lines)


def test_each_entry_has_device_and_ip_results(output):
    entries = len(GettingStartedConsole.EVIDENCE)
    assert output.count("Device Detection Results:") == entries
    assert output.count("IP Intelligence Results:") == entries


def test_every_property_is_in_the_results(output):
    assert "is not in the results" not in output, (
        "The key does not carry every property the example prints, so the "
        "example cannot show it working.")


def test_desktop_in_the_united_kingdom(output):
    first = output.split(SEPARATOR)[1]
    assert "\tDevice Type: Desktop\n" in first
    assert "\tCountry Code: GB\n" in first


def test_find_out_more_comes_last(output):
    last = output.split(SEPARATOR)[-1]
    assert last.startswith("\nFind out more:")
    for _, url in GettingStartedConsole.FIND_OUT_MORE:
        assert url in last
