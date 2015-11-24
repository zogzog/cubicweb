# copyright 2004-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of yams.
#
# yams is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# yams is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with yams. If not, see <http://www.gnu.org/licenses/>.
from datetime import time, date
from yams.buildobjs import EntityType, Datetime, Date, Time
from yams.constraints import TODAY, BoundaryConstraint

class Datetest(EntityType):
    dt1 = Datetime(default=u'now')
    dt2 = Datetime(default=u'today')
    d1  = Date(default=u'today', constraints=[BoundaryConstraint('<=', TODAY())])
    d2  = Date(default=date(2007, 12, 11))
    t1  = Time(default=time(8, 40))
    t2  = Time(default=time(9, 45))
