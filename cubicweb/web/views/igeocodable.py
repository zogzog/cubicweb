# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Specific views for entities implementing IGeocodable"""

try:
    from cubes.geocoding.views import (IGeocodableAdapter,
                                       GeocodingJsonView,
                                       GoogleMapBubbleView,
                                       GoogleMapsView,
                                       GoogeMapsLegend)

    from logilab.common.deprecation import class_moved

    msg = '[3.17] cubicweb.web.views.igeocodable moved to cubes.geocoding.views'
    IGeocodableAdapter = class_moved(IGeocodableAdapter, message=msg)
    GeocodingJsonView = class_moved(GeocodingJsonView, message=msg)
    GoogleMapBubbleView = class_moved(GoogleMapBubbleView, message=msg)
    GoogleMapsView = class_moved(GoogleMapsView, message=msg)
    GoogeMapsLegend = class_moved(GoogeMapsLegend, message=msg)
except ImportError:
    from cubicweb.web import LOGGER
    LOGGER.warning('[3.17] igeocoding extracted to cube geocoding that was not found. try installing it.')
