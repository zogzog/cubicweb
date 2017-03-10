import os.path as osp
import shutil

from mock import patch

from cubicweb import ExecutionError
from cubicweb.devtools import testlib, ApptestConfiguration
from cubicweb.server.serverctl import (
    DBDumpCommand,
    RepositorySchedulerCommand,
    SynchronizeSourceCommand,
)
from cubicweb.server.serverconfig import ServerConfiguration


class ServerCTLTC(testlib.CubicWebTC):

    def setUp(self):
        super(ServerCTLTC, self).setUp()
        self.orig_config_for = ServerConfiguration.config_for

        def config_for(appid):
            return ApptestConfiguration(appid, __file__)

        ServerConfiguration.config_for = staticmethod(config_for)

    def tearDown(self):
        ServerConfiguration.config_for = self.orig_config_for
        super(ServerCTLTC, self).tearDown()

    def test_dump(self):
        DBDumpCommand(None).run([self.appid])
        shutil.rmtree(osp.join(self.config.apphome, 'backup'))

    def test_scheduler(self):
        cmd = RepositorySchedulerCommand(None)
        with patch('sched.scheduler.run',
                   side_effect=RuntimeError('boom')) as patched_run:
            with self.assertRaises(RuntimeError) as exc_cm:
                with self.assertLogs('cubicweb.repository', level='INFO') as log_cm:
                    cmd.run([self.appid])
        # make sure repository scheduler started
        scheduler_start_message = (
            'INFO:cubicweb.repository:starting repository scheduler with '
            'tasks: update_feeds, expire_dataimports'
        )
        self.assertIn(scheduler_start_message, log_cm.output)
        # and that scheduler's run method got called
        self.assertIn('boom', str(exc_cm.exception))
        patched_run.assert_called_once_with()
        # make sure repository's shutdown method got called
        repo_shutdown_message = 'INFO:cubicweb.repository:shutting down repository'
        self.assertIn(repo_shutdown_message, log_cm.output)

    def test_source_sync(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.create_entity('CWSource', name=u'success_feed', type=u'datafeed',
                              parser=u'test_source_parser_success',
                              url=u'ignored')
            cnx.create_entity('CWSource', name=u'fail_feed', type=u'datafeed',
                              parser=u'test_source_parser_fail',
                              url=u'ignored')
            cnx.commit()

            cmd = SynchronizeSourceCommand(None)
            cmd.config.force = 1

            # Should sync all sources even if one failed
            with self.assertRaises(ExecutionError) as exc:
                cmd.run([self.appid])
            self.assertEqual(len(cnx.find('Card', title=u'success')), 1)
            self.assertEqual(len(cnx.find('Card', title=u'fail')), 0)
            self.assertEqual(str(exc.exception), 'All sources where not synced')

            # call with named sources
            cmd.run([self.appid, u'success_feed'])
            self.assertEqual(len(cnx.find('Card', title=u'success')), 2)

            with self.assertRaises(ExecutionError) as exc:
                cmd.run([self.appid, u'fail_feed'])
            self.assertEqual(str(exc.exception), 'All sources where not synced')
            self.assertEqual(len(cnx.find('Card', title=u'fail')), 0)


if __name__ == '__main__':
    from unittest import main
    main()
