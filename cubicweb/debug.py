# copyright 2019 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.

from logging import getLogger

logger = getLogger('cubicweb')


SUBSCRIBERS = {
    "rql": [],
}


def subscribe_to_debug_channel(channel, subscriber):
    if channel not in SUBSCRIBERS.keys():
        raise Exception("debug channel '%s' doesn't exist" % channel)

    SUBSCRIBERS[channel].append(subscriber)


def unsubscribe_to_debug_channel(channel, subscriber):
    if channel not in SUBSCRIBERS.keys():
        raise Exception("debug channel '%s' doesn't exist" % channel)

    if subscriber not in SUBSCRIBERS[channel]:
        raise Exception("subscriber '%s' is not in debug channel '%s'" % (subscriber, channel))

    SUBSCRIBERS[channel].remove(subscriber)


def emit_to_debug_channel(channel, message):
    if channel not in SUBSCRIBERS.keys():
        raise Exception("debug channel '%s' doesn't exist" % channel)

    for subscriber in SUBSCRIBERS[channel]:
        try:
            subscriber(message)
        except Exception:
            logger.error("Failed to send debug message '%s' to subscriber '%s'", message, subscriber, exc_info=True)
