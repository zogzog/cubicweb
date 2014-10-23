# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from yams.schema import role_name
from cubicweb import ValidationError
from cubicweb.server import Service
from cubicweb.predicates import match_user_groups, match_kwargs

class StatsService(Service):
    """Return a dictionary containing some statistics about the repository
    resources usage.
    """

    __regid__  = 'repo_stats'
    __select__ = match_user_groups('managers', 'users')

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

class GcStatsService(Service):
    """Return a dictionary containing some statistics about the repository
    resources usage.
    """

    __regid__  = 'repo_gc_stats'
    __select__ = match_user_groups('managers')

    def call(self, nmax=20):
        """Return a dictionary containing some statistics about the repository
        memory usage.

        This is a public method, not requiring a session id.

        nmax is the max number of (most) referenced object returned as
        the 'referenced' result
        """

        from cubicweb._gcdebug import gc_info
        from cubicweb.appobject import AppObject
        from cubicweb.rset import ResultSet
        from cubicweb.dbapi import Connection, Cursor
        from cubicweb.web.request import CubicWebRequestBase
        from rql.stmts import Union

        lookupclasses = (AppObject,
                         Union, ResultSet,
                         Connection, Cursor,
                         CubicWebRequestBase)
        try:
            from cubicweb.server.session import Session, InternalSession
            lookupclasses += (InternalSession, Session)
        except ImportError:
            pass  # no server part installed

        results = {}
        counters, ocounters, garbage = gc_info(lookupclasses,
                                               viewreferrersclasses=())
        values = sorted(counters.iteritems(), key=lambda x: x[1], reverse=True)
        results['lookupclasses'] = values
        values = sorted(ocounters.iteritems(), key=lambda x: x[1], reverse=True)[:nmax]
        results['referenced'] = values
        results['unreachable'] = len(garbage)
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
        errmsg = cnx._('the value "%s" is already used, use another one')

        if (cnx.execute('CWUser X WHERE X login %(login)s', {'login': login},
                        build_descr=False)
            or cnx.execute('CWUser X WHERE X use_email C, C address %(login)s',
                           {'login': login}, build_descr=False)):
            qname = role_name('login', 'subject')
            raise ValidationError(None, {qname: errmsg % login})

        if isinstance(password, unicode):
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
            if cnx.execute('EmailAddress X WHERE X address %(email)s', d,
                           build_descr=False):
                qname = role_name('address', 'subject')
                raise ValidationError(None, {qname: errmsg % d['email']})
            cnx.execute('INSERT EmailAddress X: X address %(email)s, '
                        'U primary_email X, U use_email X '
                        'WHERE U login %(login)s', d, build_descr=False)

        return user
