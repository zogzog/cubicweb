"""Set of tree-building widgets, based on jQuery treeview plugin

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import monkeypatch
from logilab.mtconverter import html_escape

from cubicweb.utils import make_uid
from cubicweb.interfaces import ITree
from cubicweb.selectors import implements
from cubicweb.view import EntityView

def treecookiename(treeid):
    return str('treestate-%s' % treeid)

class TreeView(EntityView):
    id = 'treeview'
    itemvid = 'treeitemview'
    css_classes = 'treeview widget'
    title = _('tree view')

    def call(self, subvid=None, treeid=None, initial_load=True):
        if subvid is None:
            subvid = self.req.form.pop('treesubvid', 'oneline') # consume it
        if treeid is None:
            treeid = self.req.form.pop('treeid', None)
            if treeid is None:
                self.warning('Tree state won\'t be properly restored after next reload')
                treeid = make_uid('throw away uid')
        self.w(u'<ul id="tree-%s" class="%s">' % (treeid, self.css_classes))
        for rowidx in xrange(len(self.rset)):
            self.wview(self.itemvid, self.rset, row=rowidx, col=0,
                       vid=subvid, parentvid=self.id, treeid=treeid)
        self.w(u'</ul>')
        if initial_load and not self.req.form.get('fname'):
            self.req.add_css('jquery.treeview.css')
            self.req.add_js(('cubicweb.ajax.js', 'jquery.treeview.js'))
            self.req.html_headers.add_onload(u"""
jQuery("#tree-%s").treeview({toggle: toggleTree, prerendered: true});""" % treeid)


class FileTreeView(TreeView):
    """specific version of the treeview to display file trees
    """
    id = 'filetree'
    css_classes = 'treeview widget filetree'
    title = _('file tree view')

    def call(self, subvid=None, treeid=None, initial_load=True):
        super(FileTreeView, self).call(treeid=treeid, subvid='filetree-oneline', initial_load=initial_load)

class FileItemInnerView(EntityView):
    """inner view used by the TreeItemView instead of oneline view

    This view adds an enclosing <span> with some specific CSS classes
    around the oneline view. This is needed by the jquery treeview plugin.
    """
    id = 'filetree-oneline'

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        if ITree.is_implemented_by(entity.__class__) and not entity.is_leaf():
            self.w(u'<div class="folder">%s</div>\n' % entity.view('oneline'))
        else:
            # XXX define specific CSS classes according to mime types
            self.w(u'<div class="file">%s</div>\n' % entity.view('oneline'))


class DefaultTreeViewItemView(EntityView):
    """default treeitem view for entities which don't implement ITree"""
    id = 'treeitemview'

    def cell_call(self, row, col, vid='oneline', parentvid='treeview', treeid=None):
        assert treeid is not None
        entity = self.entity(row, col)
        itemview = self.view(vid, self.rset, row=row, col=col)
        if row == len(self.rset) - 1:
            self.w(u'<li class="last">%s</li>' % itemview)
        else:
            self.w(u'<li>%s</li>' % itemview)


class TreeViewItemView(EntityView):
    """specific treeitem view for entities which implement ITree

    (each item should be expandable if it's not a tree leaf)
    """
    id = 'treeitemview'
    __select__ = EntityView.__select__ & implements(ITree) # XXX

    def open_state(self, eeid, treeid):
        cookies = self.req.get_cookie()
        treestate = cookies.get(treecookiename(treeid))
        if treestate:
            return str(eeid) in treestate.value.split(';')
        return False

    def cell_call(self, row, col, treeid, vid='oneline', parentvid='treeview'):
        w = self.w
        entity = self.entity(row, col)
        liclasses = []
        is_last = row == len(self.rset) - 1
        is_open = self.open_state(entity.eid, treeid)
        is_leaf = not hasattr(entity, 'is_leaf') or entity.is_leaf()
        if is_leaf:
            if is_last:
                liclasses.append('last')
            w(u'<li class="%s">' % u' '.join(liclasses))
        else:
            rql = entity.children_rql() % {'x': entity.eid}
            url = html_escape(self.build_url('json', rql=rql, vid=parentvid,
                                             pageid=self.req.pageid,
                                             treeid=treeid,
                                             fname='view',
                                             treesubvid=vid))
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
            divtail = """ onclick="asyncRemoteExec('node_clicked', '%s', '%s')" """ %\
                (treeid, entity.eid)
            w(u'<div class="%s"%s></div>' % (u' '.join(divclasses), divtail))

            # add empty <ul> because jquery's treeview plugin checks for
            # sublists presence
            if not is_open:
                w(u'<ul class="placeholder"><li>place holder</li></ul>')
        # the local node info
        self.wview(vid, self.rset, row=row, col=col)
        if is_open and not is_leaf: #  => rql is defined
            self.wview(parentvid, self.req.execute(rql), treeid=treeid, initial_load=False)
        w(u'</li>')

