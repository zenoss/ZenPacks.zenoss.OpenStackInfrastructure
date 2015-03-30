##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Periodic progress logging for long-running operations.

Example usage:

    import logging
    LOG = logging.getLogger(__name__)

    import time
    import progresslog

    mylist = range(100)

    progress = ProgressLogger(
        LOG,
        prefix="progress",
        total=len(mylist),
        interval=1)

    for i in mylist:
        progress.increment()
        time.sleep(0.2)

"""

import datetime
import logging


class ProgressLogger(object):

    """Periodic progress logging for long-running operations."""

    def __init__(
            self,
            logger,
            level=logging.INFO,
            prefix='',
            total=None,
            interval=60):

        self.logger = logger
        self.level = level
        self.prefix = prefix
        self.total = total
        self.interval = datetime.timedelta(seconds=interval)

        self.pos = 0
        self.start_time = datetime.datetime.now()
        self.last_time = self.start_time

    def increment(self, by=1):
        """Increment internal position and emit progress log if needed."""
        self.pos += by

        now = datetime.datetime.now()
        if now - self.last_time >= self.interval:
            self.last_time = now

            progress = '{} of {}'.format(
                self.pos,
                self.total if self.total else '?')

            elapsed = now - self.start_time

            if self.total:
                per = elapsed / self.pos
                remaining = per * (self.total - self.pos)

                msg = '{}, elapsed={}, remaining={}'.format(
                    progress,
                    str(elapsed).split('.', 1)[0],
                    str(remaining).split('.', 1)[0])
            else:
                msg = '{}, elapsed={}'.format(
                    progress,
                    str(elapsed).split('.', 1)[0])

            if self.prefix:
                msg = '{}: {}'.format(self.prefix, msg)

            self.logger.log(self.level, msg)
