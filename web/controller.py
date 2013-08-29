# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""abstract controller classe for CubicWeb web client"""

__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape
from logilab.common.registry import yes
from logilab.common.deprecation import deprecated

from cubicweb.appobject import AppObject
from cubicweb.mail import format_mail
from cubicweb.web import LOGGER, Redirect, RequestError


NAVIGATION_PARAMETERS = (('vid', '__redirectvid'),
                         ('rql', '__redirectrql'),
                         ('__redirectpath', '__redirectpath'),
                         ('__redirectparams', '__redirectparams'),
                         )
NAV_FORM_PARAMETERS = tuple(fp for ap, fp in NAVIGATION_PARAMETERS)

def redirect_params(form):
    """transform redirection parameters into navigation parameters
    """
    params = {}
    # extract navigation parameters from redirection parameters
    for navparam, redirectparam in NAVIGATION_PARAMETERS:
        if navparam == redirectparam:
            continue
        if redirectparam in form:
            params[navparam] = form[redirectparam]
    return params

def append_url_params(url, params):
    """append raw parameters to the url. Given parameters, if any, are expected
    to be already url-quoted.
    """
    if params:
        if not '?' in url:
            url += '?'
        else:
            url += '&'
        url += params
    return url


class Controller(AppObject):
    """a controller is responsible to make necessary stuff to publish
    a request. There is usually at least one standard "view" controller
    and another linked by forms to edit objects ("edit").
    """
    __registry__ = 'controllers'
    __select__ = yes()

    def __init__(self, *args, **kwargs):
        self.appli = kwargs.pop('appli', None)
        super(Controller, self).__init__(*args, **kwargs)
        # attributes use to control after edition redirection
        self._after_deletion_path = None
        self._edited_entity = None

    def publish(self, rset=None):
        """publish the current request, with an optional input rset"""
        raise NotImplementedError

    # generic methods useful for concrete implementations ######################

    def process_rql(self):
        """execute rql if specified"""
        req = self._cw
        rql = req.form.get('rql')
        if rql:
            req.ensure_ro_rql(rql)
            if not isinstance(rql, unicode):
                rql = unicode(rql, req.encoding)
            pp = req.vreg['components'].select_or_none('magicsearch', req)
            if pp is not None:
                return pp.process_query(rql)
        if 'eid' in req.form and not isinstance(req.form['eid'], list):
            return req.eid_rset(req.form['eid'])
        return None

    def notify_edited(self, entity):
        """called by edit_entity() to notify which entity is edited"""
        # NOTE: we can't use entity.rest_path() at this point because
        #       rest_path() could rely on schema constraints (such as a required
        #       relation) that might not be satisfied yet (in case of creations)
        if not self._edited_entity:
            self._edited_entity = entity

    @deprecated('[3.18] call view.set_http_cache_headers then '
                '.is_client_cache_valid() method and return instead')
    def validate_cache(self, view):
        view.set_http_cache_headers()
        self._cw.validate_cache()

    def sendmail(self, recipient, subject, body):
        senderemail = self._cw.user.cw_adapt_to('IEmailable').get_email()
        msg = format_mail({'email' : senderemail,
                           'name' : self._cw.user.dc_title(),},
                          [recipient], body, subject)
        if not self._cw.vreg.config.sendmails([(msg, [recipient])]):
            msg = self._cw._('could not connect to the SMTP server')
            url = self._cw.build_url(__message=msg)
            raise Redirect(url)

    def reset(self):
        """reset form parameters and redirect to a view determinated by given
        parameters
        """
        newparams = {}
        # sets message if needed
        # XXX - don't call .message twice since it pops the id
        msg = self._cw.message
        if msg:
            newparams['_cwmsgid'] = self._cw.set_redirect_message(msg)
        if '__action_apply' in self._cw.form:
            self._return_to_edition_view(newparams)
        if '__action_cancel' in self._cw.form:
            self._return_to_lastpage(newparams)
        else:
            self._return_to_original_view(newparams)

    def _return_to_original_view(self, newparams):
        """validate-button case"""
        # transforms __redirect[*] parameters into regular form parameters
        newparams.update(redirect_params(self._cw.form))
        # find out if we have some explicit `rql` needs
        rql = newparams.pop('rql', None)
        # if rql is needed (explicit __redirectrql or multiple deletions for
        # instance), we have to use the old `view?rql=...` form
        if rql:
            path = 'view'
            newparams['rql'] = rql
        elif '__redirectpath' in self._cw.form:
            # if redirect path was explicitly specified in the form, use it
            path = self._cw.form['__redirectpath']
            if (self._edited_entity and path != self._edited_entity.rest_path()
                and '_cwmsgid' in newparams):
                # are we here on creation or modification?
                if any(eid == self._edited_entity.eid
                       for eid in self._cw.data.get('eidmap', {}).itervalues()):
                    msg = self._cw._('click here to see created entity')
                else:
                    msg = self._cw._('click here to see edited entity')
                msg = u'(<a href="%s">%s</a>)' % (xml_escape(self._edited_entity.absolute_url()), msg)
                self._cw.append_to_redirect_message(msg)
        elif self._after_deletion_path:
            # else it should have been set during form processing
            path, params = self._after_deletion_path
            params = dict(params) # params given as tuple
            params.update(newparams)
            newparams = params
        elif self._edited_entity:
            # clear caches in case some attribute participating to the rest path
            # has been modified
            self._edited_entity.cw_clear_all_caches()
            path = self._edited_entity.rest_path()
        else:
            path = 'view'
        url = self._cw.build_url(path, **newparams)
        url = append_url_params(url, self._cw.form.get('__redirectparams'))
        raise Redirect(url)

    def _return_to_edition_view(self, newparams):
        """apply-button case"""
        form = self._cw.form
        if self._edited_entity:
            path = self._edited_entity.rest_path()
            newparams.pop('rql', None)
        # else, fallback on the old `view?rql=...` url form
        elif 'rql' in self._cw.form:
            path = 'view'
            newparams['rql'] = form['rql']
        else:
            self.warning('the edited data seems inconsistent')
            path = 'view'
        # pick up the correction edition view
        if form.get('__form_id'):
            newparams['vid'] = form['__form_id']
        # re-insert copy redirection parameters
        for redirectparam in NAV_FORM_PARAMETERS:
            if redirectparam in form:
                newparams[redirectparam] = form[redirectparam]
        raise Redirect(self._cw.build_url(path, **newparams))


    def _return_to_lastpage(self, newparams):
        """cancel-button case: in this case we are always expecting to go back
        where we came from, and this is not easy. Currently we suppose that
        __redirectpath is specifying that place if found, else we look in the
        request breadcrumbs for the last visited page.
        """
        if '__redirectpath' in self._cw.form:
            # if redirect path was explicitly specified in the form, use it
            path = self._cw.form['__redirectpath']
            url = self._cw.build_url(path)
            url = append_url_params(url, self._cw.form.get('__redirectparams'))
        else:
            url = self._cw.last_visited_page()
        # The newparams must update the params in all cases
        url = self._cw.rebuild_url(url, **newparams)
        raise Redirect(url)


from cubicweb import set_log_methods
set_log_methods(Controller, LOGGER)

