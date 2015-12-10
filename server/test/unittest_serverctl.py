import os.path as osp
import shutil

from cubicweb.devtools import testlib, ApptestConfiguration
from cubicweb.server.serverctl import _local_dump, DBDumpCommand
from cubicweb.server.serverconfig import ServerConfiguration

class ServerCTLTC(testlib.CubicWebTC):
    def setUp(self):
        super(ServerCTLTC, self).setUp()
        self.orig_config_for = ServerConfiguration.config_for
        config_for = lambda appid: ApptestConfiguration(appid, apphome=self.datadir)
        ServerConfiguration.config_for = staticmethod(config_for)

    def tearDown(self):
        ServerConfiguration.config_for = self.orig_config_for
        super(ServerCTLTC, self).tearDown()

    def test_dump(self):
        DBDumpCommand(None).run([self.appid])
        shutil.rmtree(osp.join(self.config.apphome, 'backup'))


if __name__ == '__main__':
    from unittest import main
    main()
