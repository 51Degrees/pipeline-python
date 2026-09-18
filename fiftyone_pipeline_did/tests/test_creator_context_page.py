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
What the creator context demo page does in a browser, checked by running
its script in Node with a small stand in for a browser
(creator_context_page_harness.js). Both the parse check and the run need
Node on the path, which every GitHub hosted runner has.

The service creates a 51Did only once the page has run the snippets it
asks for and sent what they collected, so a page that asks for one
directly is told the page has not finished and is given nothing. The
51Degrees client script is what runs those snippets, so the page has to
create through the script and then send what the snippets collected with
its verification call as well. These tests pin both, because neither can
be seen from the Python side of the demo and neither shows up in a unit
test of the server.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

NODE = shutil.which("node")
HERE = os.path.dirname(__file__)
HARNESS = os.path.join(HERE, "creator_context_page_harness.js")
PAGE = os.path.join(
    os.path.dirname(HERE), "examples", "creator_context_web", "page.html")

# The licensed probabilistic identifier the stand in client script
# reports, and the same value once the page has made it safe for a URL.
CREATED = "prob+lic/value="
CREATED_URL_SAFE = "prob-lic_value"


def run_page(given=None):
    """Run the page's script and return what the harness recorded."""

    command = [NODE, HARNESS, PAGE]
    if given is not None:
        command.append(given)
    finished = subprocess.run(
        command, capture_output=True, text=True, timeout=60)
    if finished.returncode != 0:
        raise AssertionError(
            "the harness failed: " + finished.stdout + finished.stderr)
    return json.loads(finished.stdout.strip().splitlines()[-1])


@unittest.skipUnless(NODE, "Node is not on the path")
class CreatorContextPageTests(unittest.TestCase):

    def test_the_page_script_parses(self):
        """A page whose script does not parse defines nothing and reports
        nothing, and the browser says so only in its console. node --check
        reads JavaScript rather than HTML, so the page's script block is
        written out on its own and checked."""

        page = open(PAGE, encoding="utf-8").read()
        # A checkout on Windows has carriage returns in it.
        block = re.search(
            r"<script>\r?\n(.*?)\r?\n</script>", page, re.S)
        self.assertIsNotNone(block, "the page has a script block")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "page-script.js")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(block.group(1))
            finished = subprocess.run(
                [NODE, "--check", path], capture_output=True, text=True)
        self.assertEqual(
            0, finished.returncode,
            "the page's script does not parse: " + finished.stderr)
        self.assertEqual([], run_page()["errors"])

    def test_the_identifier_comes_from_the_client_script(self):
        """The page asks the cloud for the client script, with the usage
        and the email address on its address, and takes the identifier
        from what the script reports."""

        record = run_page()
        self.assertEqual(1, len(record["scripts"]),
                         "the page loads the client script exactly once")
        script = record["scripts"][0]
        self.assertIn("TEST-RESOURCE-KEY.js", script)
        self.assertIn("id.usage=non-marketing", script)
        self.assertIn("id.email=", script)
        self.assertEqual("created for this browser",
                         record["rows"]["s-create"])

    def test_the_page_does_not_ask_for_an_identifier_itself(self):
        """A request of the page's own would be made before the snippets
        had run, and the service would answer it with no identifier at
        all."""

        record = run_page()
        for address in record["fetches"]:
            self.assertNotIn("json?resource=", address)
            self.assertNotIn("/json", address)

    def test_the_verification_carries_the_identifier_and_the_snippets(self):
        """The identifier the script reported is verified, made safe for a
        URL, and what the snippets collected goes with it, because the
        service compares this browser against the creator from those
        values."""

        record = run_page()
        verify = [a for a in record["fetches"] if "id/verify-full" in a]
        self.assertEqual(1, len(verify))
        self.assertIn(CREATED_URL_SAFE, verify[0])
        self.assertNotIn("+", verify[0].split("?")[0])
        self.assertIn("51D_ScreenPixelsHeight=1080", verify[0])
        self.assertIn("51D_ProfileIds=1-2-3", verify[0])
        self.assertNotIn("unrelated=ignored", verify[0])

    def test_the_result_is_redeemed_on_the_page_s_own_server(self):
        """The licence key lives on the server, so the sealed result goes
        there and the verdict comes back from there."""

        record = run_page()
        redeem = [a for a in record["fetches"] if a.startswith("/redeem?")]
        self.assertEqual(1, len(redeem))
        self.assertIn("result=sealed-result", redeem[0])
        self.assertEqual("verified", record["rows"]["s-signature"])
        self.assertEqual("verified", record["rows"]["s-context"])

    def test_a_transplanted_identifier_still_runs_the_client_script(self):
        """The page opened with an identifier from another browser checks
        that identifier, and still needs this browser's snippet values for
        the comparison, so the script runs on that path too."""

        record = run_page("given-value")
        self.assertEqual(1, len(record["scripts"]))
        verify = [a for a in record["fetches"] if "id/verify-full" in a]
        self.assertEqual(1, len(verify))
        self.assertIn("given-value", verify[0])
        self.assertIn("51D_ProfileIds=1-2-3", verify[0])


if __name__ == "__main__":
    unittest.main()
