# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""server side objects"""

import os.path as osp

def registration_callback(vreg):
    vreg.register_all(globals().values(), __name__)
    global URL_MAPPING
    URL_MAPPING = {}
    if vreg.config.apphome:
        url_mapping_file = osp.join(vreg.config.apphome, 'urlmapping.py')
        if osp.exists(url_mapping_file):
            URL_MAPPING = eval(open(url_mapping_file).read())
            vreg.info('using url mapping %s from %s', URL_MAPPING, url_mapping_file)
