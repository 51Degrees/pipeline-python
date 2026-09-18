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

from flask import Flask, request

from fiftyone_pipeline_core.web import webevidence


class WebEvidenceTests(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)

    def test_form_values_are_query_evidence(self):
        """The client script posts the results of its snippets, the session
        id and the sequence as a form body. Each form field is query
        evidence, as in the other languages' web integrations, or none of
        that reaches the pipeline."""

        with self.app.test_request_context(
                "/json", method="POST",
                data={"51D_profile": "12-34", "session-id": "abc"}):
            evidence = webevidence(request)

        self.assertEqual("12-34", evidence.get("query.51D_profile"))
        self.assertEqual("abc", evidence.get("query.session-id"))

    def test_form_value_replaces_query_string_value(self):
        """Form fields are added after the query string, so the value the
        script sent in its body is the one used."""

        with self.app.test_request_context(
                "/json?sequence=1&mark=url", method="POST",
                data={"sequence": "2"}):
            evidence = webevidence(request)

        self.assertEqual("2", evidence.get("query.sequence"))
        self.assertEqual("url", evidence.get("query.mark"))

    def test_get_request_reads_the_query_string(self):
        with self.app.test_request_context("/page?mark=url"):
            evidence = webevidence(request)

        self.assertEqual("url", evidence.get("query.mark"))

    def test_non_form_body_is_not_read(self):
        """Only a form body carries evidence. A JSON body is left alone."""

        with self.app.test_request_context(
                "/json", method="POST", json={"mark": "body"}):
            evidence = webevidence(request)

        self.assertNotIn("query.mark", evidence)


if __name__ == "__main__":
    unittest.main()
