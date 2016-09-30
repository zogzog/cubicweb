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
"""Primary view for bookmarks + user's bookmarks box"""


from cubicweb import _

from logilab.mtconverter import xml_escape

from cubicweb import Unauthorized
from cubicweb.predicates import is_instance, one_line_rset
from cubicweb.web import action, component, htmlwidgets, formwidgets as fw
from cubicweb.web.views import uicfg, primary
from cubicweb.web.views.ajaxcontroller import ajaxfunc

_abaa = uicfg.actionbox_appearsin_addmenu
_abaa.tag_subject_of(('*', 'bookmarked_by', '*'), False)
_abaa.tag_object_of(('*', 'bookmarked_by', '*'), False)

_afs = uicfg.autoform_section
_afs.tag_object_of(('*', 'bookmarked_by', 'CWUser'), 'main', 'metadata')
_afs.tag_attribute(('Bookmark', 'path'), 'main', 'attributes')
_afs.tag_attribute(('Bookmark', 'path'), 'muledit', 'attributes')

_affk = uicfg.autoform_field_kwargs
_affk.tag_attribute(('Bookmark', 'path'), {'widget': fw.EditableURLWidget})


class FollowAction(action.Action):
    __regid__ = 'follow'
    __select__ = one_line_rset() & is_instance('Bookmark')

    title = _('follow')
    category = 'mainactions'

    def url(self):
        return self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0).actual_url()


class BookmarkPrimaryView(primary.PrimaryView):
    __select__ = is_instance('Bookmark')

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


class BookmarksBox(component.CtxComponent):
    """display a box containing all user's bookmarks"""
    __regid__ = 'bookmarks_box'

    title = _('bookmarks')
    order = 40
    rql = ('Any B,T,P ORDERBY lower(T) '
           'WHERE B is Bookmark,B title T, B path P, B bookmarked_by U, '
           'U eid %(x)s')

    def init_rendering(self):
        ueid = self._cw.user.eid
        self.bookmarks_rset = self._cw.execute(self.rql, {'x': ueid})
        rschema = self._cw.vreg.schema.rschema('bookmarked_by')
        eschema = self._cw.vreg.schema.eschema('Bookmark')
        self.can_delete = rschema.has_perm(self._cw, 'delete', toeid=ueid)
        self.can_edit = (eschema.has_perm(self._cw, 'add') and
                         rschema.has_perm(self._cw, 'add', toeid=ueid))
        if not self.bookmarks_rset and not self.can_edit:
            raise component.EmptyComponent()
        self.items = []

    def render_body(self, w):
        ueid = self._cw.user.eid
        req = self._cw
        if self.can_delete:
            req.add_js('cubicweb.ajax.js')
        for bookmark in self.bookmarks_rset.entities():
            label = self.link(bookmark.title, bookmark.action_url())
            if self.can_delete:
                dlink = u'[<a class="action" href="javascript:removeBookmark(%s)" title="%s">-</a>]' % (
                    bookmark.eid, req._('delete this bookmark'))
                label = '<div>%s %s</div>' % (dlink, label)
            self.append(label)
        if self.can_edit:
            menu = htmlwidgets.BoxMenu(req._('manage bookmarks'))
            linkto = 'bookmarked_by:%s:subject' % ueid
            # use a relative path so that we can move the instance without
            # loosing bookmarks
            path = req.relative_path()
            # XXX if vtitle specified in params, extract it and use it as
            # default value for bookmark's title
            url = req.vreg['etypes'].etype_class('Bookmark').cw_create_url(
                req, __linkto=linkto, path=path)
            menu.append(self.link(req._('bookmark this page'), url))
            if self.bookmarks_rset:
                if req.user.is_in_group('managers'):
                    bookmarksrql = 'Bookmark B WHERE B bookmarked_by U, U eid %s' % ueid
                    erset = self.bookmarks_rset
                else:
                    # we can't edit shared bookmarks we don't own
                    bookmarksrql = 'Bookmark B WHERE B bookmarked_by U, B owned_by U, U eid %(x)s'
                    erset = req.execute(bookmarksrql, {'x': ueid},
                                        build_descr=False)
                    bookmarksrql %= {'x': ueid}
                if erset:
                    url = req.build_url(vid='muledit', rql=bookmarksrql)
                    menu.append(self.link(req._('edit bookmarks'), url))
            url = req.user.absolute_url(vid='xaddrelation', rtype='bookmarked_by',
                                        target='subject')
            menu.append(self.link(req._('pick existing bookmarks'), url))
            self.append(menu)
        self.render_items(w)

@ajaxfunc
def delete_bookmark(self, beid):
    rql = 'DELETE B bookmarked_by U WHERE B eid %(b)s, U eid %(u)s'
    self._cw.execute(rql, {'b': int(beid), 'u' : self._cw.user.eid})
