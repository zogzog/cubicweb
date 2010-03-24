"""core hooks

:organization: Logilab
:copyright: 2009-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from datetime import timedelta, datetime
from cubicweb.server import hook

class ServerStartupHook(hook.Hook):
    """task to cleanup expirated auth cookie entities"""
    __regid__ = 'cw_cleanup_transactions'
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
                    'DELETE FROM transaction WHERE tx_time < %(time)s',
                    {'time': mindate})
                # cleanup deleted entities
                session.system_sql(
                    'DELETE FROM deleted_entities WHERE dtime < %(time)s',
                    {'time': mindate})
                session.commit()
            finally:
                session.close()
        self.repo.looping_task(60*60*24, cleanup_old_transactions, self.repo)
