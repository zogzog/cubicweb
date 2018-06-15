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
#
# (disable pylint msg for client obj access to protected member as in obj._cw)
# pylint: disable=W0212
"""The ``ajaxcontroller`` module defines the :class:`AjaxController`
controller and the ``ajax-func`` cubicweb registry.

.. autoclass:: cubicweb.web.views.ajaxcontroller.AjaxController
   :members:

``ajax-funcs`` registry hosts exposed remote functions, that is
functions that can be called from the javascript world.

To register a new remote function, either decorate your function
with the :func:`~cubicweb.web.views.ajaxcontroller.ajaxfunc` decorator:

.. sourcecode:: python

    from cubicweb.predicates import mactch_user_groups
    from cubicweb.web.views.ajaxcontroller import ajaxfunc

    @ajaxfunc(output_type='json', selector=match_user_groups('managers'))
    def list_users(self):
        return [u for (u,) in self._cw.execute('Any L WHERE U login L')]

or inherit from :class:`~cubicweb.web.views.ajaxcontroller.AjaxFunction` and
implement the ``__call__`` method:

.. sourcecode:: python

    from cubicweb.web.views.ajaxcontroller import AjaxFunction
    class ListUser(AjaxFunction):
        __regid__ = 'list_users' # __regid__ is the name of the exposed function
        __select__ = match_user_groups('managers')
        output_type = 'json'

        def __call__(self):
            return [u for (u, ) in self._cw.execute('Any L WHERE U login L')]


.. autoclass:: cubicweb.web.views.ajaxcontroller.AjaxFunction
   :members:

.. autofunction:: cubicweb.web.views.ajaxcontroller.ajaxfunc

"""



from warnings import warn
from functools import partial

from six import PY2, text_type
from six.moves import http_client

from logilab.common.date import strptime
from logilab.common.registry import yes
from logilab.common.deprecation import deprecated

from cubicweb import ObjectNotFound, NoSelectableObject, ValidationError
from cubicweb.appobject import AppObject
from cubicweb.utils import json, json_dumps, UStringIO
from cubicweb.uilib import exc_message
from cubicweb.web import RemoteCallFailed, DirectResponse
from cubicweb.web.controller import Controller
from cubicweb.web.views import vid_from_rset
from cubicweb.web.views import basecontrollers


def optional_kwargs(extraargs):
    if extraargs is None:
        return {}
    # we receive unicode keys which is not supported by the **syntax
    return dict((str(key), value) for key, value in extraargs.items())


