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
Checks how the examples turn cloud values into text, with values in the
shapes the cloud service sends. These need no resource key.
"""

from fiftyone_pipeline_core.aspectproperty_value import AspectPropertyValue

from fiftyone_pipeline_examples.cloud.engines import WeightedCloudEngine
from fiftyone_pipeline_examples.example_utils import ExampleUtils


class Results:
    """Stands in for an engine's results, holding one value per property."""

    def __init__(self, values):
        self.values = values

    def get(self, name):
        if name not in self.values:
            raise KeyError(name)
        return self.values[name]


def test_raw_weighting_becomes_a_proportion():
    assert WeightedCloudEngine._with_weighting(
        {"value": "GB", "rawweighting": 65535}) == {
            "value": "GB", "weighting": 1.0}
    half = WeightedCloudEngine._with_weighting(
        {"value": "FR", "rawweighting": 32767})
    assert abs(half["weighting"] - 0.5) < 0.0001
    assert "rawweighting" not in half


def test_entry_without_raw_weighting_is_unchanged():
    entry = {"value": "GB", "weighting": 0.25}
    assert WeightedCloudEngine._with_weighting(entry) == entry
    assert WeightedCloudEngine._with_weighting("GB") == "GB"


def test_weighted_value_shows_each_entry_with_its_percentage():
    assert ExampleUtils.format_value([
        {"value": "GB", "weighting": 0.75},
        {"value": "IE", "weighting": 0.25},
    ]) == "GB (75%), IE (25%)"


def test_value_wrapped_in_an_object_shows_the_value():
    assert ExampleUtils.format_value(
        {"value": "POLYGON((0 0,1 0,1 1,0 0))"}) == "POLYGON((0 0,1 0,1 1,0 0))"


def test_list_and_number_formats():
    assert ExampleUtils.format_value(["iPhone", "iPhone 15"]) == \
        "iPhone, iPhone 15"
    assert ExampleUtils.format_value(51.4150001, 4) == "51.4150"
    assert ExampleUtils.format_value(True) == "True"


def test_each_reason_for_no_value_reads_differently():
    results = Results({
        "devicetype": AspectPropertyValue(None, "Desktop"),
        "browsername": AspectPropertyValue("The key is not entitled."),
    })
    assert ExampleUtils.get_human_readable(results, "devicetype") == "Desktop"
    assert ExampleUtils.get_human_readable(results, "browsername") == \
        "Unknown (The key is not entitled.)"
    assert ExampleUtils.get_human_readable(results, "platformname") == (
        "Unknown (the property 'platformname' is not in the results, so "
        "the key in use does not include it)")
    assert ExampleUtils.get_human_readable(None, "devicetype").startswith(
        "Unknown (the property")


def test_value_or_unknown():
    results = Results({
        "devicetype": AspectPropertyValue(None, "Desktop"),
        "browsername": AspectPropertyValue("No value."),
    })
    assert ExampleUtils.get_value_or_unknown(results, "devicetype") == \
        "Desktop"
    assert ExampleUtils.get_value_or_unknown(results, "browsername") == \
        "Unknown"
    assert ExampleUtils.get_value_or_unknown(results, "platformname") == \
        "Unknown"
