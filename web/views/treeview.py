from logilab.mtconverter import html_escape

from cubicweb.interfaces import ITree
from cubicweb.common.selectors import interface_selector, yes_selector
from cubicweb.common.view import EntityView

class TreeView(EntityView):
    id = 'treeview'
    accepts = ('Any',)
    
    def call(self, subvid=None):
        if subvid is None and 'subvid' in self.req.form:
            subvid = self.req.form.pop('subvid') # consume it
        if subvid is None:
            subvid = 'oneline'
        self.req.add_css('jquery.treeview.css')
        self.req.add_js(('cubicweb.ajax.js', 'jquery.treeview.js', 'cubicweb.widgets.js'))
        self.w(u'<ul class="treeview widget" cubicweb:loadtype="auto" cubicweb:wdgtype="TreeView">')
        for rowidx in xrange(len(self.rset)):
            self.wview('treeitemview', self.rset, row=rowidx, col=0, vid=subvid)
        self.w(u'</ul>')


class DefaultTreeViewItemView(EntityView):
    """default treeitem view for entities which don't implement ITree
    """
    id = 'treeitemview'
    accepts = ('Any',)
    
    def cell_call(self, row, col, vid='oneline'):
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
    # XXX append yes_selector to make sure we get an higher score than
    #     the default treeitem view
    __selectors__ = (interface_selector, yes_selector)
    accepts_interfaces = (ITree,)
    
    def cell_call(self, row, col, vid='oneline'):
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
            url = html_escape(self.build_url('json', rql=rql, vid='treeview',
                                             pageid=self.req.pageid,
                                             subvid=vid))
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

