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
encrypted result server side, adding the licence key the browser never
sees. The page runs the 51Did flow the way production does.

1. Create a 51Did by calling the ``json`` endpoint, which issues an
   identifier for the calling connection. The browser makes this call,
   so the identifier is created for the browser's own connection.
2. Verify it with ``verify-full``, which returns both the signature
   outcome and the creator context verdict only as an encrypted
   ``result`` that the caller cannot read or forge. (A deployment
   holding no context secret answers in the open instead.) The browser
   makes this call too, so the cloud observes the browser's live connection,
   then the page hands the encrypted result to this server.
3. Redeem the encrypted result with ``redeem``, presenting the 51Did,
   the encrypted result and the account's licence key, and receive the
   true creator context verdict, when the verification happened
   (``verifiedAt``) and how long ago that was
   (``secondsSinceVerified``). This server makes that call, as the only
   party holding the licence key.

A fresh challenge is issued per page load and bound through both steps
by the cloud. A production server would also remember the value it
issued and reject a redemption carrying any other, which this demo
keeps out of scope.

What a run costs. Every call to the cloud is one use against the
subscription behind the resource key. A browser-based context check
makes two, verify-full from the page and redeem from this server, so
two uses every time. The creation call is a further use.

Environment variables. ``_51DEGREES_RESOURCE_KEY`` (or the older
``RESOURCE_KEY``) is required. ``_51DEGREES_LICENSE_KEY`` (or
``LICENSE_KEY``) is optional, and the comment in ``run`` says why.
``FOD_CLOUD_API_URL`` is the cloud API base including the ``/api/v4/``
segment, defaulting to ``https://cloud.51degrees.com/api/v4/``, and is
the same variable the cloud request engine honours. ``PORT`` is the
port to listen on, defaulting to 5100.

Standard library only. Run ``python server.py`` then open
``http://localhost:5100/``.
"""

import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

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
# from it. A host other than cloud.51degrees.com would be used to (a)
# use an on premise web server, or (b) use a privately hosted version
# of the 51Degrees cloud for performance reasons. That is the private
# hosting option of the cloud service, and both run the same service,
# so this demo works unchanged against either.
API = (env("FOD_CLOUD_API_URL") or DEFAULT_API).rstrip("/") + "/"
PORT = int(os.environ.get("PORT", "5100"))

# Both files are read PER REQUEST, not once at start-up. A demo left
# running while its page is edited would otherwise keep serving the
# version it started with, which looks exactly like an edit that did not
# work. The cost is one small file read per request, which is nothing at
# demo scale.
HERE = Path(__file__).parent


def page_html():
    return (HERE / "page.html").read_text(encoding="utf-8")


def css_bytes():
    # The design system stylesheet, vendored beside this server exactly
    # as the other 51Degrees web examples vendor it. Its source of truth
    # is pattern-library/source/sass in the 51Degrees/documentation
    # repository.
    return (HERE / "examples-main.min.css").read_bytes()


class Demo(BaseHTTPRequestHandler):

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
        # The server-side step. The licence key is added here and only
        # here, so the browser never sees it, and it is sent empty when
        # there is none.
        # The identifier parameter is named 51did, because the value is
        # a 51Did and OWID is only the envelope format it travels in.
        params = urllib.parse.urlencode({
            "51did": query.get("51did", [""])[0],
            "result": query.get("result", [""])[0],
            "challenge": query.get("challenge", [""])[0],
            "license": LICENCE,
        })
        url = f"{API}id/redeem/{RESOURCE}?{params}"
        request = urllib.request.Request(
            url, headers={"User-Agent": "51did-demo-python"})
        # The cloud's answer is relayed exactly as received, status,
        # content type and body, so the page sees a 404 from a service
        # that does not offer these endpoints yet as a 404 carrying the
        # service's own text, rather than as a success carrying
        # something that is not JSON.
        try:
            with urllib.request.urlopen(request) as response:
                status = response.status
                content_type = response.headers.get(
                    "Content-Type", "application/json")
                body = response.read()
        except urllib.error.HTTPError as error:
            status = error.code
            content_type = error.headers.get(
                "Content-Type", "text/plain; charset=utf-8")
            body = error.read()
        except urllib.error.URLError as error:
            status = 502
            content_type = "text/plain; charset=utf-8"
            body = f"redeem failed: {error.reason} from {url}".encode(
                "utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


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
    print(f"51Did demo on http://localhost:{PORT}/")
    HTTPServer(("", PORT), Demo).serve_forever()


if __name__ == "__main__":
    run()
