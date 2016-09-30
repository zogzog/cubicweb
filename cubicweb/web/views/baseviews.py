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
"""
HTML views
~~~~~~~~~~

Special views
`````````````

.. autoclass:: NullView
.. autoclass:: NoResultView
.. autoclass:: FinalView


Base entity views
`````````````````

.. autoclass:: InContextView
.. autoclass:: OutOfContextView
.. autoclass:: OneLineView

Those are used to display a link to an entity, whose label depends on the entity
having to be displayed in or out of context (of another entity): some entities
make sense in the context of another entity. For instance, the `Version` of a
`Project` in forge. So one may expect that 'incontext' will be called when
display a version from within the context of a project, while 'outofcontext"'
will be called in other cases. In our example, the 'incontext' view of the
version would be something like '0.1.2', while the 'outofcontext' view would
include the project name, e.g. 'baz 0.1.2' (since only a version number without
the associated project doesn't make sense if you don't know yet that you're
talking about the famous 'baz' project. |cubicweb| tries to make guess and call
'incontext'/'outofcontext' nicely. When it can't know, the 'oneline' view should
be used.


List entity views
`````````````````

.. autoclass:: ListView
.. autoclass:: SimpleListView
.. autoclass:: SameETypeListView
.. autoclass:: CSVView

Those list views can be given a 'subvid' arguments, telling the view to use of
each item in the list. When not specified, the value of the 'redirect_vid'
attribute of :class:`ListItemView` (for 'listview') or of
:class:`SimpleListView` will be used. This default to 'outofcontext' for 'list'
/ 'incontext' for 'simplelist'


Text entity views
~~~~~~~~~~~~~~~~~

Basic HTML view have some variants to be used when generating raw text, not HTML
(for notifications for instance). Also, as explained above, some of the HTML
views use those text views as a basis.

.. autoclass:: TextView
.. autoclass:: InContextTextView
.. autoclass:: OutOfContextView
"""

from cubicweb import _

from warnings import warn

from six.moves import range

from logilab.mtconverter import TransformError, xml_escape
from logilab.common.registry import yes

from cubicweb import NoSelectableObject, tags
from cubicweb.predicates import empty_rset, one_etype_rset, match_kwargs
from cubicweb.schema import display_name
from cubicweb.view import EntityView, AnyRsetView, View
from cubicweb.uilib import cut
from cubicweb.web.views import calendar


class NullView(AnyRsetView):
    """:__regid__: *null*

    This view is the default view used when nothing needs to be rendered. It is
    always applicable and is usually used as fallback view when calling
    :meth:`_cw.view` to display nothing if the result set is empty.
    """
    __regid__ = 'null'
    __select__ = yes()
    def call(self, **kwargs):
        pass
    cell_call = call


class NoResultView(View):
    """:__regid__: *noresult*

    This view is the default view to be used when no result has been found
    (i.e. empty result set).

    It's usually used as fallback view when calling :meth:`_cw.view` to display
    "no results" if the result set is empty.
    """
    __regid__ = 'noresult'
    __select__ = empty_rset()

    def call(self, **kwargs):
        self.w(u'<div class="searchMessage"><strong>%s</strong></div>\n'
               % self._cw._('No result matching query'))


class FinalView(AnyRsetView):
    """:__regid__: *final*

    Display the value of a result set cell with minimal transformations
    (i.e. you'll get a number for entities). It is applicable on any result set,
    though usually dedicated for cells containing an attribute's value.
    """
    __regid__ = 'final'

    def cell_call(self, row, col, props=None, format='text/html'):
        value = self.cw_rset.rows[row][col]
        if value is None:
            self.w(u'')
            return
        etype = self.cw_rset.description[row][col]
        if etype == 'String':
            entity, rtype = self.cw_rset.related_entity(row, col)
            if entity is not None:
                # call entity's printable_value which may have more information
                # about string format & all
                self.w(entity.printable_value(rtype, value, format=format))
                return
        value = self._cw.printable_value(etype, value, props)
        if etype in ('Time', 'Interval'):
            self.w(value.replace(' ', '&#160;'))
        else:
            self.wdata(value)


