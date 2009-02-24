"""Primary view for bookmarks + user's bookmarks box

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb import Unauthorized
from cubicweb.selectors import implements
from cubicweb.web.htmlwidgets import BoxWidget, BoxMenu, RawBoxItem
from cubicweb.web.action import Action
from cubicweb.web.box import UserRQLBoxTemplate
from cubicweb.web.views.baseviews import PrimaryView


class FollowAction(Action):
    id = 'follow'
    __select__ = implements('Bookmark')

    title = _('follow')
    category = 'mainactions'
    
    def url(self):
        return self.rset.get_entity(self.row or 0, self.col or 0).actual_url()


class BookmarkPrimaryView(PrimaryView):
    __select__ = implements('Bookmark')
        
    def cell_call(self, row, col):
        """the primary view for bookmark entity"""
        entity = self.complete_entity(row, col)
        self.w(u'&nbsp;')
        self.w(u"<span class='title'><b>")
        self.w(u"%s : %s" % (self.req._('Bookmark'), html_escape(entity.title)))
        self.w(u"</b></span>")
        self.w(u'<br/><br/><div class="content"><a href="%s">' % (
            html_escape(entity.actual_url())))
        self.w(u'</a>')
        self.w(u'<p>%s%s</p>' % (self.req._('Used by:'), ', '.join(html_escape(u.name())
                                                                   for u in entity.bookmarked_by)))
        self.w(u'</div>')


class BookmarksBox(UserRQLBoxTemplate):
    """display a box containing all user's bookmarks"""
    id = 'bookmarks_box'
    order = 40
    title = _('bookmarks')
    rql = ('Any B,T,P ORDERBY lower(T) '
           'WHERE B is Bookmark,B title T, B path P, B bookmarked_by U, '
           'U eid %(x)s')
    etype = 'Bookmark'
    rtype = 'bookmarked_by'
    
    
    def call(self, **kwargs):
        req = self.req
        ueid = req.user.eid
        try:
            rset = req.execute(self.rql, {'x': ueid})
        except Unauthorized:
            # can't access to something in the query, forget this box
            return
        box = BoxWidget(req._(self.title), self.id)
        box.listing_class = 'sideBox'
        rschema = self.schema.rschema(self.rtype)
        eschema = self.schema.eschema(self.etype)
        candelete = rschema.has_perm(req, 'delete', toeid=ueid)
        if candelete:
            req.add_js( ('cubicweb.ajax.js', 'cubicweb.bookmarks.js') )
        else:
            dlink = None
        for bookmark in rset.entities():
            label = '<a href="%s">%s</a>' % (html_escape(bookmark.action_url()),
                                             html_escape(bookmark.title))
            if candelete:
                dlink = u'[<a href="javascript:removeBookmark(%s)" title="%s">-</a>]' % (
                    bookmark.eid, _('delete this bookmark'))
                label = '%s %s' % (dlink, label)
            box.append(RawBoxItem(label))
        if eschema.has_perm(req, 'add') and rschema.has_perm(req, 'add', toeid=ueid):
            boxmenu = BoxMenu(req._('manage bookmarks'))
            linkto = 'bookmarked_by:%s:subject' % ueid
            # use a relative path so that we can move the application without
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
                    url = self.build_url(vid='muledit', rql=bookmarksrql)
                    boxmenu.append(self.mk_action(self.req._('edit bookmarks'), url, category='manage'))
            url = req.user.absolute_url(vid='xaddrelation', rtype='bookmarked_by',
                                        target='subject')
            boxmenu.append(self.mk_action(self.req._('pick existing bookmarks'), url, category='manage'))
            box.append(boxmenu)
        if not box.is_empty():
            box.render(self.w)
