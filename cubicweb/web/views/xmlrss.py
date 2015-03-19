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
"""base xml and rss views"""

__docformat__ = "restructuredtext en"
from cubicweb import _

from base64 import b64encode
from time import timezone

from six.moves import range

from logilab.mtconverter import xml_escape

from cubicweb.predicates import (is_instance, non_final_entity, one_line_rset,
                                appobject_selectable, adaptable)
from cubicweb.view import EntityView, EntityAdapter, AnyRsetView, Component
from cubicweb.uilib import simple_sgml_tag
from cubicweb.web import httpcache, component

def encode_bytes(value):
    return '<![CDATA[%s]]>' % b64encode(value.getvalue())

# see cubicweb.sobjects.parser.DEFAULT_CONVERTERS
SERIALIZERS = {
    'String': xml_escape,
    'Bytes': encode_bytes,
    'Date': lambda x: x.strftime('%Y-%m-%d'),
    'Datetime': lambda x: x.strftime('%Y-%m-%d %H:%M:%S'),
    'Time': lambda x: x.strftime('%H:%M:%S'),
    'TZDatetime': lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), # XXX TZ
    'TZTime': lambda x: x.strftime('%H:%M:%S'),
    'Interval': lambda x: x.days * 60*60*24 + x.seconds,
    }

# base xml views ##############################################################

class XMLView(EntityView):
    """xml view for entities"""
    __regid__ = 'xml'
    title = _('xml export (entities)')
    templatable = False
    content_type = 'text/xml'
    xml_root = 'rset'
    item_vid = 'xmlitem'

    def cell_call(self, row, col):
        self.wview(self.item_vid, self.cw_rset, row=row, col=col)

    def call(self):
        """display a list of entities by calling their <item_vid> view"""
        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % self._cw.encoding)
        self.w(u'<%s size="%s">\n' % (self.xml_root, len(self.cw_rset)))
        for i in range(self.cw_rset.rowcount):
            self.cell_call(i, 0)
        self.w(u'</%s>\n' % self.xml_root)


class XMLItemView(EntityView):
    __regid__ = 'xmlitem'

    def entity_call(self, entity):
        """element as an item for an xml feed"""
        entity.complete()
        source = entity.cw_metainformation()['source']['uri']
        self.w(u'<%s eid="%s" cwuri="%s" cwsource="%s">\n'
               % (entity.cw_etype, entity.eid, xml_escape(entity.cwuri),
                  xml_escape(source)))
        for rschema, attrschema in sorted(entity.e_schema.attribute_definitions()):
            attr = rschema.type
            if attr in ('eid', 'cwuri'):
                continue
            else:
                try:
                    value = entity.cw_attr_cache[attr]
                except KeyError:
                    # Bytes
                    continue
            if value is None:
                self.w(u'  <%s/>\n' % attr)
            else:
                if attrschema in SERIALIZERS:
                    value = SERIALIZERS[attrschema](value)
                self.w(u'  <%s>%s</%s>\n' % (attr, value, attr))
        for relstr in self._cw.list_form_param('relation'):
            try:
                rtype, role = relstr.split('-')
            except ValueError:
                self.error('badly formated relation name %r', relstr)
                continue
            if role == 'subject':
                getrschema = entity.e_schema.subjrels
            elif role == 'object':
                getrschema = entity.e_schema.objrels
            else:
                self.error('badly formated relation name %r', relstr)
                continue
            if not rtype in getrschema:
                self.error('unexisting relation %r', relstr)
                continue
            self.w(u'  <%s role="%s">\n' % (rtype, role))
            self.wview('xmlrelateditem', entity.related(rtype, role, safe=True), 'null')
            self.w(u'  </%s>\n' % rtype)
        self.w(u'</%s>\n' % (entity.e_schema))


class XMLRelatedItemView(EntityView):
    __regid__ = 'xmlrelateditem'
    add_div_section = False

    def entity_call(self, entity):
        # XXX put unique attributes as xml attribute, they are much probably
        # used to search existing entities in client data feed, and putting it
        # here may avoid an extra request to get those attributes values
        self.w(u'    <%s eid="%s" cwuri="%s"/>\n'
               % (entity.e_schema, entity.eid, xml_escape(entity.cwuri)))


class XMLRelatedItemStateView(XMLRelatedItemView):
    __select__ = is_instance('State')

    def entity_call(self, entity):
        self.w(u'    <%s eid="%s" cwuri="%s" name="%s"/>\n'
               % (entity.e_schema, entity.eid, xml_escape(entity.cwuri),
                  xml_escape(entity.name)))


