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
"""Specific views for SIOC (Semantically-Interlinked Online Communities)

http://sioc-project.org
"""

from logilab.common.deprecation import class_moved

try:
    from cubes.sioc.views import *

    ISIOCItemAdapter = class_moved(ISIOCItemAdapter, message='[3.17] ISIOCItemAdapter moved to cubes.isioc.views')
    ISIOCContainerAdapter = class_moved(ISIOCContainerAdapter, message='[3.17] ISIOCContainerAdapter moved to cubes.isioc.views')
    SIOCView = class_moved(SIOCView, message='[3.17] SIOCView moved to cubes.is.view')
    SIOCContainerView = class_moved(SIOCContainerView, message='[3.17] SIOCContainerView moved to cubes.is.view')
    SIOCItemView = class_moved(SIOCItemView, message='[3.17] SIOCItemView moved to cubes.is.view')
except ImportError:
    from cubicweb.web import LOGGER
    LOGGER.warning('[3.17] isioc extracted to cube sioc that was not found. try installing it.')
