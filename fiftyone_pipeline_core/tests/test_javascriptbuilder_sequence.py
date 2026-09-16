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
The script must parse whatever the pipeline holds. The sequence is written
into the script as bare code and the session id inside quotes, and a pipeline
built without a SequenceElement, for example from a configuration file that
does not list one, passes the query string's values, or nothing at all,
straight to the builder.

The script is checked with "node --check", which needs Node on the path.
Every GitHub hosted runner has it.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

from parameterized import parameterized

from fiftyone_pipeline_core import javascriptbuilder
from fiftyone_pipeline_core.javascriptbuilder import JavascriptBuilderElement
from fiftyone_pipeline_core.jsonbundler import JSONBundlerElement
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

NODE = shutil.which("node")


def _render(evidence=None, minify=False, sequence_element=False):
    """Render the script. With sequence_element False the pipeline has only
    the JSON bundler and the JavaScript builder."""

    settings = {"javascript_builder_settings": {"minify": minify}}
    if not sequence_element:
        settings["add_javascript_builder"] = False
    builder = PipelineBuilder(settings)
    if not sequence_element:
        builder.add(JSONBundlerElement())
        builder.add(JavascriptBuilderElement({"minify": minify}))
    pipeline = builder.build()
    flowdata = pipeline.create_flowdata()
    for key, value in (evidence or {}).items():
        flowdata.evidence.add(key, value)
    flowdata.process()
    return flowdata.javascriptbuilder.javascript


def _line(script, name):
    lines = [line.strip() for line in script.splitlines()
             if re.match(r"\s*var " + name + r"\s*=", line)]
    return lines


class JavaScriptBuilderSequenceTests(unittest.TestCase):

    def assert_parses(self, script):
        if not NODE:
            self.skipTest("Node is needed to parse the script")
        handle, path = tempfile.mkstemp(suffix=".js")
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            f.write(script)
        try:
            result = subprocess.run(
                [NODE, "--check", path],
                capture_output=True, text=True, timeout=60)
        finally:
            os.remove(path)
        self.assertEqual(
            0, result.returncode,
            "the rendered script does not parse: " + result.stderr)

    @parameterized.expand([["unminified", False], ["minified", True]])
    def test_script_parses_without_sequence_element(self, _, minify):
        """With no SequenceElement and no query evidence the script is
        rendered with sequence 1 and an empty session id, and parses."""

        script = _render(minify=minify)

        self.assert_parses(script)
        if not minify:
            self.assertEqual(["var sequence = 1;"], _line(script, "sequence"))
            self.assertEqual(
                ['var sessionId = "";'], _line(script, "sessionId"))

    @parameterized.expand([
        ["text", "abc"],
        ["statement", "1;b"],
        ["empty", ""],
        ["decimal", "1.5"],
        ["underscore", "1_0"],
        ["too_large", "2147483648"],
    ])
    def test_unusable_sequence_from_query_becomes_one(self, _, value):
        """A query.sequence the builder cannot use as a whole number is
        rendered as 1, which is what the .NET builder does, so the script
        parses and nothing else is written in its place."""

        script = _render({
            "query.session-id": "abc",
            "query.sequence": value})

        self.assertEqual(["var sequence = 1;"], _line(script, "sequence"))
        self.assert_parses(script)

    @parameterized.expand([
        ["text", "7", 7],
        ["spaces", " 7 ", 7],
        ["negative", "-2", -2],
        ["number", 12, 12],
    ])
    def test_usable_sequence_from_query_is_rendered(self, _, value, expected):
        script = _render({
            "query.session-id": "abc",
            "query.sequence": value})

        self.assertEqual(
            ["var sequence = " + str(expected) + ";"],
            _line(script, "sequence"))
        self.assert_parses(script)

    def test_session_id_from_query_is_rendered(self):
        script = _render({"query.session-id": "abc-123"})

        self.assertEqual(
            ['var sessionId = "abc-123";'], _line(script, "sessionId"))
        self.assert_parses(script)

    def test_sequence_element_still_sets_the_sequence(self):
        """With the SequenceElement the first request is sequence 1 and the
        next one carries the number the element worked out."""

        first = _render(sequence_element=True)
        self.assertEqual(["var sequence = 1;"], _line(first, "sequence"))
        self.assert_parses(first)

        second = _render(
            {"query.session-id": "abc", "query.sequence": "1"},
            sequence_element=True)
        self.assertEqual(["var sequence = 2;"], _line(second, "sequence"))
        self.assert_parses(second)

    @parameterized.expand([
        ["none", None, 1],
        ["true", True, 1],
        ["float", 2.0, 1],
        ["small", -2 ** 31, -2 ** 31],
        ["too_small", -2 ** 31 - 1, 1],
        ["large", 2 ** 31 - 1, 2 ** 31 - 1],
        ["plus", "+3", 3],
    ])
    def test_get_sequence(self, _, value, expected):
        self.assertEqual(expected, javascriptbuilder.get_sequence(value))
