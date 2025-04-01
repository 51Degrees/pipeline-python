# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2025 51 Degrees Mobile Experts Limited, Davidson House,
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

from typing import Type
import unittest

from fiftyone_pipeline_cloudrequestengine.cloudrequestengine import CloudRequestEngine
from .mockrequestclient import MockRequestClient
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder


class CloudRequestEngineTestsBase(unittest.TestCase):
    def properties_contain_name(self, properties, name):

        if type(properties) == type({}):
            for propertyKey, property in properties.items():
                if (property["name"].lower() == name.lower()):
                    return True
        else:
            for property in properties:
                if (property["Name"].lower() == name.lower()):
                    return True

        return False;
    
    def mock_http(self, server_unavailable=False, **kwargs):
        return MockRequestClient(
            server_unavailable=server_unavailable,
            **kwargs,
        )
