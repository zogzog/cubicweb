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
