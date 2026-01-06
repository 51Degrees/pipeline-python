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

import unittest

from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

from .classes.testpipeline import TestPipeline
from .classes.memorylogger import MemoryLogger
from .classes.exampleflowelement1 import ExampleFlowElement1


# from .classes.exampleflowelement2 import ExampleFlowElement2
# from .classes.stopflowdata import StopFlowData
# from .classes.errorflowdata import ErrorFlowData

######################################
# The Tests

class OldConfigPropertiesMappingTest(unittest.TestCase):

    def test_success_mapping(self):
        config = {
            "data_file_path": "path",
            "usage_sharing": False,
            "licence_keys": "test",
            "update_on_start": True,
            "verify_md5": True,
            "data_file_update_base_url": "http://127.0.0.1/"
        }

        result = self._map_properties_names(
            {
                "verify_md5": "data_update_verify_md5",
                "data_file_update_base_url": "data_update_url"
            },
            config
        )

        self.assertIn("data_update_verify_md5", result)
        self.assertIn("data_update_url", result)
        self.assertNotIn("verify_md5", result)
        self.assertNotIn("data_file_update_base_url", result)

    def test_success_mapping_args_passed_as_kwargs(self):
        def check(**kwargs):
            result = self._map_properties_names(
                {
                    "verify_md5": "data_update_verify_md5",
                    "data_file_update_base_url": "data_update_url"
                },
                kwargs
            )

            self.assertIn("data_update_verify_md5", result)
            self.assertIn("data_update_url", result)
            self.assertNotIn("verify_md5", result)
            self.assertNotIn("data_file_update_base_url", result)

        check(
            data_file_path = "path",
            usage_sharing = False,
            licence_keys = "test",
            update_on_start = True,
            verify_md5 = True,
            data_file_update_base_url = "http://127.0.0.1/"
        )

    def test_empty_config_mapping(self):
        config = {
        }

        result = self._map_properties_names(
            {
                "verify_md5": "data_update_verify_md5",
                "data_file_update_base_url": "data_update_url"
            },
            config
        )

        self.assertTrue(result == {})

    def test_config_is_None_mapping(self):
        config = None

        result = self._map_properties_names(
            {
                "verify_md5": "data_update_verify_md5",
                "data_file_update_base_url": "data_update_url"
            },
            config
        )

        self.assertIsNone(result)

    def _map_properties_names(self, mappings, arguments):
        if arguments is None:
            return arguments

        return dict(
            map(
                lambda key: (mappings[key], arguments[key]) if key in mappings else (key, arguments[key]),
                arguments
            )
        )
