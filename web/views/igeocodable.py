"""Specific views for entities implementing IGeocodable

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.interfaces import IGeocodable
from cubicweb.view import EntityView
from cubicweb.selectors import implements
from cubicweb.web import json

class GeocodingJsonView(EntityView):
    __regid__ = 'geocoding-json'
    __select__ = implements(IGeocodable)

    binary = True
    templatable = False
    content_type = 'application/json'

    def call(self):
        # remove entities that don't define latitude and longitude
        self.cw_rset = self.cw_rset.filtered_rset(lambda e: e.latitude and e.longitude)
        zoomlevel = self._cw.form.pop('zoomlevel', 8)
        extraparams = self._cw.form.copy()
        extraparams.pop('vid', None)
        extraparams.pop('rql', None)
        markers = [self.build_marker_data(rowidx, extraparams)
                   for rowidx in xrange(len(self.cw_rset))]
        center = {
            'latitude': sum(marker['latitude'] for marker in markers) / len(markers),
            'longitude': sum(marker['longitude'] for marker in markers) / len(markers),
            }
        geodata = {
            'zoomlevel': int(zoomlevel),
            'center': center,
            'markers': markers,
            }
        self.w(json.dumps(geodata))

    def build_marker_data(self, row, extraparams):
        entity = self.cw_rset.get_entity(row, 0)
        icon = None
        if hasattr(entity, 'marker_icon'):
            icon = entity.marker_icon()
        else:
            icon = (self._cw.external_resource('GMARKER_ICON'), (20, 34), (4, 34), None)
        return {'latitude': entity.latitude, 'longitude': entity.longitude,
                'title': entity.dc_long_title(),
                #icon defines : (icon._url, icon.size,  icon.iconAncho', icon.shadow)
                'icon': icon,
                'bubbleUrl': entity.absolute_url(vid='gmap-bubble', __notemplate=1, **extraparams),
                }


class GoogleMapBubbleView(EntityView):
    __regid__ = 'gmap-bubble'
    __select__ = implements(IGeocodable)

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        self.w(u'<div>%s</div>' % entity.view('oneline'))
        # FIXME: we should call something like address-view if available


class GoogleMapsView(EntityView):
    __regid__ = 'gmap-view'
    __select__ = implements(IGeocodable)

    paginable = False

    def call(self, gmap_key, width=400, height=400, uselabel=True, urlparams=None):
        self._cw.demote_to_html()
        # remove entities that don't define latitude and longitude
        self.cw_rset = self.cw_rset.filtered_rset(lambda e: e.latitude and e.longitude)
        self._cw.add_js('http://maps.google.com/maps?sensor=false&file=api&v=2&key=%s' % gmap_key,
                        localfile=False)
        self._cw.add_js( ('cubicweb.widgets.js', 'cubicweb.gmap.js', 'gmap.utility.labeledmarker.js') )
        rql = self.cw_rset.printable_rql()
        if urlparams is None:
            loadurl = self._cw.build_url(rql=rql, vid='geocoding-json')
        else:
            loadurl = self._cw.build_url(rql=rql, vid='geocoding-json', **urlparams)
        self.w(u'<div style="width: %spx; height: %spx;" class="widget gmap" '
               u'cubicweb:wdgtype="GMapWidget" cubicweb:loadtype="auto" '
               u'cubicweb:loadurl="%s" cubicweb:uselabel="%s"> </div>' % (width, height, loadurl, uselabel))


class GoogeMapsLegend(EntityView):
    __regid__ = 'gmap-legend'

    def call(self):
        self.w(u'<ol>')
        for rowidx in xrange(len(self.cw_rset)):
            self.w(u'<li>')
            self.wview('listitem', self.cw_rset, row=rowidx, col=0)
            self.w(u'</li>')
        self.w(u'</ol>')
