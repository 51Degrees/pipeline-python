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
        ["negative", "-1"],
        ["zero", "0"],
        ["too_large", "99999999999"],
        ["empty", ""],
        ["statement", "1;b"],
        ["decimal", "1.5"],
        ["underscore", "1_0"],
        ["just_too_large", "2147483648"],
        ["file_separator", chr(0x1C) + "5"],
        ["group_separator", chr(0x1D) + "5"],
        ["record_separator", chr(0x1E) + "5"],
        ["unit_separator", chr(0x1F) + "5"],
        ["trailing_file_separator", "5" + chr(0x1C)],
        ["null", chr(0) + "5"],
        ["no_break_space", chr(0xA0) + "5"],
        ["line_separator", chr(0x2028) + "5"],
        ["arabic_indic_digit", chr(0x665)],
        ["full_width_digit", chr(0xFF15)],
        ["five_thousand_digits", "9" * 5000],
        ["plus_alone", "+"],
        ["spaces_alone", "   "],
        ["zeros", "0000"],
    ])
    def test_unusable_sequence_from_query_becomes_one(self, _, value):
        """A query.sequence that is not a positive 32 bit integer is rendered
        as 1, as the pipeline specification says, so the script parses and
        nothing else is written in its place."""

        script = _render({
            "query.session-id": "abc",
            "query.sequence": value})

        self.assertEqual(["var sequence = 1;"], _line(script, "sequence"))
        self.assert_parses(script)

    @parameterized.expand([
        ["text", "abc"],
        ["negative", "-1"],
        ["zero", "0"],
        ["too_large", "99999999999"],
        ["empty", ""],
        ["largest", "2147483647"],
        ["file_separator", chr(0x1C) + "5"],
        ["unit_separator", chr(0x1F) + "5"],
        ["trailing_file_separator", "5" + chr(0x1C)],
        ["five_thousand_digits", "9" * 5000],
        ["plus_alone", "+"],
    ])
    def test_unusable_sequence_with_sequence_element_becomes_one(
            self, _, value):
        """With the SequenceElement the value that reaches the script is the
        one the element works out. A query.sequence that is not a positive 32
        bit integer is treated as no sequence, so the request is sequence 1
        rather than failing. The largest sequence has no next value, so the
        builder renders 1 for it as well."""

        script = _render(
            {"query.session-id": "abc", "query.sequence": value},
            sequence_element=True)

        self.assertEqual(["var sequence = 1;"], _line(script, "sequence"))
        self.assertEqual(
            ['var sessionId = "abc";'], _line(script, "sessionId"))
        self.assert_parses(script)

    @parameterized.expand([
        ["text", "7", 7],
        ["spaces", " 7 ", 7],
        ["number", 12, 12],
        ["largest", "2147483647", 2147483647],
    ])
    def test_usable_sequence_from_query_is_rendered(self, _, value, expected):
        script = _render({
            "query.session-id": "abc",
            "query.sequence": value})

        self.assertEqual(
            ["var sequence = " + str(expected) + ";"],
            _line(script, "sequence"))
        self.assert_parses(script)

    @parameterized.expand([
        ["without_sequence_element", False],
        ["with_sequence_element", True],
    ])
    def test_session_id_from_query_is_rendered(self, _, sequence_element):
        script = _render(
            {"query.session-id": "abc-123"},
            sequence_element=sequence_element)

        self.assertEqual(
            ['var sessionId = "abc-123";'], _line(script, "sessionId"))
        self.assert_parses(script)

    def test_longest_session_id_is_rendered(self):
        session_id = "a" * 64
        script = _render({"query.session-id": session_id})

        self.assertEqual(
            ['var sessionId = "' + session_id + '";'],
            _line(script, "sessionId"))
        self.assert_parses(script)

    @parameterized.expand([
        [name + "_" + ("with" if element else "without")
         + "_sequence_element", value, check_text, element]
        for name, value, check_text in [
            ["quote", 'a"b', True],
            ["backslash", "a\\b", True],
            ["end_of_script", "</script>", True],
            ["too_long", "a" * 65, True],
            ["not_ascii", "café", True],
            # The template's own text holds "a b" and "ab", so for these two
            # only the rendered session id is read.
            ["space", "a b", False],
            ["new_line", "ab\n", False],
        ]
        for element in [False, True]
    ])
    def test_unsafe_session_id_is_rendered_empty(
            self, _, value, check_text, sequence_element):
        """The session id is written inside quotes without any escaping, so
        one that is not 1 to 64 ASCII letters, digits and hyphens is rendered
        as an empty string, as the pipeline specification says. The
        SequenceElement keeps a session id it is given, so the check is the
        builder's in both pipelines."""

        script = _render(
            {"query.session-id": value},
            sequence_element=sequence_element)

        self.assertEqual(
            ['var sessionId = "";'], _line(script, "sessionId"))
        if check_text:
            self.assertNotIn(value, script)
        self.assert_parses(script)

    def test_generated_session_id_is_rendered(self):
        """The SequenceElement creates a session id on the first request,
        and that id is safe to render."""

        script = _render(sequence_element=True)

        lines = _line(script, "sessionId")
        self.assertEqual(1, len(lines))
        self.assertRegex(lines[0], r'^var sessionId = "[A-Za-z0-9-]{1,64}";$')
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
        ["zero", 0, 1],
        ["negative", -1, 1],
        ["smallest", 1, 1],
        ["largest", 2 ** 31 - 1, 2 ** 31 - 1],
        ["too_large", 2 ** 31, 1],
        ["plus", "+3", 3],
        ["negative_text", "-3", 1],
        ["file_separator", chr(0x1C) + "5", 1],
        ["group_separator", chr(0x1D) + "5", 1],
        ["record_separator", chr(0x1E) + "5", 1],
        ["unit_separator", chr(0x1F) + "5", 1],
        ["trailing_unit_separator", "5" + chr(0x1F), 1],
        ["ascii_spaces", "\t\n 5 \r\n", 5],
        ["no_break_space", chr(0xA0) + "5", 1],
        ["arabic_indic_digit", chr(0x665), 1],
        ["five_thousand_digits", "9" * 5000, 1],
        ["leading_zeros", "007", 7],
        ["zeros", "0000", 1],
        ["bytes", b"5", 1],
        ["list", [], 1],
    ])
    def test_get_sequence(self, _, value, expected):
        self.assertEqual(expected, javascriptbuilder.get_sequence(value))

    def test_any_sequence_value_gives_a_usable_number(self):
        """A page can put anything at all in query.sequence, so the
        builder has to answer a whole number from 1 to 2147483647 for
        every value and never raise. Each character below the space is
        tried on its own and on both sides of a digit, because some of
        them read as a space to a regular expression and not to int(),
        and a very long run of digits cannot be read as a number at
        all."""

        values = ["", " ", "+", "-", "+-1", "5", "abc", "1.5", "0",
                  "-1", "9" * 5000, chr(0x665), chr(0xFF15),
                  chr(0xA0) + "5", chr(0x2000) + "5",
                  chr(0x2028) + "5", None, True, False, 2.0, 0, -1,
                  2 ** 31, 2 ** 64, b"5", [], {}, object()]
        for code in range(0x20):
            character = chr(code)
            values += [character, character + "5", "5" + character]

        for value in values:
            with self.subTest(value=repr(value)):
                sequence = javascriptbuilder.get_sequence(value)
                self.assertIsInstance(sequence, int)
                self.assertNotIsInstance(sequence, bool)
                self.assertGreaterEqual(sequence, 1)
                self.assertLessEqual(sequence, 2 ** 31 - 1)

    def test_any_sequence_value_reaches_the_script(self):
        """The same kinds of value go through both pipelines, so a value
        the builder cannot read is answered with a script rather than an
        error. U+001C to U+001F are the ones that used to raise."""

        values = [chr(0x1C) + "5", chr(0x1D) + "5", chr(0x1E) + "5",
                  chr(0x1F) + "5", "5" + chr(0x1C), chr(0) + "5",
                  "9" * 5000, "+", "   "]
        for value in values:
            for element in [False, True]:
                with self.subTest(value=repr(value), element=element):
                    script = _render(
                        {"query.session-id": "abc",
                         "query.sequence": value},
                        sequence_element=element)
                    self.assertEqual(
                        ["var sequence = 1;"],
                        _line(script, "sequence"))

    @parameterized.expand([
        ["plain", "abc-123", "abc-123"],
        ["none", None, ""],
        ["empty", "", ""],
        ["number", 5, ""],
        ["too_long", "a" * 65, ""],
        ["quote", 'a"b', ""],
    ])
    def test_get_session_id(self, _, value, expected):
        self.assertEqual(expected, javascriptbuilder.get_session_id(value))
