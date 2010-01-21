"""Primary view for bookmarks + user's bookmarks box

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb import Unauthorized
from cubicweb.selectors import implements, one_line_rset
from cubicweb.web.htmlwidgets import BoxWidget, BoxMenu, RawBoxItem
from cubicweb.web import action, box, uicfg, formwidgets as fw
from cubicweb.web.views import primary

_abaa = uicfg.actionbox_appearsin_addmenu
_abaa.tag_subject_of(('*', 'bookmarked_by', '*'), False)
_abaa.tag_object_of(('*', 'bookmarked_by', '*'), False)

_afs = uicfg.autoform_section
_afs.tag_object_of(('*', 'bookmarked_by', 'CWUser'), 'main', 'metadata')
_afs.tag_attribute(('Bookmark', 'path'), 'main', 'attributes')
_afs.tag_attribute(('Bookmark', 'path'), 'muledit', 'attributes')

_affk = uicfg.autoform_field_kwargs
_affk.tag_attribute(('Bookmark', 'path'), {'widget': fw.URLUnescapedInput})


class FollowAction(action.Action):
    __regid__ = 'follow'
    __select__ = one_line_rset() & implements('Bookmark')

    title = _('follow')
    category = 'mainactions'

    def url(self):
        return self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0).actual_url()


class BookmarkPrimaryView(primary.PrimaryView):
    __select__ = implements('Bookmark')

    def cell_call(self, row, col):
        """the primary view for bookmark entity"""
        entity = self.cw_rset.complete_entity(row, col)
        self.w(u'&#160;')
        self.w(u"<span class='title'><b>")
        self.w(u"%s : %s" % (self._cw._('Bookmark'), xml_escape(entity.title)))
        self.w(u"</b></span>")
        self.w(u'<br/><br/><div class="content"><a href="%s">' % (
            xml_escape(entity.actual_url())))
        self.w(u'</a>')
        self.w(u'<p>%s%s</p>' % (self._cw._('Used by:'), ', '.join(xml_escape(u.name())
                                                                   for u in entity.bookmarked_by)))
        self.w(u'</div>')


class BookmarksBox(box.UserRQLBoxTemplate):
    """display a box containing all user's bookmarks"""
    __regid__ = 'bookmarks_box'
    order = 40
    title = _('bookmarks')
    rql = ('Any B,T,P ORDERBY lower(T) '
           'WHERE B is Bookmark,B title T, B path P, B bookmarked_by U, '
           'U eid %(x)s')
    etype = 'Bookmark'
    rtype = 'bookmarked_by'


    def call(self, **kwargs):
        req = self._cw
        ueid = req.user.eid
        try:
            rset = req.execute(self.rql, {'x': ueid})
        except Unauthorized:
            # can't access to something in the query, forget this box
            return
        box = BoxWidget(req._(self.title), self.__regid__)
        box.listing_class = 'sideBox'
        rschema = self._cw.vreg.schema.rschema(self.rtype)
        eschema = self._cw.vreg.schema.eschema(self.etype)
        candelete = rschema.has_perm(req, 'delete', toeid=ueid)
        if candelete:
            req.add_js( ('cubicweb.ajax.js', 'cubicweb.bookmarks.js') )
        else:
            dlink = None
        for bookmark in rset.entities():
            label = '<a href="%s">%s</a>' % (xml_escape(bookmark.action_url()),
                                             xml_escape(bookmark.title))
            if candelete:
                dlink = u'[<a href="javascript:removeBookmark(%s)" title="%s">-</a>]' % (
                    bookmark.eid, _('delete this bookmark'))
                label = '%s %s' % (dlink, label)
            box.append(RawBoxItem(label))
        if eschema.has_perm(req, 'add') and rschema.has_perm(req, 'add', toeid=ueid):
            boxmenu = BoxMenu(req._('manage bookmarks'))
            linkto = 'bookmarked_by:%s:subject' % ueid
            # use a relative path so that we can move the instance without
            # loosing bookmarks
            path = req.relative_path()
            url = self.create_url(self.etype, __linkto=linkto, path=path)
            boxmenu.append(self.mk_action(req._('bookmark this page'), url,
                                          category='manage', id='bookmark'))
            if rset:
                if req.user.is_in_group('managers'):
                    bookmarksrql = 'Bookmark B WHERE B bookmarked_by U, U eid %s' % ueid
                    erset = rset
                else:
                    # we can't edit shared bookmarks we don't own
                    bookmarksrql = 'Bookmark B WHERE B bookmarked_by U, B owned_by U, U eid %(x)s'
                    erset = req.execute(bookmarksrql, {'x': ueid}, 'x',
                                                build_descr=False)
                    bookmarksrql %= {'x': ueid}
                if erset:
                    url = self._cw.build_url(vid='muledit', rql=bookmarksrql)
                    boxmenu.append(self.mk_action(self._cw._('edit bookmarks'), url, category='manage'))
            url = req.user.absolute_url(vid='xaddrelation', rtype='bookmarked_by',
                                        target='subject')
            boxmenu.append(self.mk_action(self._cw._('pick existing bookmarks'), url, category='manage'))
            box.append(boxmenu)
        if not box.is_empty():
            box.render(self.w)
