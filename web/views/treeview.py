"""Set of tree-building widgets, based on jQuery treeview plugin

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import simplejson as json

from logilab.common.decorators import monkeypatch
from logilab.mtconverter import xml_escape
from cubicweb.utils import make_uid
from cubicweb.interfaces import ITree
from cubicweb.selectors import implements
from cubicweb.view import EntityView

def treecookiename(treeid):
    return str('%s-treestate' % treeid)

class TreeView(EntityView):
    __regid__ = 'treeview'
    itemvid = 'treeitemview'
    subvid = 'oneline'
    css_classes = 'treeview widget'
    title = _('tree view')

    def _init_params(self, subvid, treeid, initial_load, initial_thru_ajax, morekwargs):
        form = self._cw.form
        if subvid is None:
            subvid = form.pop('treesubvid', self.subvid) # consume it
        if treeid is None:
            treeid = form.pop('treeid', None)
            if treeid is None:
                treeid = 'throw_away' + make_uid('uid')
        if 'morekwargs' in self._cw.form:
            ajaxargs = json.loads(form.pop('morekwargs'))
            # got unicode & python keywords must be strings
            morekwargs.update(dict((str(k), v)
                                   for k, v in ajaxargs.iteritems()))
        toplevel_thru_ajax = form.pop('treeview_top', False) or initial_thru_ajax
        toplevel = toplevel_thru_ajax or (initial_load and not form.get('fname'))
        return subvid, treeid, toplevel_thru_ajax, toplevel

    def _init_headers(self, treeid, toplevel_thru_ajax):
        self._cw.add_css('jquery.treeview.css')
        self._cw.add_js(('cubicweb.ajax.js', 'cubicweb.widgets.js', 'jquery.treeview.js'))
        self._cw.html_headers.add_onload(u"""
jQuery("#tree-%s").treeview({toggle: toggleTree, prerendered: true});""" % treeid,
                                         jsoncall=toplevel_thru_ajax)

    def call(self, subvid=None, treeid=None,
             initial_load=True, initial_thru_ajax=False, **morekwargs):
        subvid, treeid, toplevel_thru_ajax, toplevel = self._init_params(
            subvid, treeid, initial_load, initial_thru_ajax, morekwargs)
        ulid = ' '
        if toplevel:
            self._init_headers(treeid, toplevel_thru_ajax)
            ulid = ' id="tree-%s"' % treeid
        self.w(u'<ul%s class="%s">' % (ulid, self.css_classes))
        for i, entity in enumerate(sorted(self.cw_rset.entities(),
                                          key=lambda x: x.dc_title())):
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
    css_classes = 'treeview widget filetree'
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
        if ITree.is_implemented_by(entity.__class__) and not entity.is_leaf():
            self.w(u'<div class="folder">%s</div>\n' % entity.view('oneline'))
        else:
            # XXX define specific CSS classes according to mime types
            self.w(u'<div class="file">%s</div>\n' % entity.view('oneline'))


class DefaultTreeViewItemView(EntityView):
    """default treeitem view for entities which don't implement ITree"""
    __regid__ = 'treeitemview'

    def cell_call(self, row, col, vid='oneline', treeid=None, **morekwargs):
        assert treeid is not None
        entity = self.cw_rset.get_entity(row, col)
        itemview = self._cw.view(vid, self.cw_rset, row=row, col=col)
        if row == len(self.cw_rset) - 1:
            self.w(u'<li class="last">%s</li>' % itemview)
        else:
            self.w(u'<li>%s</li>' % itemview)


class TreeViewItemView(EntityView):
    """specific treeitem view for entities which implement ITree

    (each item should be expandable if it's not a tree leaf)
    """
    __regid__ = 'treeitemview'
    __select__ = implements(ITree)
    default_branch_state_is_open = False

    def open_state(self, eeid, treeid):
        cookies = self._cw.get_cookie()
        treestate = cookies.get(treecookiename(treeid))
        if treestate:
            return str(eeid) in treestate.value.split(';')
        return self.default_branch_state_is_open

    def cell_call(self, row, col, treeid, vid='oneline', parentvid='treeview',
                  is_last=False, **morekwargs):
        w = self.w
        entity = self.cw_rset.get_entity(row, col)
        liclasses = []
        is_open = self.open_state(entity.eid, treeid)
        is_leaf = not hasattr(entity, 'is_leaf') or entity.is_leaf()
        if is_leaf:
            if is_last:
                liclasses.append('last')
            w(u'<li class="%s">' % u' '.join(liclasses))
        else:
            rql = entity.children_rql() % {'x': entity.eid}
            url = xml_escape(self._cw.build_url('json', rql=rql, vid=parentvid,
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
                divtail = """ onclick="asyncRemoteExec('node_clicked', '%s', '%s')" """ %\
                    (treeid, entity.eid)
            w(u'<div class="%s"%s></div>' % (u' '.join(divclasses), divtail))

            # add empty <ul> because jquery's treeview plugin checks for
            # sublists presence
            if not is_open:
                w(u'<ul class="placeholder"><li>place holder</li></ul>')
        # the local node info
        self.wview(vid, self.cw_rset, row=row, col=col, **morekwargs)
        if is_open and not is_leaf: #  => rql is defined
            self.wview(parentvid, entity.children(entities=False), subvid=vid,
                       treeid=treeid, initial_load=False, **morekwargs)
        w(u'</li>')

