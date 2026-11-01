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

import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

from fiftyone_pipeline_engines.datafile_update_service import DataFileUpdateService
from fiftyone_pipeline_engines.datafile_update_service import UpdateStatus


def read(path):
    with open(path) as file:
        return file.read()


class RecordingPipeline:
    """Stands in for a pipeline and keeps each message logged."""

    def __init__(self):
        self.logs = []

    def log(self, level, message):
        self.logs.append((level, message))


class StandInDataFile:
    """Stands in for the data file of an engine that keeps the data it has
    when a refresh fails."""

    def __init__(self, path):
        self.path = path
        self.update_on_start = False
        self.auto_update = False
        self.file_system_watcher = True
        self.updating = False
        self.data = read(path)

    def refresh(self):
        content = read(self.path)
        if not content.startswith("version"):
            raise Exception("The data file cannot be used.")
        self.data = content


class ScheduledCheck:
    """Takes the place of a threading.Timer and waits to be run by the test."""

    def __init__(self, pending, function, args):
        self.pending = pending
        self.function = function
        self.args = args

    def start(self):
        self.pending.append(self)


class FileSystemWatcherTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, "data.dat")
        self.stamp = time.time()
        self.write("version 1")
        self.pipeline = RecordingPipeline()
        self.service = DataFileUpdateService(self.pipeline)
        self.statuses = []
        self.service.on_complete(
            lambda status, data_file: self.statuses.append(status))
        self.pending = []
        # The test runs each check the watcher schedules, one at a time.
        timer = mock.patch.object(
            threading, "Timer",
            lambda interval, function, args=None: ScheduledCheck(
                self.pending, function, args or []))
        timer.start()
        self.addCleanup(timer.stop)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def write(self, content):
        with open(self.path, "w") as file:
            file.write(content)
        # Later than any time the watcher has seen, however coarse the clock.
        self.stamp += 10
        os.utime(self.path, (self.stamp, self.stamp))

    def run_next_check(self):
        check = self.pending.pop(0)
        check.function(*check.args)

    # A refresh that fails is logged and reported, the data in use is kept,
    # and a later good file is picked up.
    def testFileSystemWatcherKeepsWatchingAfterFailedRefresh(self):
        data_file = StandInDataFile(self.path)
        self.service.register_data_file(data_file)

        self.write("unusable")
        self.run_next_check()
        self.assertEqual("version 1", data_file.data)
        self.assertEqual(
            [UpdateStatus.AUTO_UPDATE_REFRESH_FAILED], self.statuses)
        self.assertEqual(1, len(self.pipeline.logs))
        self.assertEqual("error", self.pipeline.logs[0][0])
        self.assertIn("The data file cannot be used.", self.pipeline.logs[0][1])
        self.assertEqual(1, len(self.pending))

        self.write("version 2")
        self.run_next_check()
        self.assertEqual("version 2", data_file.data)

    # A file that is missing at a check, for example part way through being
    # replaced, is looked for again at the next check.
    def testFileSystemWatcherKeepsWatchingWhileFileIsMissing(self):
        data_file = StandInDataFile(self.path)
        self.service.register_data_file(data_file)

        os.remove(self.path)
        self.run_next_check()
        self.assertEqual(1, len(self.pending))

        self.write("version 2")
        self.run_next_check()
        self.assertEqual("version 2", data_file.data)
        self.assertNotIn(
            UpdateStatus.AUTO_UPDATE_REFRESH_FAILED, self.statuses)


if __name__ == "__main__":
    unittest.main()
