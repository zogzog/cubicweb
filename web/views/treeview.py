from logilab.mtconverter import html_escape

from cubicweb.interfaces import ITree
from cubicweb.selectors import implements
from cubicweb.common.view import EntityView

class TreeView(EntityView):
    id = 'treeview'
    itemvid = 'treeitemview'
    css_classes = 'treeview widget'
    title = _('tree view')
    
    def call(self, subvid=None):
        if subvid is None and 'subvid' in self.req.form:
            subvid = self.req.form.pop('subvid') # consume it
        if subvid is None:
            subvid = 'oneline'
        self.req.add_css('jquery.treeview.css')
        self.req.add_js(('cubicweb.ajax.js', 'jquery.treeview.js', 'cubicweb.widgets.js'))
        # XXX noautoload is a quick hack to avoid treeview to be rebuilt
        #     after a json query and avoid double toggling bugs.
        #     Need to find a way to do that cleanly.
        if 'noautoload' in self.req.form:
            self.w(u'<ul class="%s" cubicweb:wdgtype="TreeView">' % self.css_classes)
        else:
            self.w(u'<ul class="%s" cubicweb:loadtype="auto" cubicweb:wdgtype="TreeView">'
                   % self.css_classes)
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
            self.w(u'<div class="folder">%s</div>' % entity.view('oneline'))
        else:
            # XXX define specific CSS classes according to mime types
            self.w(u'<div class="file">%s</div>' % entity.view('oneline'))


class DefaultTreeViewItemView(EntityView):
    """default treeitem view for entities which don't implement ITree
    """
    id = 'treeitemview'
    
    def cell_call(self, row, col, vid='oneline', parentvid='treeview'):
        entity = self.entity(row, col)
        itemview = self.view(vid, self.rset, row=row, col=col)
        if row == len(self.rset) - 1:
            self.w(u'<li class="last">%s</li>' % itemview)
        else:
            self.w(u'<li>%s</li>' % itemview)


class TreeViewItemView(EntityView):
    """specific treeitem view for entities which implement ITree
    
    (each item should be exandable if it's not a tree leaf)
    """
    id = 'treeitemview'
    __selectors__ = implements(ITree)
    
    def cell_call(self, row, col, vid='oneline', parentvid='treeview'):
        entity = self.entity(row, col)
        cssclasses = []
        is_leaf = False
        if row == len(self.rset) - 1:
            is_leaf = True
        if not hasattr(entity, 'is_leaf') or entity.is_leaf():
            if is_leaf : cssclasses.append('last')
            self.w(u'<li class="%s">' % u' '.join(cssclasses))
        else:
            rql = entity.children_rql() % {'x': entity.eid}
            url = html_escape(self.build_url('json', rql=rql, vid=parentvid,
                                             pageid=self.req.pageid,
                                             subvid=vid,
                                             noautoload=True))
            cssclasses.append('expandable')
            divclasses = ['hitarea expandable-hitarea']
            if is_leaf :
                cssclasses.append('lastExpandable')
                divclasses.append('lastExpandable-hitarea')
            self.w(u'<li cubicweb:loadurl="%s" class="%s">' % (url, u' '.join(cssclasses)))
            self.w(u'<div class="%s"> </div>' % u' '.join(divclasses))
                
            # add empty <ul> because jquery's treeview plugin checks for
            # sublists presence
            self.w(u'<ul class="placeholder"><li>place holder</li></ul>')
        self.wview(vid, self.rset, row=row, col=col)
        self.w(u'</li>')

