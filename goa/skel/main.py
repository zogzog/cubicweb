"""module defining the root handler for a lax application. You should not have
to change anything here.

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

# compute application's root directory
from os.path import dirname, abspath
APPLROOT = dirname(abspath(__file__))

# apply monkey patches first
from cubicweb import goa
goa.do_monkey_patch()

# get application's configuration (will be loaded from app.conf file)
from cubicweb.goa.goaconfig import GAEConfiguration
GAEConfiguration.ext_resources['JAVASCRIPTS'].append('DATADIR/goa.js')
config = GAEConfiguration('toto', APPLROOT)

# dynamic objects registry
from cubicweb.goa.goavreg import GAERegistry
vreg = GAERegistry(config, debug=goa.MODE == 'dev')

# trigger automatic classes registration (metaclass magic), should be done
# before schema loading
import custom

# load application'schema
vreg.schema = config.load_schema()

# load dynamic objects
vreg.load(APPLROOT)

# call the postinit so custom get a chance to do application specific stuff
custom.postinit(vreg)

from cubicweb.wsgi.handler import CubicWebWSGIApplication
application = CubicWebWSGIApplication(config, vreg=vreg)

# main function so this handler module is cached 
def main():
    from wsgiref.handlers import CGIHandler
    CGIHandler().run(application)

if __name__ == "__main__":
    main()
