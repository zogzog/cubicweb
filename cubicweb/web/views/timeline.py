# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

try:
    from cubes.timeline.views import (
            TimelineJsonView,
            TimelineViewMixIn,
            TimelineView,
            StaticTimelineView)

except ImportError:
    pass
else:
    from logilab.common.deprecation import class_moved

    TimelineJsonView = class_moved(TimelineJsonView, 'TimelineJsonView')
    TimelineViewMixIn = class_moved(TimelineViewMixIn, 'TimelineViewMixIn')
    TimelineView = class_moved(TimelineView, 'TimelineView')
    StaticTimelineView = class_moved(StaticTimelineView, 'StaticTimelineView')
