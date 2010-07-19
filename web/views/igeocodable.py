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
"""Specific views for entities implementing IGeocodable"""

__docformat__ = "restructuredtext en"

from cubicweb.interfaces import IGeocodable
from cubicweb.view import EntityView, EntityAdapter, implements_adapter_compat
from cubicweb.selectors import implements, adaptable
from cubicweb.utils import json_dumps

class IGeocodableAdapter(EntityAdapter):
    """interface required by geocoding views such as gmap-view"""
    __regid__ = 'IGeocodable'
    __select__ = implements(IGeocodable, warn=False) # XXX for bw compat, should be abstract

    @property
    @implements_adapter_compat('IGeocodable')
    def latitude(self):
        """returns the latitude of the entity"""
        raise NotImplementedError

    @property
    @implements_adapter_compat('IGeocodable')
    def longitude(self):
        """returns the longitude of the entity"""
        raise NotImplementedError

    @implements_adapter_compat('IGeocodable')
    def marker_icon(self):
        """returns the icon that should be used as the marker.

        an icon is defined by a 4-uple:

          (icon._url, icon.size,  icon.iconAnchor, icon.shadow)
        """
        return (self._cw.uiprops['GMARKER_ICON'], (20, 34), (4, 34), None)


class GeocodingJsonView(EntityView):
    __regid__ = 'geocoding-json'
    __select__ = adaptable('IGeocodable')

    binary = True
    templatable = False
    content_type = 'application/json'

    def call(self):
        zoomlevel = self._cw.form.pop('zoomlevel', 8)
        extraparams = self._cw.form.copy()
        extraparams.pop('vid', None)
        extraparams.pop('rql', None)
        markers = []
        for entity in self.cw_rset.entities():
            igeocodable = entity.cw_adapt_to('IGeocodable')
            # remove entities that don't define latitude and longitude
            if not (igeocodable.latitude and igeocodable.longitude):
                continue
            markers.append(self.build_marker_data(entity, igeocodable,
                                                  extraparams))
        center = {
            'latitude': sum(marker['latitude'] for marker in markers) / len(markers),
            'longitude': sum(marker['longitude'] for marker in markers) / len(markers),
            }
        geodata = {
            'zoomlevel': int(zoomlevel),
            'center': center,
            'markers': markers,
            }
        self.w(json_dumps(geodata))

    def build_marker_data(self, entity, igeocodable, extraparams):
        return {'latitude': igeocodable.latitude,
                'longitude': igeocodable.longitude,
                'icon': igeocodable.marker_icon(),
                'title': entity.dc_long_title(),
                'bubbleUrl': entity.absolute_url(
                    vid='gmap-bubble', __notemplate=1, **extraparams),
                }


class GoogleMapBubbleView(EntityView):
    __regid__ = 'gmap-bubble'
    __select__ = adaptable('IGeocodable')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        self.w(u'<div>%s</div>' % entity.view('oneline'))
        # FIXME: we should call something like address-view if available


class GoogleMapsView(EntityView):
    __regid__ = 'gmap-view'
    __select__ = adaptable('IGeocodable')

    paginable = False

    def call(self, gmap_key, width=400, height=400, uselabel=True, urlparams=None):
        self._cw.demote_to_html()
        self._cw.add_js('http://maps.google.com/maps?sensor=false&file=api&v=2&key=%s'
                        % gmap_key, localfile=False)
        self._cw.add_js( ('cubicweb.widgets.js', 'cubicweb.gmap.js', 'gmap.utility.labeledmarker.js') )
        rql = self.cw_rset.printable_rql()
        if urlparams is None:
            loadurl = self._cw.build_url(rql=rql, vid='geocoding-json')
        else:
            loadurl = self._cw.build_url(rql=rql, vid='geocoding-json', **urlparams)
        self.w(u'<div style="width: %spx; height: %spx;" class="widget gmap" '
               u'cubicweb:wdgtype="GMapWidget" cubicweb:loadtype="auto" '
               u'cubicweb:loadurl="%s" cubicweb:uselabel="%s"> </div>'
               % (width, height, loadurl, uselabel))


class GoogeMapsLegend(EntityView):
    __regid__ = 'gmap-legend'

    def call(self):
        self.w(u'<ol>')
        for rowidx in xrange(len(self.cw_rset)):
            self.w(u'<li>')
            self.wview('listitem', self.cw_rset, row=rowidx, col=0)
            self.w(u'</li>')
        self.w(u'</ol>')
