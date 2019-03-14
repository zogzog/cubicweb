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
"""Set of tree views / tree-building widgets, some based on jQuery treeview
plugin.
"""


from cubicweb import _

from logilab.mtconverter import xml_escape

from cubicweb.utils import make_uid, json
from cubicweb.predicates import adaptable
from cubicweb.view import EntityView
from cubicweb.web.views import baseviews
from cubicweb.web.views.ajaxcontroller import ajaxfunc

def treecookiename(treeid):
    return str('%s-treestate' % treeid)

def _done_init(done, view, row, col):
    """handle an infinite recursion safety belt"""
    if done is None:
        done = set()
    entity = view.cw_rset.get_entity(row, col)
    if entity.eid in done:
        msg = entity._cw._('loop in %(rel)s relation (%(eid)s)') % {
            'rel': entity.cw_adapt_to('ITree').tree_relation,
            'eid': entity.eid
            }
        return None, msg
    done.add(entity.eid)
    return done, entity


class BaseTreeView(baseviews.ListView):
    """base tree view"""
    __regid__ = 'tree'
    __select__ = adaptable('ITree')
    item_vid = 'treeitem'

    def call(self, done=None, **kwargs):
        if done is None:
            done = set()
        super(BaseTreeView, self).call(done=done, **kwargs)

    def cell_call(self, row, col=0, vid=None, done=None, maxlevel=None, klass=None, **kwargs):
        assert maxlevel is None or maxlevel > 0
        done, entity = _done_init(done, self, row, col)
        if done is None:
            # entity is actually an error message
            self.w(u'<li class="badcontent">%s</li>' % entity)
            return
        self.open_item(entity)
        entity.view(vid or self.item_vid, w=self.w, **kwargs)
        if maxlevel is not None:
            maxlevel -= 1
            if maxlevel == 0:
                self.close_item(entity)
                return
        relatedrset = entity.cw_adapt_to('ITree').children(entities=False)
        self.wview(self.__regid__, relatedrset, 'null', done=done,
                   maxlevel=maxlevel, klass=klass, **kwargs)
        self.close_item(entity)

    def open_item(self, entity):
        self.w(u'<li class="%s">\n' % entity.cw_etype.lower())
    def close_item(self, entity):
        self.w(u'</li>\n')


class TreePathView(EntityView):
    """a recursive path view"""
    __regid__ = 'path'
    __select__ = adaptable('ITree')
    item_vid = 'oneline'
    separator = u'&#160;&gt;&#160;'

    def call(self, **kwargs):
        self.w(u'<div class="pathbar">')
        super(TreePathView, self).call(**kwargs)
        self.w(u'</div>')

    def cell_call(self, row, col=0, vid=None, done=None, **kwargs):
        done, entity = _done_init(done, self, row, col)
        if done is None:
            # entity is actually an error message
            self.w(u'<span class="badcontent">%s</span>' % entity)
            return
        parent = entity.cw_adapt_to('ITree').parent()
        if parent:
            parent.view(self.__regid__, w=self.w, done=done)
            self.w(self.separator)
        entity.view(vid or self.item_vid, w=self.w)


class TreeComboBoxView(TreePathView):
    """display folder in edition's combobox"""
    __regid__ = 'combobox'
    item_vid = 'text'
    separator = u' > '

# XXX rename regid to ajaxtree/foldabletree or something like that (same for
# treeitemview)
class TreeView(EntityView):
    """ajax tree view, click to expand folder"""

    __regid__ = 'treeview'
    itemvid = 'treeitemview'
    subvid = 'oneline'
    cssclass = 'treeview widget'
    title = _('tree view')

    def _init_params(self, subvid, treeid, initial_load, morekwargs):
        form = self._cw.form
        if subvid is None:
            subvid = form.pop('treesubvid', self.subvid)  # consume it
        if treeid is None:
            treeid = form.pop('treeid', None)
            if treeid is None:
                treeid = 'throw_away' + make_uid('uid')
        if 'morekwargs' in self._cw.form:
            ajaxargs = json.loads(form.pop('morekwargs'))
            # got unicode & python keywords must be strings
            morekwargs.update(dict((str(k), v)
                                   for k, v in ajaxargs.items()))
        return subvid, treeid

    def _init_headers(self, treeid):
        self._cw.add_css(('jquery-treeview/jquery.treeview.css', 'cubicweb.treeview.css'))
        self._cw.add_js(('cubicweb.ajax.js', 'cubicweb.widgets.js', 'jquery-treeview/jquery.treeview.js'))
        self._cw.html_headers.add_onload(u"""
jQuery("#tree-%s").treeview({toggle: toggleTree, prerendered: true});""" % treeid)

    def call(self, subvid=None, treeid=None,
             initial_load=True, **morekwargs):
        subvid, treeid = self._init_params(subvid, treeid,
                                           initial_load, morekwargs)
        ulid = ' '
        self._init_headers(treeid)
        ulid = ' id="tree-%s"' % treeid
        self.w(u'<ul%s class="%s">' % (ulid, self.cssclass))
        # XXX force sorting on x.sortvalue() (which return dc_title by default)
        # we need proper ITree & co specification to avoid this.
        # (pb when type ambiguity at the other side of the tree relation,
        # unability to provide generic implementation on eg Folder...)
        for i, entity in enumerate(sorted(self.cw_rset.entities(),
                                          key=lambda x: x.sortvalue())):
            if i+1 < len(self.cw_rset):
                morekwargs['is_last'] = False
            else:
                morekwargs['is_last'] = True
            entity.view(self.itemvid, vid=subvid, parentvid=self.__regid__,
                        treeid=treeid, w=self.w, **morekwargs)
        self.w(u'</ul>')

    def cell_call(self, *args, **allargs):
        """ does not makes much sense until you have to invoke
        somentity.view('treeview') """
        allargs.pop('row')
        allargs.pop('col')
        self.call(*args, **allargs)


