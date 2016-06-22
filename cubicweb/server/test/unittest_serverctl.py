import os.path as osp
import shutil

from cubicweb import ExecutionError
from cubicweb.devtools import testlib, ApptestConfiguration
from cubicweb.server.serverctl import _local_dump, DBDumpCommand, SynchronizeSourceCommand
from cubicweb.server.serverconfig import ServerConfiguration

class ServerCTLTC(testlib.CubicWebTC):
    def setUp(self):
        super(ServerCTLTC, self).setUp()
        self.orig_config_for = ServerConfiguration.config_for
        config_for = lambda appid: ApptestConfiguration(appid, __file__)
        ServerConfiguration.config_for = staticmethod(config_for)

    def tearDown(self):
        ServerConfiguration.config_for = self.orig_config_for
        super(ServerCTLTC, self).tearDown()

    def test_dump(self):
        DBDumpCommand(None).run([self.appid])
        shutil.rmtree(osp.join(self.config.apphome, 'backup'))

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
