# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from cubicweb.predicates import match_user_groups, match_kwargs


class StatsService(Service):
    """Return a dictionary containing some statistics about the repository
    resources usage.
    """

    __regid__ = 'repo_stats'
    __select__ = match_user_groups('managers', 'users')

    def call(self):
        repo = self._cw.repo  # Service are repo side only.
        results = {}
        querier = repo.querier
        source = repo.system_source
        for size, maxsize, hits, misses, title in (
            (len(querier.rql_cache), repo.config['rql-cache-size'],
             querier.rql_cache.cache_hit, querier.rql_cache.cache_miss, 'rqlt_st'),
            (len(source._cache), repo.config['rql-cache-size'],
             source.cache_hit, source.cache_miss, 'sql'),
        ):
            results['%s_cache_size' % title] = {'size': size, 'maxsize': maxsize}
            results['%s_cache_hit' % title] = hits
            results['%s_cache_miss' % title] = misses
            results['%s_cache_hit_percent' % title] = (hits * 100) / (hits + misses)
        results['type_cache_size'] = len(repo._type_cache)
        results['sql_no_cache'] = repo.system_source.no_cache
        results['nb_active_threads'] = threading.activeCount()
        results['available_cnxsets'] = repo.cnxsets.qsize()
        results['threads'] = [t.name for t in threading.enumerate()]
        return results


class GcStatsService(Service):
    """Return a dictionary containing some statistics about the repository
    resources usage.
    """

    __regid__ = 'repo_gc_stats'
    __select__ = match_user_groups('managers')

    def call(self, nmax=20):
        """Return a dictionary containing some statistics about the repository
        memory usage.

        nmax is the max number of (most) referenced object returned as
        the 'referenced' result
        """

        from cubicweb._gcdebug import gc_info
        from cubicweb.appobject import AppObject
        from cubicweb.rset import ResultSet
        from cubicweb.web.request import CubicWebRequestBase
        from rql.stmts import Union

        lookupclasses = (AppObject,
                         Union, ResultSet,
                         CubicWebRequestBase)

        results = {}
        counters, ocounters, garbage = gc_info(lookupclasses,
                                               viewreferrersclasses=())
        values = sorted(counters.items(), key=lambda x: x[1], reverse=True)
        results['lookupclasses'] = values
        values = sorted(ocounters.items(), key=lambda x: x[1], reverse=True)[:nmax]
        results['referenced'] = values
        results['unreachable'] = garbage
        return results


class RegisterUserService(Service):
    """check if a user with the given login exists, if not create it with the
    given password. This service is designed to be used for anonymous
    registration on public web sites.

    To use it, do:
     with self.appli.repo.internal_cnx() as cnx:
        cnx.call_service('register_user',
                         login=login,
                         password=password,
                         **cwuserkwargs)
    """
    __regid__ = 'register_user'
    __select__ = Service.__select__ & match_kwargs('login', 'password')
    default_groups = ('users',)

    def call(self, login, password, email=None, groups=None, **cwuserkwargs):
        cnx = self._cw
        if isinstance(password, str):
            # password should *always* be utf8 encoded
            password = password.encode('UTF8')
        cwuserkwargs['login'] = login
        cwuserkwargs['upassword'] = password
        # we have to create the user
        user = cnx.create_entity('CWUser', **cwuserkwargs)
        if groups is None:
            groups = self.default_groups
        assert groups, "CWUsers must belong to at least one CWGroup"
        group_names = ', '.join('%r' % group for group in groups)
        cnx.execute('SET X in_group G WHERE X eid %%(x)s, G name IN (%s)' % group_names,
                    {'x': user.eid})
        if email or '@' in login:
            d = {'login': login, 'email': email or login}
            cnx.execute('INSERT EmailAddress X: X address %(email)s, '
                        'U primary_email X, U use_email X '
                        'WHERE U login %(login)s', d, build_descr=False)

        return user


class SourceSynchronizationService(Service):
    """Force synchronization of a datafeed source. Actual synchronization is done
    asynchronously, this will simply create and return the entity which will hold the import
    log.
    """
    __regid__ = 'source-sync'
    __select__ = Service.__select__ & match_user_groups('managers')

    def call(self, source_eid):
        source = self._cw.repo.source_by_eid(source_eid)
        result = source.pull_data(self._cw, force=True, sync=False)
        return result['import_log_eid']
