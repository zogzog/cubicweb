# copyright 2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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


from cubicweb import _


from logilab.common.registry import Predicate

from cubicweb import UnknownEid, tags, transaction as tx
from cubicweb.view import View, StartupView
from cubicweb.predicates import match_kwargs, ExpectedValuePredicate
from cubicweb.schema import display_name


class undoable_action(Predicate):
    """Select only undoable actions depending on filters provided. Undo Action
    is expected to be specified by the `tx_action` argument.

    Currently the only implemented filter is:

    :param action_type: chars among CUDAR (standing for Create, Update, Delete,
                        Add, Remove)
    """

    # XXX FIXME : this selector should be completed to allow selection on the
    # entity or relation types and public / private.
    def __init__(self, action_type='CUDAR'):
        assert not set(action_type) - set('CUDAR')
        self.action_type = action_type

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, ', '.join(
            "%s=%v" % (str(k), str(v)) for k, v in kwargs.items() ))

    def __call__(self, cls, req, tx_action=None, **kwargs):
        # tx_action is expected to be a transaction.AbstractAction
        if not isinstance(tx_action, tx.AbstractAction):
            return 0
        # Filter according to action type
        return int(tx_action.action in self.action_type)


class UndoHistoryView(StartupView):
    __regid__ = 'undohistory'
    title = _('Undoing')
    item_vid = 'undoable-transaction-view'
    cache_max_age = 0

    redirect_path = 'view' #TODO
    redirect_params = dict(vid='undohistory') #TODO
    public_actions_only = True

    # TODO Allow to choose if if want all actions or only the public ones
    # (default)

    def call(self, **kwargs):
        txs = self._cw.cnx.undoable_transactions()
        if txs :
            self.w(u"<ul class='undo-transactions'>")
            for tx in txs:
                self.cell_call(tx)
            self.w(u"</ul>")

    def cell_call(self, tx):
        self.w(u'<li>')
        self.wview(self.item_vid, None, txuuid=tx.uuid,
                   public=self.public_actions_only,
                   redirect_path=self.redirect_path,
                   redirect_params=self.redirect_params)
        self.w(u'</li>\n')


class UndoableTransactionView(View):
    __regid__ = 'undoable-transaction-view'
    __select__ = View.__select__ & match_kwargs('txuuid')

    item_vid = 'undoable-action-list-view'
    cache_max_age = 0

    def build_undo_link(self, txuuid,
                        redirect_path=None, redirect_params=None):
        """ the kwargs are passed to build_url"""
        _ = self._cw._
        redirect = {}
        if redirect_path:
            redirect['__redirectpath'] = redirect_path
        if redirect_params:
            if isinstance(redirect_params, dict):
                redirect['__redirectparams'] = self._cw.build_url_params(**redirect_params)
            else:
                redirect['__redirectparams'] = redirect_params
        link_url = self._cw.build_url('undo', txuuid=txuuid, **redirect)
        msg = u"<span class='undo'>%s</span>" % tags.a( _('undo'), href=link_url)
        return msg

    def call(self, txuuid, public=True,
             redirect_path=None, redirect_params=None):
        _ = self._cw._
        txinfo = self._cw.cnx.transaction_info(txuuid)
        try:
            #XXX Under some unknown circumstances txinfo.user_eid=-1
            user = self._cw.entity_from_eid(txinfo.user_eid)
        except UnknownEid:
            user = None
        undo_url = self.build_undo_link(txuuid,
                                        redirect_path=redirect_path,
                                        redirect_params=redirect_params)
        txinfo_dict = dict( dt = self._cw.format_date(txinfo.datetime, time=True),
                            user_eid = txinfo.user_eid,
                            user = user and user.view('outofcontext') or _("undefined user"),
                            txuuid = txuuid,
                            undo_link = undo_url)
        self.w( _("By %(user)s on %(dt)s [%(undo_link)s]") % txinfo_dict)

        tx_actions = txinfo.actions_list(public=public)
        if tx_actions :
            self.wview(self.item_vid, None, tx_actions=tx_actions)


class UndoableActionListView(View):
    __regid__ = 'undoable-action-list-view'
    __select__ = View.__select__ & match_kwargs('tx_actions')
    title = _('Undoable actions')
    item_vid = 'undoable-action-view'
    cache_max_age = 0

    def call(self, tx_actions):
        if tx_actions :
            self.w(u"<ol class='undo-actions'>")
            for action in tx_actions:
                self.cell_call(action)
            self.w(u"</ol>")

    def cell_call(self, action):
        self.w(u'<li>')
        self.wview(self.item_vid, None, tx_action=action)
        self.w(u'</li>\n')


class UndoableActionBaseView(View):
    __regid__ = 'undoable-action-view'
    __abstract__ = True

    def call(self, tx_action):
        raise NotImplementedError(self)

    def _build_entity_link(self, eid):
        try:
            entity = self._cw.entity_from_eid(eid)
            return entity.view('outofcontext')
        except UnknownEid:
            return _("(suppressed) entity #%d") % eid

    def _build_relation_info(self, rtype, eid_from,  eid_to):
        return dict( rtype=display_name(self._cw, rtype),
                     entity_from=self._build_entity_link(eid_from),
                     entity_to=self._build_entity_link(eid_to) )

    def _build_entity_info(self, etype, eid, changes):
        return dict( etype=display_name(self._cw, etype),
                     entity=self._build_entity_link(eid),
                     eid=eid,
                     changes=changes)


class UndoableAddActionView(UndoableActionBaseView):
    __select__ = UndoableActionBaseView.__select__ & undoable_action(action_type='A')

    def call(self, tx_action):
        _ = self._cw._
        self.w(_("Added relation : %(entity_from)s %(rtype)s %(entity_to)s") %
               self._build_relation_info(tx_action.rtype, tx_action.eid_from, tx_action.eid_to))


class UndoableRemoveActionView(UndoableActionBaseView):
    __select__ = UndoableActionBaseView.__select__ & undoable_action(action_type='R')

    def call(self, tx_action):
        _ = self._cw._
        self.w(_("Delete relation : %(entity_from)s %(rtype)s %(entity_to)s") %
               self._build_relation_info(tx_action.rtype, tx_action.eid_from, tx_action.eid_to))


class UndoableCreateActionView(UndoableActionBaseView):
    __select__ = UndoableActionBaseView.__select__ & undoable_action(action_type='C')

    def call(self, tx_action):
        _ = self._cw._
        self.w(_("Created %(etype)s : %(entity)s") % #  : %(changes)s
               self._build_entity_info( tx_action.etype, tx_action.eid, tx_action.changes) )


class UndoableDeleteActionView(UndoableActionBaseView):
    __select__ = UndoableActionBaseView.__select__ & undoable_action(action_type='D')

    def call(self, tx_action):
        _ = self._cw._
        self.w(_("Deleted %(etype)s : %(entity)s") %
               self._build_entity_info( tx_action.etype, tx_action.eid, tx_action.changes))


class UndoableUpdateActionView(UndoableActionBaseView):
    __select__ = UndoableActionBaseView.__select__ & undoable_action(action_type='U')

    def call(self, tx_action):
        _ = self._cw._
        self.w(_("Updated %(etype)s : %(entity)s") %
               self._build_entity_info( tx_action.etype, tx_action.eid, tx_action.changes))
