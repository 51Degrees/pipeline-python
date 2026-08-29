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

"""51Did creator context demo server.

Serves ``page.html`` with a fresh challenge per load, and redeems the
encrypted result server side with the ``DidClient`` from this package,
adding the licence key the browser never sees. The page runs the 51Did
flow the way production does.

1. Create a 51Did by calling the ``json`` endpoint, which issues an
   identifier for the calling connection. The browser makes this call,
   so the identifier is created for the browser's own connection.
2. Verify it with ``verify-full``, which returns both the signature
   outcome and the creator context verdict only as an encrypted
   ``result`` that the caller cannot read or forge. (A deployment
   holding no context secret answers in the open instead.) The browser
   makes this call too, so the cloud observes the browser's live connection,
   then the page hands the encrypted result to this server.
3. Parse the 51Did, check its signature offline against the published
   public keys, then redeem the encrypted result with ``redeem``,
   presenting the 51Did, the encrypted result and the account's licence
   key, and receive the true creator context verdict, when the
   verification happened (``verifiedAt``) and how long ago that was
   (``secondsSinceVerified``). This server makes that call, as the only
   party holding the licence key.

A fresh challenge is issued per page load and bound through both steps
by the cloud. A production server would also remember the value it
issued and reject a redemption carrying any other, which this demo
keeps out of scope.

What a run costs. Every call to the cloud is one use against the
subscription behind the resource key. A browser-based context check
makes two, verify-full from the page and redeem from this server, so
two uses every time. The creation call is a further use. The public
key list the offline check needs is fetched once and cached for a day.

Environment variables. ``_51DEGREES_RESOURCE_KEY`` (or the older
``RESOURCE_KEY``) is required. ``_51DEGREES_LICENSE_KEY`` (or
``LICENSE_KEY``) is optional, and the comment in ``run`` says why.
``FOD_CLOUD_API_URL`` is the cloud API base including the ``/api/v4/``
segment, defaulting to ``https://cloud.51degrees.com/api/v4/``, and is
the same variable the cloud request engine and the ``DidClient`` honour.
``PORT`` is the port to listen on, defaulting to 5100.

Standard library plus this package. Run ``python server.py`` then open
``http://localhost:5100/``.
"""

import json
import os
import secrets
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The package from this repository rather than a published one, so the
# branch is what runs. When the package is installed the import succeeds
# directly, and otherwise the package source beside this example is used,
# which is how a checkout runs the demo without an install step. The OWID
# library the package builds on must be installed either way (see the
# package readme).
try:
    from fiftyone_pipeline_did import (
        DidClient, DidClientError, DidNotSupportedError, FodId)
except ImportError:
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    from fiftyone_pipeline_did import (
        DidClient, DidClientError, DidNotSupportedError, FodId)

DEFAULT_API = "https://cloud.51degrees.com/api/v4/"