class InContextView(EntityView):
    """:__regid__: *incontext*

    This view is used when the entity should be considered as displayed in its
    context. By default it produces the result of ``entity.dc_title()`` wrapped in a
    link leading to the primary view of the entity.
    """
    __regid__ = 'incontext'

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        desc = cut(entity.dc_description(), 50)
        self.w(u'<a href="%s" title="%s">%s</a>' % (
            xml_escape(entity.absolute_url()), xml_escape(desc),
            xml_escape(entity.dc_title())))

class OutOfContextView(EntityView):
    """:__regid__: *outofcontext*

    This view is used when the entity should be considered as displayed out of
    its context. By default it produces the result of ``entity.dc_long_title()``
    wrapped in a link leading to the primary view of the entity.
    """
    __regid__ = 'outofcontext'

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        desc = cut(entity.dc_description(), 50)
        self.w(u'<a href="%s" title="%s">%s</a>' % (
            xml_escape(entity.absolute_url()), xml_escape(desc),
            xml_escape(entity.dc_long_title())))


class OneLineView(EntityView):
    """:__regid__: *oneline*

    This view is used when we can't tell if the entity should be considered as
    displayed in or out of context. By default it produces the result of the
    `text` view in a link leading to the primary view of the entity.
    """
    __regid__ = 'oneline'
    title = _('oneline')

    def cell_call(self, row, col, **kwargs):
        """the one line view for an entity: linked text view
        """
        entity = self.cw_rset.get_entity(row, col)
        desc = cut(entity.dc_description(), 50)
        title = cut(entity.dc_title(),
                    self._cw.property_value('navigation.short-line-size'))
        self.w(u'<a href="%s" title="%s">%s</a>' % (
                xml_escape(entity.absolute_url()), xml_escape(desc),
                xml_escape(title)))


# text views ###################################################################

