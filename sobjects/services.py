# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Define server side service provided by cubicweb"""

import threading

from cubicweb.server import Service
from cubicweb.predicates import match_user_groups

class StatsService(Service):
    """Return a dictionary containing some statistics about the repository
    resources usage.
    """

    __regid__  = 'repo_stats'
    __select__ = match_user_groups('managers')

    def call(self):
        repo = self._cw.repo # Service are repo side only.
        results = {}
        querier = repo.querier
        source = repo.system_source
        for size, maxsize, hits, misses, title in (
            (len(querier._rql_cache), repo.config['rql-cache-size'],
            querier.cache_hit, querier.cache_miss, 'rqlt_st'),
            (len(source._cache), repo.config['rql-cache-size'],
            source.cache_hit, source.cache_miss, 'sql'),
            ):
            results['%s_cache_size' % title] = '%s / %s' % (size, maxsize)
            results['%s_cache_hit' % title] = hits
            results['%s_cache_miss' % title] = misses
            results['%s_cache_hit_percent' % title] = (hits * 100) / (hits + misses)
        results['type_source_cache_size'] = len(repo._type_source_cache)
        results['extid_cache_size'] = len(repo._extid_cache)
        results['sql_no_cache'] = repo.system_source.no_cache
        results['nb_open_sessions'] = len(repo._sessions)
        results['nb_active_threads'] = threading.activeCount()
        looping_tasks = repo._tasks_manager._looping_tasks
        results['looping_tasks'] = ', '.join(str(t) for t in looping_tasks)
        results['available_cnxsets'] = repo._cnxsets_pool.qsize()
        results['threads'] = ', '.join(sorted(str(t) for t in threading.enumerate()))
        return results
