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
"""module defining the root handler for a lax instance. You should not have
to change anything here.

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
