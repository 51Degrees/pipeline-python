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
The cloud engines the mixed examples add to a pipeline.

The 51Degrees cloud service answers one request with a section for each
product the key in use carries. A cloud request engine makes that request,
and each engine after it reads its own section of the answer into the flow
data, so one request serves device detection, IP intelligence and the
translated country names together.

Each engine that reads a section needs a cloud request engine earlier in the
same pipeline, and the key has to carry at least one property from that
section, or the pipeline cannot be built. The cloud request engine comes
from the fiftyone_pipeline_cloudrequestengine package, which takes a
resource key or a licence key with the list of properties wanted.
"""

from fiftyone_pipeline_cloudrequestengine.cloudengine import CloudEngine
from fiftyone_pipeline_core.aspectproperty_value import AspectPropertyValue

# The cloud gives each weighted value a raw weighting from 0 to 65535.
RAW_WEIGHTING_MAX = 65535


class DeviceDetectionCloud(CloudEngine):
    """!
    Device detection results, read from the "device" section of the cloud
    response and available as flowdata.device.
    """

    DATA_KEY = "device"

    def __init__(self):

        super(DeviceDetectionCloud, self).__init__()

        self.datakey = self.DATA_KEY


class WeightedCloudEngine(CloudEngine):
    """!
    A cloud engine whose section includes weighted values. Each weighted
    value is a list of {"value", "weighting"} dictionaries with the weighting
    as a proportion from 0.0 to 1.0, the form the on-premise engines use,
    rather than the raw weighting the cloud sends.
    """

    def process_internal(self, flowdata):

        super(WeightedCloudEngine, self).process_internal(flowdata)

        element_data = flowdata.get(self.datakey)

        for name, metadata in self.properties.items():
            if "weighted" not in str(metadata.get("type", "")).lower():
                continue
            key = name.lower()
            value = element_data.contents.get(key)
            if value is None or not value.has_value():
                continue
            items = value.value()
            if not isinstance(items, list):
                continue
            element_data.contents[key] = AspectPropertyValue(
                value=[self._with_weighting(item) for item in items])

    @staticmethod
    def _with_weighting(item):

        """!
        Turn the raw weighting of one weighted entry into a proportion. An
        entry with no raw weighting is returned unchanged.
        """

        if not isinstance(item, dict) or "rawweighting" not in item:
            return item
        result = dict(item)
        result["weighting"] = result.pop("rawweighting") / RAW_WEIGHTING_MAX
        return result


class IpIntelligenceCloud(WeightedCloudEngine):
    """!
    IP intelligence results, read from the "ip" section of the cloud
    response and available as flowdata.ip.
    """

    DATA_KEY = "ip"

    def __init__(self):

        super(IpIntelligenceCloud, self).__init__()

        self.datakey = self.DATA_KEY


class CountriesTranslationCloud(WeightedCloudEngine):
    """!
    Country names translated by the cloud service, read from the
    "countrynamestranslated" section of the cloud response and available as
    flowdata.countrynamestranslated.

    The lists whose names end in "All" are aligned by position, so the
    country code at a position in countrycodesgeographicalall names the same
    country as the entry at that position in
    countrynamesgeographicalalltranslated.
    """

    DATA_KEY = "countrynamestranslated"

    def __init__(self):

        super(CountriesTranslationCloud, self).__init__()

        self.datakey = self.DATA_KEY
