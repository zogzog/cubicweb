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
"""Set of HTML generic base views:

* noresult, final
* primary, sidebox
* oneline, incontext, outofcontext, text
* list
"""

__docformat__ = "restructuredtext en"
_ = unicode

from datetime import timedelta
from warnings import warn

from rql import nodes

from logilab.mtconverter import TransformError, xml_escape, xml_escape

from cubicweb import NoSelectableObject, tags
from cubicweb.selectors import yes, empty_rset, one_etype_rset, match_kwargs
from cubicweb.schema import display_name
from cubicweb.view import EntityView, AnyRsetView, View
from cubicweb.uilib import cut, printable_value
from cubicweb.web.views import calendar


class NullView(AnyRsetView):
    """default view when no result has been found"""
    __regid__ = 'null'
    __select__ = yes()
    def call(self, **kwargs):
        pass
    cell_call = call


class NoResultView(View):
    """default view when no result has been found"""
    __select__ = empty_rset()
    __regid__ = 'noresult'

    def call(self, **kwargs):
        self.w(u'<div class="searchMessage"><strong>%s</strong></div>\n'
               % self._cw._('No result matching query'))


class FinalView(AnyRsetView):
    """display values without any transformation (i.e. get a number for
    entities)
    """
    __regid__ = 'final'
    # record generated i18n catalog messages
    _('%d&#160;years')
    _('%d&#160;months')
    _('%d&#160;weeks')
    _('%d&#160;days')
    _('%d&#160;hours')
    _('%d&#160;minutes')
    _('%d&#160;seconds')
    _('%d years')
    _('%d months')
    _('%d weeks')
    _('%d days')
    _('%d hours')
    _('%d minutes')
    _('%d seconds')

    def cell_call(self, row, col, props=None, format='text/html'):
        etype = self.cw_rset.description[row][col]
        value = self.cw_rset.rows[row][col]

        if value is None:
            self.w(u'')
            return
        if etype == 'String':
            entity, rtype = self.cw_rset.related_entity(row, col)
            if entity is not None:
                # yes !
                self.w(entity.printable_value(rtype, value, format=format))
                return
        elif etype in ('Time', 'Interval'):
            if etype == 'Interval' and isinstance(value, (int, long)):
                # `date - date`, unlike `datetime - datetime` gives an int
                # (number of days), not a timedelta
                # XXX should rql be fixed to return Int instead of Interval in
                #     that case? that would be probably the proper fix but we
                #     loose information on the way...
                value = timedelta(days=value)
            # value is DateTimeDelta but we have no idea about what is the
            # reference date here, so we can only approximate years and months
            if format == 'text/html':
                space = '&#160;'
            else:
                space = ' '
            if value.days > 730: # 2 years
                self.w(self._cw.__('%%d%syears' % space) % (value.days // 365))
            elif value.days > 60: # 2 months
                self.w(self._cw.__('%%d%smonths' % space) % (value.days // 30))
            elif value.days > 14: # 2 weeks
                self.w(self._cw.__('%%d%sweeks' % space) % (value.days // 7))
            elif value.days > 2:
                self.w(self._cw.__('%%d%sdays' % space) % int(value.days))
            elif value.seconds > 3600:
                self.w(self._cw.__('%%d%shours' % space) % int(value.seconds // 3600))
            elif value.seconds >= 120:
                self.w(self._cw.__('%%d%sminutes' % space) % int(value.seconds // 60))
            else:
                self.w(self._cw.__('%%d%sseconds' % space) % int(value.seconds))
            return
        self.wdata(printable_value(self._cw, etype, value, props))


# XXX deprecated
class SecondaryView(EntityView):
    __regid__ = 'secondary'
    title = _('secondary')

    def cell_call(self, row, col, **kwargs):
        """the secondary view for an entity
        secondary = icon + view(oneline)
        """
        entity = self.cw_rset.get_entity(row, col)
        self.w(u'&#160;')
        self.wview('oneline', self.cw_rset, row=row, col=col)


class OneLineView(EntityView):
    __regid__ = 'oneline'
    title = _('oneline')

    def cell_call(self, row, col, **kwargs):
        """the one line view for an entity: linked text view
        """
        entity = self.cw_rset.get_entity(row, col)
        self.w(u'<a href="%s">' % xml_escape(entity.absolute_url()))
        self.w(xml_escape(self._cw.view('text', self.cw_rset, row=row, col=col)))
        self.w(u'</a>')


class TextView(EntityView):
    """the simplest text view for an entity"""
    __regid__ = 'text'
    title = _('text')
    content_type = 'text/plain'

    def call(self, **kwargs):
        """the view is called for an entire result set, by default loop
        other rows of the result set and call the same view on the
        particular row

        Views applicable on None result sets have to override this method
        """
        rset = self.cw_rset
        if rset is None:
            raise NotImplementedError, self
        for i in xrange(len(rset)):
            self.wview(self.__regid__, rset, row=i, **kwargs)
            if len(rset) > 1:
                self.w(u"\n")

    def cell_call(self, row, col=0, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        self.w(cut(entity.dc_title(),
                   self._cw.property_value('navigation.short-line-size')))


class MetaDataView(EntityView):
    """paragraph view of some metadata"""
    __regid__ = 'metadata'
    show_eid = True

    def cell_call(self, row, col):
        _ = self._cw._
        entity = self.cw_rset.get_entity(row, col)
        self.w(u'<div class="metadata">')
        if self.show_eid:
            self.w(u'%s #%s - ' % (entity.dc_type(), entity.eid))
        if entity.modification_date != entity.creation_date:
            self.w(u'<span>%s</span> ' % _('latest update on'))
            self.w(u'<span class="value">%s</span>, '
                   % self._cw.format_date(entity.modification_date))
        # entities from external source may not have a creation date (eg ldap)
        if entity.creation_date:
            self.w(u'<span>%s</span> ' % _('created on'))
            self.w(u'<span class="value">%s</span>'
                   % self._cw.format_date(entity.creation_date))
        if entity.creator:
            self.w(u' <span>%s</span> ' % _('by'))
            self.w(u'<span class="value">%s</span>' % entity.creator.name())
        self.w(u'</div>')


class InContextTextView(TextView):
    __regid__ = 'textincontext'
    title = None # not listed as a possible view
    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        self.w(entity.dc_title())


class OutOfContextTextView(InContextTextView):
    __regid__ = 'textoutofcontext'

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        self.w(entity.dc_long_title())


class InContextView(EntityView):
    __regid__ = 'incontext'

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        desc = cut(entity.dc_description(), 50)
        self.w(u'<a href="%s" title="%s">' % (
            xml_escape(entity.absolute_url()), xml_escape(desc)))
        self.w(xml_escape(self._cw.view('textincontext', self.cw_rset,
                                        row=row, col=col)))
        self.w(u'</a>')


class OutOfContextView(EntityView):
    __regid__ = 'outofcontext'

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        desc = cut(entity.dc_description(), 50)
        self.w(u'<a href="%s" title="%s">' % (
            xml_escape(entity.absolute_url()), xml_escape(desc)))
        self.w(xml_escape(self._cw.view('textoutofcontext', self.cw_rset,
                                        row=row, col=col)))
        self.w(u'</a>')


# list views ##################################################################

class ListView(EntityView):
    __regid__ = 'list'
    title = _('list')
    item_vid = 'listitem'

    def call(self, klass=None, title=None, subvid=None, listid=None, **kwargs):
        """display a list of entities by calling their <item_vid> view

        :param listid: the DOM id to use for the root element
        """
        # XXX much of the behaviour here should probably be outside this view
        if subvid is None and 'subvid' in self._cw.form:
            subvid = self._cw.form.pop('subvid') # consume it
        if listid:
            listid = u' id="%s"' % listid
        else:
            listid = u''
        if title:
            self.w(u'<div%s class="%s"><h4>%s</h4>\n' % (listid, klass or 'section', title))
            self.w(u'<ul>\n')
        else:
            self.w(u'<ul%s class="%s">\n' % (listid, klass or 'section'))
        for i in xrange(self.cw_rset.rowcount):
            self.cell_call(row=i, col=0, vid=subvid, **kwargs)
        self.w(u'</ul>\n')
        if title:
            self.w(u'</div>\n')

    def cell_call(self, row, col=0, vid=None, **kwargs):
        self.w(u'<li>')
        self.wview(self.item_vid, self.cw_rset, row=row, col=col, vid=vid, **kwargs)
        self.w(u'</li>\n')


class ListItemView(EntityView):
    __regid__ = 'listitem'

    @property
    def redirect_vid(self):
        if self._cw.search_state[0] == 'normal':
            return 'outofcontext'
        return 'outofcontext-search'

    def cell_call(self, row, col, vid=None, **kwargs):
        if not vid:
            vid = self.redirect_vid
        try:
            self.wview(vid, self.cw_rset, row=row, col=col, **kwargs)
        except NoSelectableObject:
            if vid == self.redirect_vid:
                raise
            self.wview(self.redirect_vid, self.cw_rset, row=row, col=col, **kwargs)


class SimpleListView(ListItemView):
    """list without bullets"""
    __regid__ = 'simplelist'
    redirect_vid = 'incontext'

    def call(self, subvid=None, **kwargs):
        """display a list of entities by calling their <item_vid> view

        :param listid: the DOM id to use for the root element
        """
        if subvid is None and 'vid' in kwargs:
            warn("should give a 'subvid' argument instead of 'vid'",
                 DeprecationWarning, stacklevel=2)
        else:
            kwargs['vid'] = subvid
        return super(SimpleListView, self).call(**kwargs)


class SameETypeListView(EntityView):
    """list of entities of the same type, when asked explicitly for same etype list
    view (for instance, display gallery if only images)
    """
    __regid__ = 'sameetypelist'
    __select__ = EntityView.__select__ & one_etype_rset()
    item_vid = 'sameetypelistitem'

    @property
    def title(self):
        etype = iter(self.cw_rset.column_types(0)).next()
        return display_name(self._cw, etype, form='plural')

    def call(self, **kwargs):
        """display a list of entities by calling their <item_vid> view"""
        showtitle = kwargs.pop('showtitle', not 'vtitle' in self._cw.form)
        if showtitle:
            self.w(u'<h1>%s</h1>' % self.title)
        super(SameETypeListView, self).call(**kwargs)

    def cell_call(self, row, col=0, **kwargs):
        self.wview(self.item_vid, self.cw_rset, row=row, col=col, **kwargs)


class SameETypeListItemView(EntityView):
    __regid__ = 'sameetypelistitem'

    def cell_call(self, row, col, **kwargs):
        self.wview('listitem', self.cw_rset, row=row, col=col, **kwargs)


class CSVView(SimpleListView):
    __regid__ = 'csv'
    redirect_vid = 'incontext'

    def call(self, subvid=None, **kwargs):
        if subvid is None and 'vid' in kwargs:
            warn("should give a 'subvid' argument instead of 'vid'",
                 DeprecationWarning, stacklevel=2)
        else:
            kwargs['vid'] = subvid
        rset = self.cw_rset
        for i in xrange(len(rset)):
            self.cell_call(i, 0, **kwargs)
            if i < rset.rowcount-1:
                self.w(u", ")


class TreeItemView(ListItemView):
    __regid__ = 'treeitem'

    def cell_call(self, row, col):
        self.wview('incontext', self.cw_rset, row=row, col=col)

class TextSearchResultView(EntityView):
    """this view is used to display full-text search

    It tries to highlight part of data where the search word appears.

    XXX: finish me (fixed line width, fixed number of lines, CSS, etc.)
    """
    __regid__ = 'tsearch'

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.complete_entity(row, col)
        self.w(entity.view('incontext'))
        searched = self.cw_rset.searched_text()
        if searched is None:
            return
        searched = searched.lower()
        highlighted = '<b>%s</b>' % searched
        for attr in entity.e_schema.indexable_attributes():
            try:
                value = xml_escape(entity.printable_value(attr, format='text/plain').lower())
            except TransformError, ex:
                continue
            except:
                continue
            if searched in value:
                contexts = []
                for ctx in value.split(searched):
                    if len(ctx) > 30:
                        contexts.append(u'...' + ctx[-30:])
                    else:
                        contexts.append(ctx)
                value = u'\n' + highlighted.join(contexts)
                self.w(value.replace('\n', '<br/>'))


class TooltipView(EntityView):
    """A entity view used in a tooltip"""
    __regid__ = 'tooltip'
    def cell_call(self, row, col):
        self.wview('oneline', self.cw_rset, row=row, col=col)


# XXX bw compat

from logilab.common.deprecation import class_moved

try:
    from cubicweb.web.views.tableview import TableView
    TableView = class_moved(TableView)
except ImportError:
    pass # gae has no tableview module (yet)

from cubicweb.web.views import boxes, xmlrss, primary
PrimaryView = class_moved(primary.PrimaryView)
SideBoxView = class_moved(boxes.SideBoxView)
XmlView = class_moved(xmlrss.XMLView)
XmlItemView = class_moved(xmlrss.XMLItemView)
XmlRsetView = class_moved(xmlrss.XMLRsetView)
RssView = class_moved(xmlrss.RSSView)
RssItemView = class_moved(xmlrss.RSSItemView)


class GroupByView(EntityView):
    """grouped view of a result set. The `group_key` method return the group
    key of an entities (a string or tuple of string).

    For each group, display a link to entities of this group by generating url
    like <basepath>/<key> or <basepath>/<key item 1>/<key item 2>.
    """
    __abstrack__ = True
    __select__ = EntityView.__select__ & match_kwargs('basepath')
    entity_attribute = None
    reversed = False

    def index_url(self, basepath, key, **kwargs):
        if isinstance(key, (list, tuple)):
            key = '/'.join(key)
        return self._cw.build_url('%s/%s' % (basepath, key),
                                  **kwargs)

    def index_link(self, basepath, key, items):
        url = self.index_url(basepath, key)
        if isinstance(key, (list, tuple)):
            key = ' '.join(key)
        return tags.a(key, href=url)

    def group_key(self, entity, **kwargs):
        value = getattr(entity, self.entity_attribute)
        if callable(value):
            value = value()
        return value

    def call(self, basepath, maxentries=None, **kwargs):
        index = {}
        for entity in self.cw_rset.entities():
            index.setdefault(self.group_key(entity, **kwargs), []).append(entity)
        displayed = sorted(index)
        if self.reversed:
            displayed = reversed(displayed)
        if maxentries is None:
            needmore = False
        else:
            needmore = len(index) > maxentries
            displayed = tuple(displayed)[:maxentries]
        w = self.w
        w(u'<ul class="boxListing">')
        for key in displayed:
            w(u'<li>%s</li>\n' %
              self.index_link(basepath, key, index[key]))
        if needmore:
            url = self._cw.build_url('view', vid=self.__regid__,
                                     rql=self.cw_rset.printable_rql())
            w( u'<li>%s</li>\n' % tags.a(u'[%s]' % self._cw._('see more'),
                                         href=url))
        w(u'</ul>\n')


class ArchiveView(GroupByView):
    """archive view of a result set. Links to months are built using a basepath
    parameters, eg using url like <basepath>/<year>/<month>
    """
    __regid__ = 'cw.archive.by_date'
    entity_attribute = 'creation_date'
    reversed = True

    def group_key(self, entity, **kwargs):
        value = super(ArchiveView, self).group_key(entity, **kwargs)
        return '%04d' % value.year, '%02d' % value.month

    def index_link(self, basepath, key, items):
        """represent a single month entry"""
        year, month = key
        label = u'%s %s [%s]' % (self._cw._(calendar.MONTHNAMES[int(month)-1]),
                                 year, len(items))
        etypes = set(entity.__regid__ for entity in items)
        vtitle = '%s %s' % (', '.join(display_name(self._cw, etype, 'plural')
                                      for etype in etypes),
                            label)
        title = self._cw._('archive for %(month)s/%(year)s') % {
            'month': month, 'year': year}
        url = self.index_url(basepath, key, vtitle=vtitle)
        return tags.a(label, href=url, title=title)


class AuthorView(GroupByView):
    """author view of a result set. Links to month are built using a basepath
    parameters, eg using url like <basepath>/<author>
    """
    __regid__ = 'cw.archive.by_author'
    entity_attribute = 'creator'

    def group_key(self, entity, **kwargs):
        value = super(AuthorView, self).group_key(entity, **kwargs)
        if value:
            return value.login
        return value

    def index_link(self, basepath, key, items):
        label = u'%s [%s]' % (key, len(items))
        etypes = set(entity.__regid__ for entity in items)
        vtitle = self._cw._('%(etype)s by %(author)s') % {
            'etype': ', '.join(display_name(self._cw, etype, 'plural')
                               for etype in etypes),
            'author': label}
        url = self.index_url(basepath, key, vtitle=vtitle)
        title = self._cw._('archive for %(author)s') % {'author': key}
        return tags.a(label, href=url, title=title)