class FileTreeView(TreeView):
    """specific version of the treeview to display file trees
    """
    __regid__ = 'filetree'
    cssclass = 'treeview widget filetree'
    title = _('file tree view')

    def call(self, subvid=None, treeid=None, initial_load=True, **kwargs):
        super(FileTreeView, self).call(treeid=treeid, subvid='filetree-oneline',
                                       initial_load=initial_load, **kwargs)

class FileItemInnerView(EntityView):
    """inner view used by the TreeItemView instead of oneline view

    This view adds an enclosing <span> with some specific CSS classes
    around the oneline view. This is needed by the jquery treeview plugin.
    """
    __regid__ = 'filetree-oneline'

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        itree = entity.cw_adapt_to('ITree')
        if itree and not itree.is_leaf():
            self.w(u'<div class="folder">%s</div>\n' % entity.view('oneline'))
        else:
            # XXX define specific CSS classes according to mime types
            self.w(u'<div class="file">%s</div>\n' % entity.view('oneline'))


class DefaultTreeViewItemView(EntityView):
    """default treeitem view for entities which don't adapt to ITree"""
    __regid__ = 'treeitemview'

    def cell_call(self, row, col, vid='oneline', treeid=None, **morekwargs):
        assert treeid is not None
        itemview = self._cw.view(vid, self.cw_rset, row=row, col=col)
        last_class = morekwargs['is_last'] and ' class="last"' or ''
        self.w(u'<li%s>%s</li>' % (last_class, itemview))


class TreeViewItemView(EntityView):
    """specific treeitem view for entities which adapt to ITree

    (each item should be expandable if it's not a tree leaf)
    """
    __regid__ = 'treeitemview'
    __select__ = adaptable('ITree')
    default_branch_state_is_open = False

    def open_state(self, eeid, treeid):
        cookies = self._cw.get_cookie()
        treestate = cookies.get(treecookiename(treeid))
        if treestate:
            return str(eeid) in treestate.value.split(':')
        return self.default_branch_state_is_open

    def cell_call(self, row, col, treeid, vid='oneline', parentvid='treeview',
                  is_last=False, **morekwargs):
        w = self.w
        entity = self.cw_rset.get_entity(row, col)
        itree = entity.cw_adapt_to('ITree')
        liclasses = []
        if self._cw.url(includeparams=False) == entity.absolute_url():
            liclasses.append(u'selected')
        is_open = self.open_state(entity.eid, treeid)
        is_leaf = itree is None or itree.is_leaf()
        if is_leaf:
            if is_last:
                liclasses.append('last')
            w(u'<li class="%s">' % u' '.join(liclasses))
        else:
            rql = itree.children_rql() % {'x': entity.eid}
            url = xml_escape(self._cw.build_url('ajax', rql=rql, vid=parentvid,
                                                pageid=self._cw.pageid,
                                                treeid=treeid,
                                                fname='view',
                                                treesubvid=vid,
                                                morekwargs=json.dumps(morekwargs)))
            divclasses = ['hitarea']
            if is_open:
                liclasses.append('collapsable')
                divclasses.append('collapsable-hitarea')
            else:
                liclasses.append('expandable')
                divclasses.append('expandable-hitarea')
            if is_last:
                if is_open:
                    liclasses.append('lastCollapsable')
                    divclasses.append('lastCollapsable-hitarea')
                else:
                    liclasses.append('lastExpandable')
                    divclasses.append('lastExpandable-hitarea')
            if is_open:
                w(u'<li class="%s">' % u' '.join(liclasses))
            else:
                w(u'<li cubicweb:loadurl="%s" class="%s">' % (url, u' '.join(liclasses)))
            if treeid.startswith('throw_away'):
                divtail = ''
            else:
                divtail = """ onclick="asyncRemoteExec('node_clicked', '%s', '%s')" """ % (
                    treeid, entity.eid)
            w(u'<div class="%s"%s></div>' % (u' '.join(divclasses), divtail))

            # add empty <ul> because jquery's treeview plugin checks for
            # sublists presence
            if not is_open:
                w(u'<ul class="placeholder"><li>place holder</li></ul>')
        # the local node info
        self.wview(vid, self.cw_rset, row=row, col=col, **morekwargs)
        if is_open and not is_leaf: #  => rql is defined
            self.wview(parentvid, itree.children(entities=False), subvid=vid,
                       treeid=treeid, initial_load=False, **morekwargs)
        w(u'</li>')



@ajaxfunc
def node_clicked(self, treeid, nodeeid):
    """add/remove eid in treestate cookie"""
    cookies = self._cw.get_cookie()
    statename = treecookiename(treeid)
    treestate = cookies.get(statename)
    if treestate is None:
        self._cw.set_cookie(statename, nodeeid)
    else:
        marked = set(filter(None, treestate.value.split(':')))
        if nodeeid in marked:
            marked.remove(nodeeid)
        else:
            marked.add(nodeeid)
        self._cw.set_cookie(statename, ':'.join(marked))
