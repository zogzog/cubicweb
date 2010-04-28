# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""

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
