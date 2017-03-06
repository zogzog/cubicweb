# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""dummy wsgi server for CubicWeb web instances"""



import socket

from cubicweb.wsgi.handler import CubicWebWSGIApplication
from cubicweb import ConfigurationError
from werkzeug.serving import run_simple

from logging import getLogger
LOGGER = getLogger('cubicweb')


def run(config):
    config.check_writeable_uid_directory(config.appdatahome)

    port = config['port'] or 8080
    interface = config['interface']

    app = CubicWebWSGIApplication(config)
    repo = app.appli.repo
    try:
        LOGGER.info('starting http server on %s', config['base-url'])
        run_simple(interface, port, app,
                   threaded=True,
                   use_debugger=True,
                   processes=1) # more processes yield weird errors
    finally:
        repo.shutdown()
