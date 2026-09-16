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

# The values the JavaScript builder hands to the client script template.
# Every language's builder renders the same template and is expected to
# produce the same script, with the .NET builder as the reference, so these
# tests pin the values the .NET builder passes. They read the values handed
# to the template rather than the rendered text, so they do not depend on
# how a given template revision names its variables.

import json
import unittest
from unittest import mock

from fiftyone_pipeline_core import javascriptbuilder
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder


class _Captured:
    """Records the variables of the last render and renders nothing."""

    def __init__(self):
        self.variables = None

    def render(self, template, variables):
        self.variables = dict(variables)
        return ""


def _render_variables(evidence, settings=None):
    js_settings = {"minify": False, "endpoint": "/json"}
    js_settings.update(settings or {})
    pipeline = PipelineBuilder(
        {"javascript_builder_settings": js_settings}).build()
    flowdata = pipeline.create_flowdata()
    for key, value in evidence.items():
        flowdata.evidence.add(key, value)
    captured = _Captured()
    with mock.patch.object(
            javascriptbuilder.chevron, "render", captured.render):
        flowdata.process()
    return captured.variables


class JavaScriptBuilderVariablesTests(unittest.TestCase):

    def test_parameters_are_url_encoded(self):
        """The script joins the rendered parameters into its request body
        as they are, so each key and value must already be encoded, as the
        .NET builder does. An unencoded '&' or '=' in a value would split
        it into extra body fields, and a space would not survive."""

        variables = _render_variables({
            "header.host": "example.com",
            "query.mark": "a b&c=d~e",
            "query.x y": "1",
        })

        parameters = json.loads(variables["_parameters"])
        self.assertEqual(
            {"mark": "a+b%26c%3Dd%7Ee", "x+y": "1"}, parameters)

    def test_parameters_are_written_without_spaces(self):
        """The .NET builder writes the parameters object with no spaces
        between the parts, so the rendered script is the same text."""

        variables = _render_variables({
            "header.host": "example.com",
            "query.a": "1",
            "query.b": "2",
        })

        self.assertEqual('{"a":"1","b":"2"}', variables["_parameters"])

    def test_parameters_leave_out_session_id_and_sequence(self):
        """Both are appended by the script itself, after it takes the record
        of a request's inputs."""

        variables = _render_variables({
            "header.host": "example.com",
            "query.session-id": "abc",
            "query.sequence": 1,
            "query.mark": "kept",
        })

        self.assertEqual(
            {"mark": "kept"}, json.loads(variables["_parameters"]))

    def test_url_carries_no_query_string(self):
        """The callback URL is the protocol, the host and the endpoint and
        nothing more, as in the .NET builder. The query values reach the
        callback in the request body, through the parameters. Adding them to
        the URL as well sent the session id and the sequence twice, and wrote
        header and server values, such as the host and the protocol, into
        the URL as if they were query values."""

        variables = _render_variables({
            "header.host": "example.com",
            "header.protocol": "https",
            "query.session-id": "abc",
            "query.sequence": 1,
            "query.mark": "kept",
        })

        self.assertEqual("https://example.com/json", variables["_url"])
        self.assertTrue(variables["_updateEnabled"])

    def test_url_has_one_slash_between_host_and_endpoint(self):
        """As in the .NET builder, a slash is added where neither the host
        nor the endpoint has one, and one is dropped where both do."""

        without = _render_variables(
            {"header.host": "example.com"}, {"endpoint": "json"})
        both = _render_variables(
            {}, {"host": "example.com/", "endpoint": "/json"})

        self.assertEqual("https://example.com/json", without["_url"])
        self.assertEqual("https://example.com/json", both["_url"])

    def test_parameter_name_holding_a_dot_is_kept_whole(self):
        variables = _render_variables(
            {"header.host": "example.com", "query.a.b": "1"})

        self.assertEqual(
            {"a.b": "1"}, json.loads(variables["_parameters"]))

    def test_url_keeps_a_query_string_given_in_the_endpoint(self):
        """A query string the integrator put in the endpoint setting is
        part of the endpoint and is kept as given."""

        variables = _render_variables(
            {"header.host": "example.com", "query.mark": "kept"},
            {"endpoint": "/json?tenant=1"})

        self.assertEqual(
            "https://example.com/json?tenant=1", variables["_url"])


if __name__ == "__main__":
    unittest.main()
