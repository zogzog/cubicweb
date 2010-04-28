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
from cubicweb import toolsutils
from cubicweb.devtools import DEFAULT_SOURCES, BaseApptestConfiguration

class RealDatabaseConfiguration(BaseApptestConfiguration):
    init_repository = False
    sourcesdef =  DEFAULT_SOURCES.copy()

    def sources(self):
        """
        By default, we run tests with the sqlite DB backend.
        One may use its own configuration by just creating a
        'sources' file in the test directory from wich tests are
        launched.
        """
        self._sources = self.sourcesdef
        return self._sources


def buildconfig(dbuser, dbpassword, dbname, adminuser, adminpassword, dbhost=None):
    """convenience function that builds a real-db configuration class"""
    sourcesdef =  {'system': {'adapter' : 'native',
                              'db-encoding' : 'UTF-8', #'ISO-8859-1',
                              'db-user' : dbuser,
                              'db-password' : dbpassword,
                              'db-name' : dbname,
                              'db-driver' : 'postgres',
                              'db-host' : dbhost,
                              },
                   'admin' : {'login': adminuser,
                              'password': adminpassword,
                              },
                   }
    return type('MyRealDBConfig', (RealDatabaseConfiguration,),
                {'sourcesdef': sourcesdef})


def loadconfig(filename):
    """convenience function that builds a real-db configuration class
    from a file
    """
    return type('MyRealDBConfig', (RealDatabaseConfiguration,),
                {'sourcesdef': toolsutils.read_config(filename)})