class TextView(EntityView):
    """:__regid__: *text*

    This is the simplest text view for an entity. By default it returns the
    result of the entity's `dc_title()` method, which is cut to fit the
    `navigation.short-line-size` property if necessary.
    """
    __regid__ = 'text'
    title = _('text')
    content_type = 'text/plain'

    def call(self, **kwargs):
        """The view is called for an entire result set, by default loop other
        rows of the result set and call the same view on the particular row.

        Subclasses views that are applicable on None result sets will have to
        override this method.
        """
        rset = self.cw_rset
        if rset is None:
            raise NotImplementedError(self)
        for i in range(len(rset)):
            self.wview(self.__regid__, rset, row=i, **kwargs)
            if len(rset) > 1:
                self.w(u"\n")

    def cell_call(self, row, col=0, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        self.w(cut(entity.dc_title(),
                   self._cw.property_value('navigation.short-line-size')))


class InContextTextView(TextView):
    """:__regid__: *textincontext*

    Similar to the `text` view, but called when an entity is considered in
    context (see description of incontext HTML view for more information on
    this). By default it displays what's returned by the `dc_title()` method of
    the entity.
    """
    __regid__ = 'textincontext'
    title = None # not listed as a possible view
    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        self.w(entity.dc_title())


class OutOfContextTextView(InContextTextView):
    """:__regid__: *textoutofcontext*

    Similar to the `text` view, but called when an entity is considered out of
    context (see description of outofcontext HTML view for more information on
    this). By default it displays what's returned by the `dc_long_title()`
    method of the entity.
    """
    __regid__ = 'textoutofcontext'

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        self.w(entity.dc_long_title())


# list views ##################################################################

class ListView(EntityView):
    """:__regid__: *list*

    This view displays a list of entities by creating a HTML list (`<ul>`) and
    call the view `listitem` for each entity of the result set. The 'list' view
    will generate HTML like:

    .. sourcecode:: html

      <ul class="section">
        <li>"result of 'subvid' view for a row</li>
        ...
      </ul>

    If you wish to use a different view for each entity, either subclass and
    change the :attr:`item_vid` class attribute or specify a `subvid` argument
    when calling this view.
    """
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
        for i in range(self.cw_rset.rowcount):
            self.cell_call(row=i, col=0, vid=subvid, klass=klass, **kwargs)
        self.w(u'</ul>\n')
        if title:
            self.w(u'</div>\n')

    def cell_call(self, row, col=0, vid=None, klass=None, **kwargs):
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
    """:__regid__: *simplelist*

    Similar to :class:~cubicweb.web.views.baseviews.ListView but using '<div>'
    instead of '<ul>'. It rely on '<div>' behaviour to separate items. HTML will
    look like

    .. sourcecode:: html

      <div class="section">"result of 'subvid' view for a row</div>
      ...


    It relies on base :class:`~cubicweb.view.View` class implementation of the
    :meth:`call` method to insert those <div>.
    """
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
    """:__regid__: *sameetypelist*

    This view displays a list of entities of the same type, in HTML section
    ('<div>') and call the view `sameetypelistitem` for each entity of the
    result set. It's designed to get a more adapted global list when displayed
    entities are all of the same type (for instance, display gallery if there
    are only images entities).
    """
    __regid__ = 'sameetypelist'
    __select__ = EntityView.__select__ & one_etype_rset()
    item_vid = 'sameetypelistitem'

    @property
    def title(self):
        etype = next(iter(self.cw_rset.column_types(0)))
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
    """:__regid__: *csv*

    This view displays each entity in a coma separated list. It is NOT related
    to the well-known text file format.
    """
    __regid__ = 'csv'
    redirect_vid = 'incontext'
    separator = u', '

    def call(self, subvid=None, **kwargs):
        kwargs['vid'] = subvid
        rset = self.cw_rset
        for i in range(len(rset)):
            self.cell_call(i, 0, **kwargs)
            if i < rset.rowcount-1:
                self.w(self.separator)


# XXX to be documented views ###################################################

class MetaDataView(EntityView):
    """paragraph view of some metadata"""
    __regid__ = 'metadata'
    show_eid = True

    def cell_call(self, row, col):
        _ = self._cw._
        entity = self.cw_rset.get_entity(row, col)
        self.w(u'<div>')
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
            if entity.creation_date:
                self.w(u' <span>%s</span> ' % _('by'))
            else:
                self.w(u' <span>%s</span> ' % _('created_by'))
            self.w(u'<span class="value">%s</span>' % entity.creator.name())
        source = entity.cw_source[0]
        if source.name != 'system':
            self.w(u' (<span>%s</span>' % _('cw_source'))
            self.w(u' <span class="value">%s</span>)' % source.view('oneline'))
            source_def = self._cw.source_defs()[source.name]
            if source_def.get('use-cwuri-as-url'):
                self.w(u' <a href="%s">%s</span>' % (entity.cwuri, self._cw._('view original')))
        self.w(u'</div>')


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
            except TransformError as ex:
                continue
            except Exception:
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


class GroupByView(EntityView):
    """grouped view of a result set. The `group_key` method return the group
    key of an entities (a string or tuple of string).

    For each group, display a link to entities of this group by generating url
    like <basepath>/<key> or <basepath>/<key item 1>/<key item 2>.
    """
    __abstract__ = True
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
            if key:
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
        etypes = set(entity.cw_etype for entity in items)
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
            return (value.name(), value.login)
        return (None, None)

    def index_link(self, basepath, key, items):
        if key[0] is None:
            return
        label = u'%s [%s]' % (key[0], len(items))
        etypes = set(entity.cw_etype for entity in items)
        vtitle = self._cw._('%(etype)s by %(author)s') % {
            'etype': ', '.join(display_name(self._cw, etype, 'plural')
                               for etype in etypes),
            'author': label}
        url = self.index_url(basepath, key[1], vtitle=vtitle)
        title = self._cw._('archive for %(author)s') % {'author': key[0]}
        return tags.a(label, href=url, title=title)


# bw compat ####################################################################

from logilab.common.deprecation import class_moved, class_deprecated

from cubicweb.web.views import boxes, xmlrss, primary, tableview
PrimaryView = class_moved(primary.PrimaryView)
SideBoxView = class_moved(boxes.SideBoxView)
XmlView = class_moved(xmlrss.XMLView)
XmlItemView = class_moved(xmlrss.XMLItemView)
XmlRsetView = class_moved(xmlrss.XMLRsetView)
RssView = class_moved(xmlrss.RSSView)
RssItemView = class_moved(xmlrss.RSSItemView)
TableView = class_moved(tableview.TableView)
