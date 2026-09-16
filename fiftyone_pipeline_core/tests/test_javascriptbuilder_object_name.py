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
The client side object's name can be set in the builder's settings
(obj_name) or per request (query.fod-js-object-name). The name is written
into the script as a variable name, a session storage key and a property
name, so these tests check that a different name works, and that a name
which is not a JavaScript identifier is never written into the script.

The script is checked with "node --check" and run in Node with a minimal
stand in for a browser (object_name_harness.js). Both need Node on the path,
which every GitHub hosted runner has.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from parameterized import parameterized

from fiftyone_pipeline_core.constants import Constants
from fiftyone_pipeline_core.javascriptbuilder import JavascriptBuilderElement
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

from .classes.memorylogger import MemoryLogger
from .test_javascriptbuilder import TestEngine

NODE = shutil.which("node")
HARNESS = os.path.join(os.path.dirname(__file__), "object_name_harness.js")


def _render(settings=None, evidence=None, logger=None):
    """Render the script for one request and return it."""

    builder = PipelineBuilder(
        {"javascript_builder_settings": settings or {"minify": False}})
    if logger is not None:
        builder.add_logger(logger)
    pipeline = builder.add(TestEngine()).build()
    flowdata = pipeline.create_flowdata()
    for key, value in (evidence or {}).items():
        flowdata.evidence.add(key, value)
    flowdata.process()
    return flowdata.javascriptbuilder.javascript


def _write(script):
    handle, path = tempfile.mkstemp(suffix=".js")
    with os.fdopen(handle, "w", encoding="utf-8") as f:
        f.write(script)
    return path


def _node(*args):
    return subprocess.run(
        [NODE] + list(args), capture_output=True, text=True, timeout=60)


def _declared_names(script):
    return re.findall(
        r"\bvar\s+([^\s=]*)\s*=\s*new\s+fiftyoneDegreesManager\b", script)


@unittest.skipUnless(NODE, "Node is needed to parse and run the script")
class JavaScriptBuilderObjectNameTests(unittest.TestCase):

    def assert_parses(self, script):
        path = _write(script)
        try:
            result = _node("--check", path)
        finally:
            os.remove(path)
        self.assertEqual(
            0, result.returncode,
            "the rendered script does not parse: " + result.stderr)

    def run_script(self, script, name):
        path = _write(script)
        try:
            result = _node(HARNESS, path, name, "test.normal")
        finally:
            os.remove(path)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def assert_uses_name(self, script, name):
        self.assertEqual([name], _declared_names(script))
        self.assertIsNone(
            re.search(r"\bvar\s+fod\b", script) if name != "fod" else None,
            "the default name must not be declared as well")
        self.assertIn('var sessionKey = "' + name + '";', script)
        self.assertIn('window["' + name + 'Evidence"]', script)
        self.assertIn('typeof window["' + name + '"]', script)

    @parameterized.expand([
        ["settings", {"obj_name": "myFod", "minify": False}, {}],
        ["evidence", {"minify": False},
         {Constants.EVIDENCE_OBJECT_NAME: "myFod"}],
    ])
    def test_valid_name_is_used(self, _, settings, evidence):
        """A valid name from the settings or from the page request is
        declared, used as the storage key and in the evidence lookup, and
        the script parses and creates that object."""

        script = _render(settings, evidence)

        self.assert_uses_name(script, "myFod")
        self.assert_parses(script)

        result = self.run_script(script, "myFod")
        self.assertIsNone(result["error"])
        self.assertTrue(result["exists"], "window.myFod was not created")
        self.assertEqual("function", result["complete"])
        self.assertEqual("function", result["onChange"])
        self.assertEqual("function", result["refresh"])
        self.assertEqual("true", result["value"])
        self.assertEqual(["myFod"], result["globals"])

    def test_valid_name_from_evidence_minified(self):
        """The minified script declares the requested name and parses."""

        script = _render(
            {"minify": True}, {Constants.EVIDENCE_OBJECT_NAME: "myFod"})

        self.assertEqual(["myFod"], _declared_names(script))
        self.assert_parses(script)

    @parameterized.expand([
        ["statement", "a;b", True],
        ["leading_digit", "9bad", True],
        ["quote", 'x"y', True],
        ["empty", "", False],
        # A reserved word is also an ordinary word in the script's comments,
        # so only the places the name is written are checked for it.
        ["reserved_word", "class", False],
    ])
    def test_invalid_name_from_evidence_is_ignored(
            self, _, name, check_text):
        """A requested name that is not a JavaScript identifier is not
        written into the script. The configured name is used, the script
        parses and runs, and a warning is logged."""

        logger = MemoryLogger("warning")
        script = _render(
            {"minify": False},
            {Constants.EVIDENCE_OBJECT_NAME: name},
            logger)

        self.assert_uses_name(script, "fod")
        self.assert_parses(script)

        # The requested value is still one of the request's query values,
        # which the script carries as data inside a JSON string. Every other
        # line must be free of it.
        if check_text:
            other_lines = [
                line for line in script.splitlines()
                if "var renderedParameters" not in line]
            self.assertFalse(
                any(name in line for line in other_lines),
                "the requested name was written into the script")

        result = self.run_script(script, "fod")
        self.assertIsNone(result["error"])
        self.assertTrue(result["exists"])
        self.assertEqual(["fod"], result["globals"])

        warnings = [
            entry["message"] for entry in logger.memory_log
            if entry["level"] == "warning"
            and Constants.EVIDENCE_OBJECT_NAME in entry["message"]]
        self.assertEqual(1, len(warnings), str(logger.memory_log))
        if check_text:
            self.assertNotIn(name, warnings[0])

    def test_invalid_name_from_evidence_uses_configured_name(self):
        """The fallback is the configured name, not always 'fod'."""

        script = _render(
            {"obj_name": "myFod", "minify": False},
            {Constants.EVIDENCE_OBJECT_NAME: "9bad"})

        self.assert_uses_name(script, "myFod")
        self.assert_parses(script)


class JavaScriptBuilderObjectNameSettingTests(unittest.TestCase):

    @parameterized.expand([
        ["statement", "a;b"],
        ["leading_digit", "9bad"],
        ["quote", 'x"y'],
        ["empty", ""],
        ["reserved_word", "var"],
        ["not_a_string", 5],
    ])
    def test_invalid_configured_name_is_refused(self, _, name):
        """An invalid name in the settings is refused when the builder is
        created."""

        with self.assertRaises(ValueError):
            JavascriptBuilderElement({"obj_name": name})

    @parameterized.expand([
        ["plain", "myFod"],
        ["underscore", "_fod"],
        ["dollar", "$fod9"],
    ])
    def test_valid_configured_name_is_accepted(self, _, name):
        element = JavascriptBuilderElement({"obj_name": name})
        self.assertEqual(name, element.settings["_objName"])
