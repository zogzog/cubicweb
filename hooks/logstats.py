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

"""looping task for dumping instance's stats in a file
"""

__docformat__ = "restructuredtext en"

from datetime import datetime
import json

from cubicweb.server import hook

class LogStatsStartHook(hook.Hook):
    """register task to regularly dump instance's stats in a file

    data are stored as one json entry per row
    """
    __regid__ = 'cubicweb.hook.logstats.start'
    events = ('server_startup',)

    def __call__(self):
        interval = self.repo.config.get('logstat-interval', 0)
        if interval <= 0:
            return            

        def dump_stats(repo):
            statsfile = repo.config.get('logstat-file')
            with repo.internal_cnx() as cnx:
                stats = cnx.call_service('repo_stats')
                gcstats = cnx.call_service('repo_gc_stats', nmax=5)
                
            allstats = {'resources': stats,
                        'memory': gcstats,
                        'timestamp': datetime.utcnow().isoformat(),
                       }
            try:
                with open(statsfile, 'ab') as ofile:
                    json.dump(allstats, ofile)
                    ofile.write('\n')
            except IOError:
                repo.warning('Cannot open stats file for writing: %s', statsfile)
                    
        self.repo.looping_task(interval, dump_stats, self.repo)
