# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""core hooks registering some maintainance tasks as server startup time"""

__docformat__ = "restructuredtext en"

from datetime import timedelta, datetime

from cubicweb.server import hook

class ServerStartupHook(hook.Hook):
    """task to cleanup expirated auth cookie entities"""
    __regid__ = 'cw.start-looping-tasks'
    events = ('server_startup',)

    def __call__(self):
        # XXX use named args and inner functions to avoid referencing globals
        # which may cause reloading pb
        lifetime = timedelta(days=self.repo.config['keep-transaction-lifetime'])
        def cleanup_old_transactions(repo=self.repo, lifetime=lifetime):
            mindate = datetime.now() - lifetime
            session = repo.internal_session()
            try:
                session.system_sql(
                    'DELETE FROM transactions WHERE tx_time < %(time)s',
                    {'time': mindate})
                # cleanup deleted entities
                session.system_sql(
                    'DELETE FROM deleted_entities WHERE dtime < %(time)s',
                    {'time': mindate})
                session.commit()
            finally:
                session.close()
        self.repo.looping_task(60*60*24, cleanup_old_transactions, self.repo)
        def update_feeds(repo):
            session = repo.internal_session()
            try:
                # don't iter on repo.sources which doesn't include copy based
                # sources (the one we're looking for)
                for source in repo.sources_by_eid.itervalues():
                    if (not source.copy_based_source
                        or not repo.config.source_enabled(source)
                        or not source.config['synchronize']):
                        continue
                    try:
                        stats = source.pull_data(session)
                        if stats.get('created'):
                            source.info('added %s entities', len(stats['created']))
                        if stats.get('updated'):
                            source.info('updated %s entities', len(stats['updated']))
                    except Exception, exc:
                        session.exception('while trying to update feed %s', source)
                    session.set_cnxset()
            finally:
                session.close()
        self.repo.looping_task(60, update_feeds, self.repo)