class XMLRsetView(AnyRsetView):
    """dumps raw rset as xml"""
    __regid__ = 'rsetxml'
    title = _('xml export')
    templatable = False
    content_type = 'text/xml'
    xml_root = 'rset'

    def call(self):
        w = self.w
        rset, descr = self.cw_rset, self.cw_rset.description
        eschema = self._cw.vreg.schema.eschema
        labels = self.columns_labels(tr=False)
        w(u'<?xml version="1.0" encoding="%s"?>\n' % self._cw.encoding)
        w(u'<%s query="%s">\n' % (self.xml_root, xml_escape(rset.printable_rql())))
        for rowindex, row in enumerate(self.cw_rset):
            w(u' <row>\n')
            for colindex, val in enumerate(row):
                etype = descr[rowindex][colindex]
                tag = labels[colindex]
                attrs = {}
                if '(' in tag:
                    attrs['expr'] = tag
                    tag = 'funccall'
                if val is not None and not eschema(etype).final:
                    attrs['eid'] = val
                    # csvrow.append(val) # val is eid in that case
                    val = self._cw.view('textincontext', rset,
                                        row=rowindex, col=colindex)
                else:
                    val = self._cw.view('final', rset, row=rowindex,
                                        col=colindex, format='text/plain')
                w(simple_sgml_tag(tag, val, **attrs))
            w(u'\n </row>\n')
        w(u'</%s>\n' % self.xml_root)


# RSS stuff ###################################################################

class IFeedAdapter(EntityAdapter):
    __needs_bw_compat__ = True
    __regid__ = 'IFeed'
    __select__ = is_instance('Any')

    def rss_feed_url(self):
        """return a URL to the rss feed for this entity"""
        return self.entity.absolute_url(vid='rss')


class RSSFeedURL(Component):
    __regid__ = 'rss_feed_url'
    __select__ = non_final_entity()

    def feed_url(self):
        return self._cw.build_url(rql=self.cw_rset.limited_rql(), vid='rss')


class RSSEntityFeedURL(Component):
    __regid__ = 'rss_feed_url'
    __select__ = one_line_rset() & adaptable('IFeed')

    def feed_url(self):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        return entity.cw_adapt_to('IFeed').rss_feed_url()


class RSSIconBox(component.CtxComponent):
    """just display the RSS icon on uniform result set"""
    __regid__ = 'rss'
    __select__ = (component.CtxComponent.__select__
                  & appobject_selectable('components', 'rss_feed_url'))

    visible = False
    order = 999

    def render(self, w, **kwargs):
        try:
            rss = self._cw.uiprops['RSS_LOGO']
        except KeyError:
            self.error('missing RSS_LOGO external resource')
            return
        urlgetter = self._cw.vreg['components'].select('rss_feed_url', self._cw,
                                                       rset=self.cw_rset)
        url = urlgetter.feed_url()
        w(u'<a href="%s"><img src="%s" alt="rss"/></a>\n' % (xml_escape(url), rss))


class RSSView(XMLView):
    __regid__ = 'rss'
    title = _('rss export')
    templatable = False
    content_type = 'text/xml'
    http_cache_manager = httpcache.MaxAgeHTTPCacheManager
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default
    item_vid = 'rssitem'

    def _open(self):
        req = self._cw
        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % req.encoding)
        self.w(u'<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">\n')
        self.w(u'  <channel>\n')
        self.w(u'    <title>%s RSS Feed</title>\n'
               % xml_escape(self.page_title()))
        self.w(u'    <description>%s</description>\n'
               % xml_escape(req.form.get('vtitle', '')))
        params = req.form.copy()
        params.pop('vid', None)
        self.w(u'    <link>%s</link>\n' % xml_escape(self._cw.build_url(**params)))

    def _close(self):
        self.w(u'  </channel>\n')
        self.w(u'</rss>')

    def call(self):
        """display a list of entities by calling their <item_vid> view"""
        self._open()
        for i in range(self.cw_rset.rowcount):
            self.cell_call(i, 0)
        self._close()

    def cell_call(self, row, col):
        self.wview(self.item_vid, self.cw_rset, row=row, col=col)


class RSSItemView(EntityView):
    __regid__ = 'rssitem'
    date_format = '%%Y-%%m-%%dT%%H:%%M%+03i:00' % (timezone / 3600)
    add_div_section = False

    def cell_call(self, row, col):
        entity = self.cw_rset.complete_entity(row, col)
        self.w(u'<item>\n')
        self.w(u'<guid isPermaLink="true">%s</guid>\n'
               % xml_escape(entity.absolute_url()))
        self.render_title_link(entity)
        self.render_description(entity)
        self._marker('dc:date', entity.dc_date(self.date_format))
        self.render_entity_creator(entity)
        self.w(u'</item>\n')

    def render_description(self, entity):
        self._marker('description', entity.dc_description(format='text/html'))

    def render_title_link(self, entity):
        self._marker('title', entity.dc_long_title())
        self._marker('link', entity.absolute_url())

    def render_entity_creator(self, entity):
        if entity.creator:
            self._marker('dc:creator', entity.dc_creator())

    def _marker(self, marker, value):
        if value:
            self.w(u'  <%s>%s</%s>\n' % (marker, xml_escape(value), marker))