class AjaxController(Controller):
    """AjaxController handles ajax remote calls from javascript

    The following javascript function call:

    .. sourcecode:: javascript

      var d = asyncRemoteExec('foo', 12, "hello");
      d.addCallback(function(result) {
          alert('server response is: ' + result);
      });

    will generate an ajax HTTP GET on the following url::

        BASE_URL/ajax?fname=foo&arg=12&arg="hello"

    The AjaxController controller will therefore be selected to handle those URLs
    and will itself select the :class:`cubicweb.web.views.ajaxcontroller.AjaxFunction`
    matching the *fname* parameter.
    """
    __regid__ = 'ajax'

    def publish(self, rset=None):
        self._cw.ajax_request = True
        try:
            fname = self._cw.form['fname']
        except KeyError:
            raise RemoteCallFailed('no method specified',
                                   status=http_client.BAD_REQUEST)
        # 1/ check first for old-style (JSonController) ajax func for bw compat
        try:
            func = getattr(basecontrollers.JSonController, 'js_%s' % fname)
            if PY2:
                func = func.__func__
            func = partial(func, self)
        except AttributeError:
            # 2/ check for new-style (AjaxController) ajax func
            try:
                func = self._cw.vreg['ajax-func'].select(fname, self._cw)
            except ObjectNotFound:
                raise RemoteCallFailed('no %s method' % fname,
                                       status=http_client.BAD_REQUEST)
        else:
            warn('[3.15] remote function %s found on JSonController, '
                 'use AjaxFunction / @ajaxfunc instead' % fname,
                 DeprecationWarning, stacklevel=2)
        debug_mode = self._cw.vreg.config.debugmode
        # no <arg> attribute means the callback takes no argument
        args = self._cw.form.get('arg', ())
        if not isinstance(args, (list, tuple)):
            args = (args,)
        try:
            args = [json.loads(arg) for arg in args]
        except ValueError as exc:
            if debug_mode:
                self.exception('error while decoding json arguments for '
                               'js_%s: %s (err: %s)', fname, args, exc)
            raise RemoteCallFailed(exc_message(exc, self._cw.encoding),
                                   status=http_client.BAD_REQUEST)
        try:
            result = func(*args)
        except (RemoteCallFailed, DirectResponse):
            raise
        except ValidationError as exc:
            raise RemoteCallFailed(exc_message(exc, self._cw.encoding),
                                   status=http_client.BAD_REQUEST)
        except Exception as exc:
            if debug_mode:
                self.exception(
                    'an exception occurred while calling js_%s(%s): %s',
                    fname, args, exc)
            raise RemoteCallFailed(exc_message(exc, self._cw.encoding))
        if result is None:
            return b''
        # get unicode on @htmlize methods, encoded string on @jsonize methods
        elif isinstance(result, text_type):
            return result.encode(self._cw.encoding)
        return result

class AjaxFunction(AppObject):
    """
    Attributes on this base class are:

    :attr: `check_pageid`: make sure the pageid received is valid before proceeding
    :attr: `output_type`:

           - *None*: no processing, no change on content-type

           - *json*: serialize with `json_dumps` and set *application/json*
                     content-type

           - *xhtml*: wrap result in an XML node and forces HTML / XHTML
                      content-type (use ``_cw.html_content_type()``)

    """
    __registry__ = 'ajax-func'
    __select__ = yes()
    __abstract__ = True

    check_pageid = False
    output_type = None

    @staticmethod
    def _rebuild_posted_form(names, values, action=None):
        form = {}
        for name, value in zip(names, values):
            # remove possible __action_xxx inputs
            if name.startswith('__action'):
                if action is None:
                    # strip '__action_' to get the actual action name
                    action = name[9:]
                continue
            # form.setdefault(name, []).append(value)
            if name in form:
                curvalue = form[name]
                if isinstance(curvalue, list):
                    curvalue.append(value)
                else:
                    form[name] = [curvalue, value]
            else:
                form[name] = value
        # simulate click on __action_%s button to help the controller
        if action:
            form['__action_%s' % action] = u'whatever'
        return form

    def validate_form(self, action, names, values):
        self._cw.form = self._rebuild_posted_form(names, values, action)
        return basecontrollers._validate_form(self._cw, self._cw.vreg)

    def _exec(self, rql, args=None, rocheck=True):
        """json mode: execute RQL and return resultset as json"""
        rql = rql.strip()
        if rql.startswith('rql:'):
            rql = rql[4:]
        if rocheck:
            self._cw.ensure_ro_rql(rql)
        try:
            return self._cw.execute(rql, args)
        except Exception as ex:
            if self._cw.vreg.config.debugmode:
                self.exception("error in _exec(rql=%s): %s", rql, ex)
            return None
        return None

    def _call_view(self, view, paginate=False, **kwargs):
        divid = self._cw.form.get('divid')
        # we need to call pagination before with the stream set
        try:
            stream = view.set_stream()
        except AttributeError:
            stream = UStringIO()
            kwargs['w'] = stream.write
            assert not paginate
        if divid == 'contentmain':
            # ensure divid isn't reused by the view (e.g. table view)
            del self._cw.form['divid']
            paginate = True
        if divid == 'contentmain':
            stream.write(u'<div id="contentmain">')
        nav_html = UStringIO()
        if paginate and not view.handle_pagination:
            view.paginate(w=nav_html.write)
        stream.write(nav_html.getvalue())
        view.render(**kwargs)
        stream.write(nav_html.getvalue())
        if divid == 'contentmain':
            stream.write(u'</div>')
        extresources = self._cw.html_headers.getvalue(skiphead=True)
        if extresources:
            stream.write(u'<div class="ajaxHtmlHead">\n') # XXX use a widget?
            stream.write(extresources)
            stream.write(u'</div>\n')
        return stream.getvalue()


