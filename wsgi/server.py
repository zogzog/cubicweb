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

__docformat__ = "restructuredtext en"

from cubicweb.wsgi.handler import CubicWebWSGIApplication
from cubicweb import ConfigurationError
from wsgiref import simple_server

from logging import getLogger
LOGGER = getLogger('cubicweb')


def run(config):
    config.check_writeable_uid_directory(config.appdatahome)

    port = config['port'] or 8080
    interface = config['interface']

    app = CubicWebWSGIApplication(config)
    handler_cls = simple_server.WSGIRequestHandler
    httpd = simple_server.WSGIServer((interface, port), handler_cls)
    httpd.set_app(app)
    repo = app.appli.repo
    try:
        repo.start_looping_tasks()
        LOGGER.info('starting http server on %s', config['base-url'])
        httpd.serve_forever()
    finally:
        repo.shutdown()
