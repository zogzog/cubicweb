"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.devtools import buildconfig, loadconfig
from cubicweb.devtools.testlib import RealDBTest

def setup_module(options):
    if options.source:
        configcls = loadconfig(options.source)
    elif options.dbname is None:
        raise Exception('either <sourcefile> or <dbname> options are required')
    else:
        configcls = buildconfig(options.dbuser, options.dbpassword,
                                               options.dbname, options.euser,
                                               options.epassword)
    RealDatabaseTC.configcls = configcls

class RealDatabaseTC(RealDBTest):
    configcls = None # set by setup_module()

    def test_all_primaries(self):
        for rset in self.iter_individual_rsets(limit=50):
            yield self.view, 'primary', rset, rset.req.reset_headers()

    ## startup views
    def test_startup_views(self):
        for vid in self.list_startup_views():
            req = self.request()
            yield self.view, vid, None, req


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