def _ajaxfunc_factory(implementation, selector=yes(), _output_type=None,
                      _check_pageid=False, regid=None):
    """converts a standard python function into an AjaxFunction appobject"""
    class AnAjaxFunc(AjaxFunction):
        __regid__ = regid or implementation.__name__
        __select__ = selector
        output_type = _output_type
        check_pageid = _check_pageid

        def serialize(self, content):
            if self.output_type is None:
                return content
            elif self.output_type == 'xhtml':
                self._cw.set_content_type(self._cw.html_content_type())
                return ''.join((u'<div>',
                                content.strip(), u'</div>'))
            elif self.output_type == 'json':
                self._cw.set_content_type('application/json')
                return json_dumps(content)
            raise RemoteCallFailed('no serializer found for output type %s'
                                   % self.output_type)

        def __call__(self, *args, **kwargs):
            if self.check_pageid:
                data = self._cw.session.data.get(self._cw.pageid)
                if data is None:
                    raise RemoteCallFailed(self._cw._('pageid-not-found'))
            return self.serialize(implementation(self, *args, **kwargs))

    AnAjaxFunc.__name__ = implementation.__name__
    # make sure __module__ refers to the original module otherwise
    # vreg.register(obj) will ignore ``obj``.
    AnAjaxFunc.__module__ = implementation.__module__
    # relate the ``implementation`` object to its wrapper appobject
    # will be used by e.g.:
    #   import base_module
    #   @ajaxfunc
    #   def foo(self):
    #       return 42
    #   assert foo(object) == 42
    #   vreg.register_and_replace(foo, base_module.older_foo)
    implementation.__appobject__ = AnAjaxFunc
    return implementation


def ajaxfunc(implementation=None, selector=yes(), output_type=None,
             check_pageid=False, regid=None):
    """promote a standard function to an ``AjaxFunction`` appobject.

    All parameters are optional:

    :param selector: a custom selector object if needed, default is ``yes()``

    :param output_type: either None, 'json' or 'xhtml' to customize output
                        content-type. Default is None

    :param check_pageid: whether the function requires a valid `pageid` or not
                         to proceed. Default is False.

    :param regid: a custom __regid__ for the created ``AjaxFunction`` object. Default
                  is to keep the wrapped function name.

    ``ajaxfunc`` can be used both as a standalone decorator:

    .. sourcecode:: python

        @ajaxfunc
        def my_function(self):
            return 42

    or as a parametrizable decorator:

    .. sourcecode:: python

        @ajaxfunc(output_type='json')
        def my_function(self):
            return 42

    """
    # if used as a parametrized decorator (e.g. @ajaxfunc(output_type='json'))
    if implementation is None:
        def _decorator(func):
            return _ajaxfunc_factory(func, selector=selector,
                                     _output_type=output_type,
                                     _check_pageid=check_pageid,
                                     regid=regid)
        return _decorator
    # else, used as a standalone decorator (i.e. @ajaxfunc)
    return _ajaxfunc_factory(implementation, selector=selector,
                             _output_type=output_type,
                             _check_pageid=check_pageid, regid=regid)



