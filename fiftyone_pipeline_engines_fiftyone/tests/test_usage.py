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

import platform
import sys
import threading
from time import sleep
import unittest
from wsgiref.simple_server import make_server
import gzip

from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder
from fiftyone_pipeline_engines_fiftyone.share_usage import ShareUsage
from flask import Flask, request, render_template
import requests

testHost = "127.0.0.1"
testPort = 5000
testEndpoint = f"http://{testHost}:{testPort}"

shareUsageVersion = "1.1"


class ReceiverThread(threading.Thread):

    def __init__(self, app):
        threading.Thread.__init__(self)
        self.server = make_server(testHost, testPort, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()

    def get_received(self):
        return self.server.get_app().received

app = Flask(__name__)
app.received = []

@app.route('/', methods=['POST'])
def server():
    data = gzip.decompress(request.data).decode("utf8")
    str(app.received.append(data))
    return ""


######################################
# The Tests

class UsageTests(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.startReceiver()

    def setUp(self):
        app.received = []

    @classmethod
    def tearDownClass(cls):
        cls.stopReceiver()

    @classmethod
    def startReceiver(cls):
        cls.receiver = ReceiverThread(app)
        cls.receiver.start()

    @classmethod
    def stopReceiver(cls):
        cls.receiver.shutdown()

    def waitForUsageThreads(self):
        # necessary for context switching and
        # allowing the thread pool in ShareUsage to start sending data and release the GIL
        sleep(0.1)

    def test_data_received(self):
        """!
        Check that data is received from the share usage element. 
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint = testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 1)
        
    def test_data_correct(self):
        """!
        Check that the data received from the share usage element is correct.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.process()

        self.waitForUsageThreads()
        self.assertIsNotNone(app.received[0])
        self.assertGreater(len(app.received[0]), 0)
        self.assertRegex(app.received[0], f"^<Devices version=\"{shareUsageVersion}\"><Device>.*")
        self.assertRegex(app.received[0], ".*</Device></Devices>$")
        self.assertIn("<Language>Python</Language>", app.received[0])
        self.assertIn(f"<LanguageVersion>{platform.python_version()}</LanguageVersion>", app.received[0])
        self.assertIn(f"<Platform>{platform.system()} {platform.release()}</Platform>", app.received[0])
        self.assertIn("<FlowElement>ShareUsage</FlowElement>", app.received[0])

    def test_includes_header(self):
        """!
        Check that the data received from the share usage element contains the
        headers which were in the evidence.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        uaValue = "some user agent.."
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("header.user-agent", uaValue)
        flowdata.process()

        self.waitForUsageThreads()
        self.assertIsNotNone(app.received[0])
        self.assertGreater(len(app.received[0]), 0)
        self.assertIn(f"<header Name=\"user-agent\">{uaValue}</header>", app.received[0]);

    def test_client_ip(self):
        """!
        Check that the data received from the share usage element includes
        the client IP from the evidence.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        ip = "1.2.3.4"
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("server.client-ip", ip)
        flowdata.process()

        self.waitForUsageThreads()
        self.assertIsNotNone(app.received[0])
        self.assertGreater(len(app.received[0]), 0)
        self.assertIn(f"<ClientIP>{ip}</ClientIP>", app.received[0]);

    def test_two_events_first(self):
        """!
        Check that a single event is not sent when the requested package
        size is 2.
        """

        usage = ShareUsage(
            requested_package_size=2,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 0)

    def test_two_events_second(self):
        """!
        Check that a single event is not sent when the requested package
        size is 2.
        """

        usage = ShareUsage(
            requested_package_size=2,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata1 = pipeline.create_flowdata()
        flowdata1.evidence.add("header.user-agent", "ua 1")
        flowdata1.process()
        flowdata2 = pipeline.create_flowdata()
        flowdata2.evidence.add("header.user-agent", "ua 2")
        flowdata2.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 1)
        self.assertIn("ua 1", app.received[0])
        self.assertIn("ua 2", app.received[0])

    def test_ignore_headers(self):
        """!
        Check that the share usage element respects the headerBlacklist.
        When header names are added to the list, values for them should
        not be included in the data shared.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint,
            header_blacklist=[ "x-forwarded-for", "forwarded-for" ])

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("header.user-agent", "some user agent")
        flowdata.evidence.add("header.x-forwarded-for", "5.6.7.8")
        flowdata.evidence.add("header.forwarded-for", "2001::")
        flowdata.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 1)
        self.assertNotIn("x-forwarded-for", app.received[0])
        self.assertNotIn("forwarded-for", app.received[0])

    def test_queue_cleared(self):

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("header.user-agent", "some user agent")
        flowdata.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 1)
        self.assertEqual(len(usage.share_data), 0)

    def test_session_and_sequence(self):
        """!
        Check that session and sequence values are included.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("query.session-id", "1")
        flowdata.evidence.add("query.sequence", "1")
        flowdata.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 1)
        self.assertIn("<SessionId>1</SessionId>", app.received[0])
        self.assertIn("<Sequence>1</Sequence>", app.received[0])

    def test_invalid_char(self):
        """!
        Check that invalid characters are escaped correctly.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        replacementChar = chr(int("0xFFFD", 16))

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("header.user-agent", "1ƌ2")
        flowdata.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 1)
        self.assertNotIn("ƌ", app.received[0])
        self.assertIn(replacementChar, app.received[0])
        self.assertIn(f"<header Name=\"user-agent\" replaced=\"true\">1{replacementChar}2</header>", app.received[0])

    def test_truncated_value(self):
        """!
        Check that long values are truncated correctly.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        ua = "X" * 1000

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("header.user-agent", ua)
        flowdata.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 1)
        self.assertIn("truncated=\"true\"", app.received[0])
        self.assertNotIn(ua, app.received[0])
        self.assertIn(f'<header Name="user-agent" truncated="true">{"X" * 512}</header>', app.received[0])

    def test_send_more_than_once(self):
        """!
        Check that the queue of data is correctly reset, and used for the
        next set of requests.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata1 = pipeline.create_flowdata()
        flowdata1.evidence.add("header.user-agent", "ua 1")
        flowdata1.process()
        flowdata2 = pipeline.create_flowdata()
        flowdata2.evidence.add("header.user-agent", "ua 2")
        flowdata2.process()

        self.waitForUsageThreads()
        self.assertEqual(len(app.received), 2)
        self.assertEqual(len(usage.share_data), 0)
        received = "\n".join(app.received)
        self.assertIn("ua 1", received)
        self.assertIn("ua 2", received)

    def test_low_percentage(self):
        """!
        Check that small portion sharing is done correctly.
        """

        usage = ShareUsage(
            requested_package_size=10,
            share_percentage=0.01,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()

        requiredEvents = 0
        while len(app.received) == 0 and requiredEvents <= 10000:
            flowdata = pipeline.create_flowdata()
            flowdata.evidence.add("server.client-ip", "1.2.3.4")
            flowdata.evidence.add("header.user-agent", f"ua {requiredEvents}")
            flowdata.process()
            requiredEvents = requiredEvents + 1

        self.waitForUsageThreads()

        # On average, the number of required events should be around
        # 1000. However, as it's chance based it can vary
        # significantly. We only want to catch any gross errors so just
        # make sure the value is of the expected order of magnitude.
        self.assertGreater(requiredEvents, 100,
            "Expected the number of required events to be at least " +
            f"100, but was actually '{requiredEvents}'")
        self.assertLess(requiredEvents, 10000,
            "Expected the number of required events to be less than " +
            f"10,000, but was actually '{requiredEvents}'")

    def test_includes_header(self):
        """!
        Check that XML characters are escaped correctly.
        """

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint)

        pipeline = (PipelineBuilder())\
            .add(usage)\
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("header.user-agent", '"\'&><')
        flowdata.process()

        self.waitForUsageThreads()
        self.assertIsNotNone(app.received[0])
        self.assertGreater(len(app.received[0]), 0)
        self.assertIn('&quot;', app.received[0])
        self.assertIn('&apos;', app.received[0])
        self.assertIn('&lt;', app.received[0])
        self.assertIn('&gt;', app.received[0])
        self.assertIn('&amp;', app.received[0])


    # zzz is to make this test run last so no other tests depend on the receiver anymore
    # we depend on python unittests ordering tests alphabetically, which is not ideal, but works for now
    def test_zzz_timeout(self):
        # this tests just verifies that there is a timeout and that the tests actually complete
        # even if there is no server listening, so we shut it down right away
        self.__class__.stopReceiver()

        usage = ShareUsage(
            requested_package_size=1,
            endpoint=testEndpoint,
            request_timeout=1 #really short request time out
        )

        pipeline = (PipelineBuilder()) \
            .add(usage) \
            .build()
        flowdata = pipeline.create_flowdata()
        flowdata.evidence.add("header.user-agent", '"\'&><')
        flowdata.process()

        self.assertTrue(True)
