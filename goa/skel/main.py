"""module defining the root handler for a lax instance. You should not have
to change anything here.

:organization: Logilab
:copyright: 2008-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

# compute instance's root directory
from os.path import dirname, abspath
APPLROOT = dirname(abspath(__file__))

# apply monkey patches first
from cubicweb import goa
goa.do_monkey_patch()

# get instance's configuration (will be loaded from app.conf file)
from cubicweb.goa.goaconfig import GAEConfiguration
GAEConfiguration.ext_resources['JAVASCRIPTS'].append('DATADIR/goa.js')
config = GAEConfiguration('toto', APPLROOT)

# dynamic objects registry
from cubicweb.goa.goavreg import GAEVregistry
vreg = GAEVregistry(config, debug=goa.MODE == 'dev')

# trigger automatic classes registration (metaclass magic), should be done
# before schema loading
import custom

# load instance'schema
vreg.schema = config.load_schema()

# load dynamic objects
vreg.load(APPLROOT)

# call the postinit so custom get a chance to do instance specific stuff
custom.postinit(vreg)

from cubicweb.wsgi.handler import CubicWebWSGIApplication
application = CubicWebWSGIApplication(config, vreg=vreg)

# main function so this handler module is cached
def main():
    from wsgiref.handlers import CGIHandler
    CGIHandler().run(application)

if __name__ == "__main__":
    main()