###############################################################################
#  Cubicweb remote functions for :                                            #
#  - appobject rendering                                                      #
#  - user / page session data management                                      #
###############################################################################
@ajaxfunc(output_type='xhtml')
def view(self):
    # XXX try to use the page-content template
    req = self._cw
    rql = req.form.get('rql')
    if rql:
        rset = self._exec(rql)
    elif 'eid' in req.form:
        rset = self._cw.eid_rset(req.form['eid'])
    else:
        rset = None
    vid = req.form.get('vid') or vid_from_rset(req, rset, self._cw.vreg.schema)
    try:
        viewobj = self._cw.vreg['views'].select(vid, req, rset=rset)
    except NoSelectableObject:
        vid = req.form.get('fallbackvid', 'noresult')
        viewobj = self._cw.vreg['views'].select(vid, req, rset=rset)
    viewobj.set_http_cache_headers()
    if req.is_client_cache_valid():
        return ''
    return self._call_view(viewobj, paginate=req.form.pop('paginate', False))


@ajaxfunc(output_type='xhtml')
def component(self, compid, rql, registry='components', extraargs=None):
    if rql:
        rset = self._exec(rql)
    else:
        rset = None
    # XXX while it sounds good, addition of the try/except below cause pb:
    # when filtering using facets return an empty rset, the edition box
    # isn't anymore selectable, as expected. The pb is that with the
    # try/except below, we see a "an error occurred" message in the ui, while
    # we don't see it without it. Proper fix would probably be to deal with
    # this by allowing facet handling code to tell to js_component that such
    # error is expected and should'nt be reported.
    #try:
    comp = self._cw.vreg[registry].select(compid, self._cw, rset=rset,
                                          **optional_kwargs(extraargs))
    #except NoSelectableObject:
    #    raise RemoteCallFailed('unselectable')
    return self._call_view(comp, **optional_kwargs(extraargs))

@ajaxfunc(output_type='xhtml')
def render(self, registry, oid, eid=None,
              selectargs=None, renderargs=None):
    if eid is not None:
        rset = self._cw.eid_rset(eid)
        # XXX set row=0
    elif self._cw.form.get('rql'):
        rset = self._cw.execute(self._cw.form['rql'])
    else:
        rset = None
    viewobj = self._cw.vreg[registry].select(oid, self._cw, rset=rset,
                                             **optional_kwargs(selectargs))
    return self._call_view(viewobj, **optional_kwargs(renderargs))


@ajaxfunc(output_type='json')
def i18n(self, msgids):
    """returns the translation of `msgid`"""
    return [self._cw._(msgid) for msgid in msgids]

@ajaxfunc(output_type='json')
def format_date(self, strdate):
    """returns the formatted date for `msgid`"""
    date = strptime(strdate, '%Y-%m-%d %H:%M:%S')
    return self._cw.format_date(date)

@ajaxfunc(output_type='json')
def external_resource(self, resource):
    """returns the URL of the external resource named `resource`"""
    return self._cw.uiprops[resource]

@ajaxfunc
def unload_page_data(self):
    """remove user's session data associated to current pageid"""
    self._cw.session.data.pop(self._cw.pageid, None)

@ajaxfunc(output_type='json')
@deprecated("[3.13] use jQuery.cookie(cookiename, cookievalue, {path: '/'}) in js land instead")
def set_cookie(self, cookiename, cookievalue):
    """generates the Set-Cookie HTTP reponse header corresponding
    to `cookiename` / `cookievalue`.
    """
    cookiename, cookievalue = str(cookiename), str(cookievalue)
    self._cw.set_cookie(cookiename, cookievalue)



@ajaxfunc
def delete_relation(self, rtype, subjeid, objeid):
    rql = 'DELETE S %s O WHERE S eid %%(s)s, O eid %%(o)s' % rtype
    self._cw.execute(rql, {'s': subjeid, 'o': objeid})

@ajaxfunc
def add_relation(self, rtype, subjeid, objeid):
    rql = 'SET S %s O WHERE S eid %%(s)s, O eid %%(o)s' % rtype
    self._cw.execute(rql, {'s': subjeid, 'o': objeid})
