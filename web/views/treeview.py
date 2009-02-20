from logilab.mtconverter import html_escape
from cubicweb.interfaces import ITree
from cubicweb.common.selectors import implement_interface, yes
from cubicweb.common.view import EntityView

class TreeView(EntityView):
    id = 'treeview'
    accepts = ('Any',)
    itemvid = 'treeitemview'
    css_classes = 'treeview widget'
    title = _('tree view')

    def call(self, subvid=None, treeid=None):
        if subvid is None and 'subvid' in self.req.form:
            subvid = self.req.form.pop('subvid') # consume it
        if subvid is None:
            subvid = 'oneline'
        self.req.add_css('jquery.treeview.css')
        self.req.add_js(('cubicweb.ajax.js', 'jquery.treeview.js'))
        # XXX find a way, an id is MANDATORY
        treeid = 'TREE' #treeid or self.rset.rows[0][0]
        self.req.html_headers.add_onload(u"""
             $("#tree-%s").treeview({toggle: toggleTree,
		                     prerendered: true});""" % treeid)
        self.w(u'<ul id="tree-%s" class="%s">' % (treeid, self.css_classes))
        for rowidx in xrange(len(self.rset)):
            self.wview(self.itemvid, self.rset, row=rowidx, col=0,
                       vid=subvid, parentvid=self.id)
        self.w(u'</ul>')

class FileTreeView(TreeView):
    """specific version of the treeview to display file trees
    """
    id = 'filetree'
    css_classes = 'treeview widget filetree'
    title = _('file tree view')

    def call(self, subvid=None):
        super(FileTreeView, self).call(subvid='filetree-oneline')

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
    """default treeitem view for entities which don't implement ITree
    """
    id = 'treeitemview'
    accepts = ('Any',)

    def cell_call(self, row, col, vid='oneline', parentvid='treeview'):
        entity = self.entity(row, col)
        itemview = self.view(vid, self.rset, row=row, col=col)
        if row == len(self.rset) - 1:
            self.w(u'<li class="last">%s</li>' % itemview)
        else:
            self.w(u'<li>%s</li>' % itemview)


class TreeStateMixin(object):

    def open_state(self):
        raise NotImplementedError

class TreeViewItemView(EntityView, TreeStateMixin):
    """specific treeitem view for entities which implement ITree

    (each item should be exandable if it's not a tree leaf)
    """
    id = 'treeitemview'
    # XXX append yes to make sure we get an higher score than
    #     the default treeitem view
    __selectors__ = (implement_interface, yes)
    accepts_interfaces = (ITree,)

    def open_state(self):
        """implements TreeState mixin"""
        return ()

    def cell_call(self, row, col, vid='oneline', parentvid='treeview'):
        w = self.w
        entity = self.entity(row, col)
        liclasses = []
        is_leaf = False
        is_open = str(entity.eid) in self.open_state()
        if row == len(self.rset) - 1:
            is_leaf = True
        if not hasattr(entity, 'is_leaf') or entity.is_leaf():
            if is_leaf : liclasses.append('last')
            w(u'<li class="%s">' % u' '.join(liclasses))
        else:
            rql = entity.children_rql() % {'x': entity.eid}
            url = html_escape(self.build_url('json', rql=rql, vid=parentvid,
                                             pageid=self.req.pageid,
                                             subvid=vid,
                                             noautoload=True))
            if is_open:
                liclasses.append('collapsable')
            else:
                liclasses.append('expandable')
            divclasses = ['hitarea']
            if is_open:
                divclasses.append('collapsable-hitarea')
            else:
                divclasses.append('expandable-hitarea')
            if is_leaf:
                liclasses.append('lastExpandable')
                if not is_open:
                    divclasses.append('lastExpandable-hitarea')
            if is_open:
                w(u'<li class="%s">' % u' '.join(liclasses))
            else:
                w(u'<li cubicweb:loadurl="%s" class="%s">' % (url, u' '.join(liclasses)))
            if is_leaf:
                divtail = ''
            else:
                divtail = ''' onclick="async_remote_exec('node_clicked', %s)"''' % entity.eid
            w(u'<div class="%s"%s></div>' % (u' '.join(divclasses), divtail))

            # add empty <ul> because jquery's treeview plugin checks for
            # sublists presence
            if not is_open:
                w(u'<ul class="placeholder"><li>place holder</li></ul>')
        # the local node info
        self.wview(vid, self.rset, row=row, col=col)
        if is_open: # recurse if needed
            self.wview(parentvid, self.req.execute(rql))
        w(u'</li>')

from logilab.common.decorators import monkeypatch
from cubicweb.web.views.basecontrollers import JSonController

@monkeypatch(JSonController)
def js_node_clicked(self, eid):
    """add/remove eid in treestate cookie
    XXX this deals with one tree per page
        also check the treeid issue above
    """
    cookies = self.req.get_cookie()
    treestate = cookies.get('treestate')
    if treestate is None:
        cookies['treestate'] = str(eid)
        self.req.set_cookie(cookies, 'treestate')
    else:
        marked = set(treestate.value.split(';'))
        if eid in marked:
            marked.remove(eid)
        else:
            marked.add(eid)
        cookies['treestate'] = ';'.join(str(x) for x in marked)
        self.req.set_cookie(cookies, 'treestate')
