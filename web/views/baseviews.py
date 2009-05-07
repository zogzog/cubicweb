"""Set of HTML generic base views:

* noresult, final
* primary, sidebox
* secondary, oneline, incontext, outofcontext, text
* list


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
#from __future__ import with_statement

__docformat__ = "restructuredtext en"

from rql import nodes

from logilab.mtconverter import TransformError, html_escape, xml_escape

from cubicweb import NoSelectableObject
from cubicweb.selectors import yes, empty_rset
from cubicweb.view import EntityView, AnyRsetView, View
from cubicweb.common.uilib import cut, printable_value

_ = unicode

class NullView(AnyRsetView):
    """default view when no result has been found"""
    id = 'null'
    __select__ = yes()
    def call(self, **kwargs):
        pass
    cell_call = call


class NoResultView(View):
    """default view when no result has been found"""
    __select__ = empty_rset()
    id = 'noresult'

    def call(self, **kwargs):
        self.w(u'<div class="searchMessage"><strong>%s</strong></div>\n'
               % self.req._('No result matching query'))


class FinalView(AnyRsetView):
    """display values without any transformation (i.e. get a number for
    entities)
    """
    id = 'final'
    # record generated i18n catalog messages
    _('%d&nbsp;years')
    _('%d&nbsp;months')
    _('%d&nbsp;weeks')
    _('%d&nbsp;days')
    _('%d&nbsp;hours')
    _('%d&nbsp;minutes')
    _('%d&nbsp;seconds')
    _('%d years')
    _('%d months')
    _('%d weeks')
    _('%d days')
    _('%d hours')
    _('%d minutes')
    _('%d seconds')

    def cell_call(self, row, col, props=None, displaytime=False, format='text/html'):
        etype = self.rset.description[row][col]
        value = self.rset.rows[row][col]
       
        if etype == 'String':
            entity, rtype = self.rset.related_entity(row, col)
            if entity is not None:
                # yes !
                self.w(entity.printable_value(rtype, value, format=format))
                return
        if etype in ('Time', 'Interval'):
            # value is DateTimeDelta but we have no idea about what is the
            # reference date here, so we can only approximate years and months
            if format == 'text/html':
                space = '&nbsp;'
            else:
                space = ' '
            if value.days > 730: # 2 years
                self.w(self.req.__('%%d%syears' % space) % (value.days // 365))
            elif value.days > 60: # 2 months
                self.w(self.req.__('%%d%smonths' % space) % (value.days // 30))
            elif value.days > 14: # 2 weeks
                self.w(self.req.__('%%d%sweeks' % space) % (value.days // 7))
            elif value.days > 2:
                self.w(self.req.__('%%d%sdays' % space) % int(value.days))
            elif value.seconds > 3600:
                self.w(self.req.__('%%d%shours' % space) % int(value.seconds // 3600))
            elif value.seconds >= 120:
                self.w(self.req.__('%%d%sminutes' % space) % int(value.seconds // 60))
            else:
                self.w(self.req.__('%%d%sseconds' % space) % int(value.seconds))
            return
        self.wdata(printable_value(self.req, etype, value, props, displaytime=displaytime))


class SecondaryView(EntityView):
    id = 'secondary'
    title = _('secondary')

    def cell_call(self, row, col):
        """the secondary view for an entity
        secondary = icon + view(oneline)
        """
        entity = self.entity(row, col)
        self.w(u'&nbsp;')
        self.wview('oneline', self.rset, row=row, col=col)


class OneLineView(EntityView):
    id = 'oneline'
    title = _('oneline')

    def cell_call(self, row, col):
        """the one line view for an entity: linked text view
        """
        entity = self.entity(row, col)
        self.w(u'<a href="%s">' % html_escape(entity.absolute_url()))
        self.w(html_escape(self.view('text', self.rset, row=row, col=col)))
        self.w(u'</a>')


class TextView(EntityView):
    """the simplest text view for an entity"""
    id = 'text'
    title = _('text')
    content_type = 'text/plain'

    def call(self, **kwargs):
        """the view is called for an entire result set, by default loop
        other rows of the result set and call the same view on the
        particular row

        Views applicable on None result sets have to override this method
        """
        rset = self.rset
        if rset is None:
            raise NotImplementedError, self
        for i in xrange(len(rset)):
            self.wview(self.id, rset, row=i, **kwargs)
            if len(rset) > 1:
                self.w(u"\n")

    def cell_call(self, row, col=0, **kwargs):
        entity = self.entity(row, col)
        self.w(cut(entity.dc_title(),
                   self.req.property_value('navigation.short-line-size')))


class MetaDataView(EntityView):
    """paragraph view of some metadata"""
    id = 'metadata'
    show_eid = True

    def cell_call(self, row, col):
        _ = self.req._
        entity = self.entity(row, col)
        self.w(u'<div class="metadata">')
        if self.show_eid:
            self.w(u'#%s - ' % entity.eid)
        if entity.modification_date != entity.creation_date:
            self.w(u'<span>%s</span> ' % _('latest update on'))
            self.w(u'<span class="value">%s</span>, '
                   % self.format_date(entity.modification_date))
        # entities from external source may not have a creation date (eg ldap)
        if entity.creation_date:
            self.w(u'<span>%s</span> ' % _('created on'))
            self.w(u'<span class="value">%s</span>'
                   % self.format_date(entity.creation_date))
        if entity.creator:
            self.w(u' <span>%s</span> ' % _('by'))
            self.w(u'<span class="value">%s</span>' % entity.creator.name())
        self.w(u'</div>')


# new default views for finner control in general views , to use instead of
# oneline / secondary

class InContextTextView(TextView):
    id = 'textincontext'
    title = None # not listed as a possible view
    def cell_call(self, row, col):
        entity = self.entity(row, col)
        self.w(entity.dc_title())


class OutOfContextTextView(InContextTextView):
    id = 'textoutofcontext'

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        self.w(entity.dc_long_title())


class InContextView(EntityView):
    id = 'incontext'

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        desc = cut(entity.dc_description(), 50)
        self.w(u'<a href="%s" title="%s">' % (html_escape(entity.absolute_url()),
                                              html_escape(desc)))
        self.w(html_escape(self.view('textincontext', self.rset, row=row, col=col)))
        self.w(u'</a>')


class OutOfContextView(EntityView):
    id = 'outofcontext'

    def cell_call(self, row, col):
        self.w(u'<a href="%s">' % self.entity(row, col).absolute_url())
        self.w(html_escape(self.view('textoutofcontext', self.rset, row=row, col=col)))
        self.w(u'</a>')


# list views ##################################################################

class ListView(EntityView):
    id = 'list'
    title = _('list')
    item_vid = 'listitem'

    def call(self, klass=None, title=None, subvid=None, listid=None, **kwargs):
        """display a list of entities by calling their <item_vid> view

        :param listid: the DOM id to use for the root element
        """
        if subvid is None and 'subvid' in self.req.form:
            subvid = self.req.form.pop('subvid') # consume it
        if listid:
            listid = u' id="%s"' % listid
        else:
            listid = u''
        if title:
            self.w(u'<div%s class="%s"><h4>%s</h4>\n' % (listid, klass or 'section', title))
            self.w(u'<ul>\n')
        else:
            self.w(u'<ul%s class="%s">\n' % (listid, klass or 'section'))
        for i in xrange(self.rset.rowcount):
            self.cell_call(row=i, col=0, vid=subvid, **kwargs)
        self.w(u'</ul>\n')
        if title:
            self.w(u'</div>\n')

    def cell_call(self, row, col=0, vid=None, **kwargs):
        self.w(u'<li>')
        self.wview(self.item_vid, self.rset, row=row, col=col, vid=vid, **kwargs)
        self.w(u'</li>\n')

    def url(self):
        """overrides url method so that by default, the view list is called
        with sorted entities
        """
        coltypes = self.rset.column_types(0)
        # don't want to generate the rql if there is some restriction on
        # something else than the entity type
        if len(coltypes) == 1:
            # XXX norestriction is not correct here. For instance, in cases like
            # Any P,N WHERE P is Project, P name N
            # norestriction should equal True
            restr = self.rset.syntax_tree().children[0].where
            norestriction = (isinstance(restr, nodes.Relation) and
                             restr.is_types_restriction())
            if norestriction:
                etype = iter(coltypes).next()
                return self.build_url(etype.lower(), vid=self.id)
        if len(self.rset) == 1:
            entity = self.rset.get_entity(0, 0)
            return self.build_url(entity.rest_path(), vid=self.id)
        return self.build_url(rql=self.rset.printable_rql(), vid=self.id)


class ListItemView(EntityView):
    id = 'listitem'

    @property
    def redirect_vid(self):
        if self.req.search_state[0] == 'normal':
            return 'outofcontext'
        return 'outofcontext-search'

    def cell_call(self, row, col, vid=None, **kwargs):
        if not vid:
            vid = self.redirect_vid
        try:
            self.wview(vid, self.rset, row=row, col=col, **kwargs)
        except NoSelectableObject:
            if vid == self.redirect_vid:
                raise
            self.wview(self.redirect_vid, self.rset, row=row, col=col, **kwargs)


class SimpleListView(ListItemView):
    """list without bullets"""
    id = 'simplelist'
    redirect_vid = 'incontext'


class CSVView(SimpleListView):
    id = 'csv'
    redirect_vid = 'incontext'

    def call(self, **kwargs):
        rset = self.rset
        for i in xrange(len(rset)):
            self.cell_call(i, 0, vid=kwargs.get('vid'))
            if i < rset.rowcount-1:
                self.w(u", ")


class TreeItemView(ListItemView):
    id = 'treeitem'

    def cell_call(self, row, col):
        self.wview('incontext', self.rset, row=row, col=col)

class TextSearchResultView(EntityView):
    """this view is used to display full-text search

    It tries to highlight part of data where the search word appears.

    XXX: finish me (fixed line width, fixed number of lines, CSS, etc.)
    """
    id = 'tsearch'

    def cell_call(self, row, col, **kwargs):
        entity = self.complete_entity(row, col)
        self.w(entity.view('incontext'))
        searched = self.rset.searched_text()
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
    id = 'tooltip'
    def cell_call(self, row, col):
        self.wview('oneline', self.rset, row=row, col=col)


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