def env(*names):
    """The first of the named environment variables that is set and not
    empty, so the aligned name is tried before the older one."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


RESOURCE = env("_51DEGREES_RESOURCE_KEY", "RESOURCE_KEY")
LICENCE = env("_51DEGREES_LICENSE_KEY", "LICENSE_KEY") or ""
# The cloud API base, normalised to end in exactly one slash so that
# every URL is the base followed by its path. The page receives the same
# value through its __API__ placeholder and builds its two cloud calls
# from it, and the DidClient treats the same variable the same way. A
# host other than cloud.51degrees.com would be used to (a) use an on
# premise web server, or (b) use a privately hosted version of the
# 51Degrees cloud for performance reasons. That is the private hosting
# option of the cloud service, and both run the same service, so this
# demo works unchanged against either.
API = (env("FOD_CLOUD_API_URL") or DEFAULT_API).rstrip("/") + "/"
PORT = int(os.environ.get("PORT", "5100"))


def page_html():
    # Both files are read PER REQUEST, not once at start-up. A demo left
    # running while its page is edited would otherwise keep serving the
    # version it started with, which looks exactly like an edit that did
    # not work. The cost is one small file read per request, which is
    # nothing at demo scale.
    return (HERE / "page.html").read_text(encoding="utf-8")


def css_bytes():
    # The design system stylesheet, vendored beside this server exactly
    # as the other 51Degrees web examples vendor it. Its source of truth
    # is pattern-library/source/sass in the 51Degrees/documentation
    # repository.
    return (HERE / "examples-main.min.css").read_bytes()


class Demo(BaseHTTPRequestHandler):
    """The demo's three routes. ``client`` is the one ``DidClient`` the
    whole server shares, set by ``run`` from the environment, or by a test
    with a stand-in transport."""

    client = None

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/redeem":
            self.redeem(urllib.parse.parse_qs(url.query))
        elif url.path == "/examples-main.min.css":
            body = css_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/":
            self.page()
        else:
            self.send_error(404)

    def page(self):
        body = (page_html()
                .replace("__RESOURCE__", RESOURCE)
                .replace("__CHALLENGE__", secrets.token_hex(16))
                .replace("__API__", API)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redeem(self, query):
        """The server-side step. The licence key is inside the client and
        is added here and only here, so the browser never sees it.

        Answers the page with the cloud's status and a body in the cloud's
        own shape (signature, context, factors when present, verifiedAt,
        secondsSinceVerified) built from the typed result, plus
        serverSignature, which is this server's own offline check of the
        identifier's signature against the published public keys. The page
        ignores fields it does not know, so page.html is the same for every
        language.
        """
        client = self.client
        if client is None:
            self.send_json(500, {"error": "The server has no DidClient. "
                                          "Start it with run()."})
            return
        # The identifier arrives in the URL-safe alphabet from the page,
        # which from_base64 accepts alongside the standard one. The
        # parameter is named 51did, because the value is a 51Did and OWID
        # is only the envelope format it travels in.
        try:
            fod_id = FodId.from_base64(query.get("51did", [""])[0])
        except Exception as error:
            # The caller's own identifier, so naming the fault costs
            # nothing, which is the same 400 with an errors list the cloud
            # gives.
            self.send_json(400, {
                "errors": ["51did is not a valid 51Did: {0}".format(error)]})
            return
        try:
            # The signature checked here, offline, before the cloud is
            # asked to redeem anything, so a forged envelope is named by
            # this server rather than only by the cloud.
            signature_valid = client.verify_signature(fod_id)
            redeemed = client.redeem(
                fod_id,
                query.get("result", [""])[0],
                query.get("challenge", [""])[0])
            body = redeemed.to_dict()
            body["serverSignature"] = \
                "verified" if signature_valid else "invalid"
            self.send_json(redeemed.status_code, body)
        except DidNotSupportedError as error:
            # A host without the creator context answers 404 with a text
            # body, which the page reports as not supported by this host.
            self.send_text(404, error.body or str(error))
        except DidClientError as error:
            if error.status_code is None:
                self.send_json(502, {"error": str(error)})
                return
            # Relayed as the cloud said it, status and body, so a failure
            # reads on the page as what the cloud said.
            body = error.body or str(error)
            if _is_json(body):
                self.send_bytes(error.status_code, "application/json",
                                body.encode("utf-8"))
            else:
                self.send_text(error.status_code, body)
        except OSError as error:
            # An unreachable cloud must answer the page, not crash the
            # demo server. urllib's URLError is an OSError.
            self.send_json(502, {"error": "redeem failed: {0}".format(
                getattr(error, "reason", error))})

    def send_json(self, status, body):
        self.send_bytes(status, "application/json",
                        json.dumps(body).encode("utf-8"))

    def send_text(self, status, text):
        self.send_bytes(status, "text/plain; charset=utf-8",
                        text.encode("utf-8"))

    def send_bytes(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _is_json(text):
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def run():
    if not RESOURCE:
        sys.exit("Set _51DEGREES_RESOURCE_KEY (or RESOURCE_KEY) to the "
                 "resource key of the page.")
    if not LICENCE:
        # Only an account that holds licence keys needs one to redeem,
        # because the licence key is what keeps redemption to the acting
        # party's own servers. An account holding none has nothing to
        # check against, so the demo runs without it. Saying so here
        # means an account that DOES hold licence keys, run without one,
        # is diagnosed at start-up rather than by an unreadable verdict
        # three steps later that looks like a cryptographic failure.
        print("No _51DEGREES_LICENSE_KEY set. Redemption will work where "
              "the account holds no licence keys, and will report the "
              "context unreadable where it holds some.")
    # One client for the whole server. It holds the resource key, the
    # licence key and the endpoint, and caches the public key list.
    Demo.client = DidClient(RESOURCE, LICENCE or None, API)
    print(f"51Did demo on http://localhost:{PORT}/")
    HTTPServer(("", PORT), Demo).serve_forever()


if __name__ == "__main__":
    run()
