"""Specific views for entities implementing IGeocodable

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import simplejson

from cubicweb.interfaces import IGeocodable
from cubicweb.view import EntityView
from cubicweb.selectors import implements

class GeocodingJsonView(EntityView):
    id = 'geocoding-json'
    binary = True
    templatable = False
    content_type = 'application/json'

    __select__ = implements(IGeocodable)

    def call(self):
        # remove entities that don't define latitude and longitude
        self.rset = self.rset.filtered_rset(lambda e: e.latitude and e.longitude)
        zoomlevel = self.req.form.pop('zoomlevel', 8)
        extraparams = self.req.form.copy()
        extraparams.pop('vid', None)
        extraparams.pop('rql', None)
        markers = [self.build_marker_data(rowidx, extraparams)
                   for rowidx in xrange(len(self.rset))]
        center = {
            'latitude': sum(marker['latitude'] for marker in markers) / len(markers),
            'longitude': sum(marker['longitude'] for marker in markers) / len(markers),
            }
        geodata = {
            'zoomlevel': int(zoomlevel),
            'center': center,
            'markers': markers,
            }
        self.w(simplejson.dumps(geodata))

    def build_marker_data(self, row, extraparams):
        entity = self.entity(row, 0)
        icon = None
        if hasattr(entity, 'marker_icon'):
            icon = entity.marker_icon()
        else:
            icon = (self.req.external_resource('GMARKER_ICON'), (20, 34), (4, 34), None)
        return {'latitude': entity.latitude, 'longitude': entity.longitude,
                'title': entity.dc_long_title(),
                #icon defines : (icon._url, icon.size,  icon.iconAncho', icon.shadow)
                'icon': icon,
                'bubbleUrl': entity.absolute_url(vid='gmap-bubble', __notemplate=1, **extraparams),
                }


class GoogleMapBubbleView(EntityView):
    id = 'gmap-bubble'

    __select__ = implements(IGeocodable)

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        self.w(u'<div>%s</div>' % entity.view('oneline'))
        # FIXME: we should call something like address-view if available


class GoogleMapsView(EntityView):
    id = 'gmap-view'

    __select__ = implements(IGeocodable)
    paginable = False

    def call(self, gmap_key, width=400, height=400, uselabel=True, urlparams=None):
        self.req.demote_to_html()
        # remove entities that don't define latitude and longitude
        self.rset = self.rset.filtered_rset(lambda e: e.latitude and e.longitude)
        self.req.add_js('http://maps.google.com/maps?sensor=false&file=api&v=2&key=%s' % gmap_key,
                        localfile=False)
        self.req.add_js( ('cubicweb.widgets.js', 'cubicweb.gmap.js', 'gmap.utility.labeledmarker.js') )
        rql = self.rset.printable_rql()
        if urlparams is None:
            loadurl = self.build_url(rql=rql, vid='geocoding-json')
        else:
            loadurl = self.build_url(rql=rql, vid='geocoding-json', **urlparams)
        self.w(u'<div style="width: %spx; height: %spx;" class="widget gmap" '
               u'cubicweb:wdgtype="GMapWidget" cubicweb:loadtype="auto" '
               u'cubicweb:loadurl="%s" cubicweb:uselabel="%s"> </div>' % (width, height, loadurl, uselabel))


class GoogeMapsLegend(EntityView):
    id = 'gmap-legend'

    def call(self):
        self.w(u'<ol>')
        for rowidx in xrange(len(self.rset)):
            self.w(u'<li>')
            self.wview('listitem', self.rset, row=rowidx, col=0)
            self.w(u'</li>')
        self.w(u'</ol>')
