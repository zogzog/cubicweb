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
"""Rules based url rewriter component, to get configurable RESTful urls"""

import re

from cubicweb.uilib import domid
from cubicweb.appobject import AppObject


def rgx(pattern, flags=0):
    """this is just a convenient shortcut to add the $ sign"""
    return re.compile(pattern+'$', flags)

class metarewriter(type):
    """auto-extend rules dictionary"""
    def __new__(mcs, name, bases, classdict):
        # collect baseclass' rules
        rules = []
        ignore_baseclass_rules = classdict.get('ignore_baseclass_rules', False)
        if not ignore_baseclass_rules:
            for base in bases:
                rules[0:0] = getattr(base, 'rules', [])
        rules[0:0] = classdict.get('rules', [])
        inputs = set()
        for data in rules[:]:
            try:
                input, output, groups = data
            except ValueError:
                input, output = data
            if input in inputs:
                rules.remove( (input, output) )
            else:
                inputs.add(input)
        classdict['rules'] = rules
        return super(metarewriter, mcs).__new__(mcs, name, bases, classdict)


class URLRewriter(AppObject, metaclass=metarewriter):
    """Base class for URL rewriters.

    Url rewriters should have a `rules` dict that maps an input URI
    to something that should be used for rewriting.

    The actual logic that defines how the rules dict is used is implemented
    in the `rewrite` method.

    A `priority` attribute might be used to indicate which rewriter
    should be tried first. The higher the priority is, the earlier the
    rewriter will be tried.
    """
    __registry__ = 'urlrewriting'
    __abstract__ = True
    priority = 1

    def rewrite(self, req, uri):
        raise NotImplementedError


class SimpleReqRewriter(URLRewriter):
    """The SimpleReqRewriters uses a `rules` dict that maps input URI
    (regexp or plain string) to a dictionary to update the request's
    form.

    If the input uri is a regexp, group substitution is allowed.
    """
    __regid__ = 'simple'

    rules = [
        ('/_', dict(vid='manage')),
        ('/_registry', dict(vid='registry')),
#        (rgx('/_([^/]+?)/?'), dict(vid=r'\1')),
        ('/schema',  dict(vid='schema')),
        ('/index', dict(vid='index')),
        ('/myprefs', dict(vid='propertiesform')),
        ('/siteconfig', dict(vid='systempropertiesform')),
        ('/siteinfo', dict(vid='siteinfo')),
        ('/manage', dict(vid='manage')),
        ('/notfound', dict(vid='404')),
        ('/error', dict(vid='error')),
        ('/sparql', dict(vid='sparql')),
        ('/processinfo', dict(vid='processinfo')),
        (rgx('/cwuser', re.I), dict(vid='cw.users-and-groups-management',
                                    tab=domid('cw.users-management'))),
        (rgx('/cwgroup', re.I), dict(vid='cw.users-and-groups-management',
                                     tab=domid('cw.groups-management'))),
        (rgx('/cwsource', re.I), dict(vid='cw.sources-management')),
        # XXX should be case insensitive as 'create', but I would like to find another way than
        # relying on the etype_selector
        (rgx('/schema/([^/]+?)/?'),  dict(vid='primary', rql=r'Any X WHERE X is CWEType, X name "\1"')),
        (rgx('/add/([^/]+?)/?'), dict(vid='creation', etype=r'\1')),
        (rgx('/doc/images/(.+?)/?'), dict(vid='wdocimages', fid=r'\1')),
        (rgx('/doc/?'), dict(vid='wdoc', fid=r'main')),
        (rgx('/doc/(.+?)/?'), dict(vid='wdoc', fid=r'\1')),
        ]

    def rewrite(self, req, uri):
        """for each `input`, `output `in rules, if `uri` matches `input`,
        req's form is updated with `output`
        """
        for data in self.rules:
            try:
                inputurl, infos, required_groups = data
            except ValueError:
                inputurl, infos = data
                required_groups = None
            if required_groups and not req.user.matching_groups(required_groups):
                continue
            if isinstance(inputurl, str):
                if inputurl == uri:
                    req.form.update(infos)
                    break
            elif inputurl.match(uri): # it's a regexp
                # XXX what about i18n? (vtitle for instance)
                for param, value in infos.items():
                    if isinstance(value, str):
                        req.form[param] = inputurl.sub(value, uri)
                    else:
                        req.form[param] = value
                break
        else:
            self.debug("no simple rewrite rule found for %s", uri)
            raise KeyError(uri)
        return None, None


def build_rset(rql, rgxgroups=None, setuser=False,
               vid=None, vtitle=None, form={}, **kwargs):

    def do_build_rset(inputurl, uri, req, schema, kwargs=kwargs):
        kwargs = kwargs.copy()
        if rgxgroups:
            match = inputurl.match(uri)
            for arg, group in rgxgroups:
                kwargs[arg] = match.group(group)
        req.form.update(form)
        if setuser:
            kwargs['u'] = req.user.eid
        if vid:
            req.form['vid'] = vid
        if vtitle:
            req.form['vtitle'] = req._(vtitle) % kwargs
        return None, req.execute(rql, kwargs)
    return do_build_rset

def update_form(**kwargs):
    def do_build_rset(inputurl, uri, req, schema):
        match = inputurl.match(uri)
        kwargs.update(match.groupdict())
        req.form.update(kwargs)
        return None, None
    return do_build_rset

def rgx_action(rql=None, args=None, argsgroups=(), setuser=False,
               form=None, formgroups=(), transforms={}, rqlformparams=(), controller=None):
    def do_build_rset(inputurl, uri, req, schema,
                      ):
        if rql:
            kwargs = args and args.copy() or {}
            if argsgroups:
                match = inputurl.match(uri)
                for key in argsgroups:
                    value = match.group(key)
                    try:
                        kwargs[key] = transforms[key](value)
                    except KeyError:
                        kwargs[key] = value
            if setuser:
                kwargs['u'] = req.user.eid
            for param in rqlformparams:
                kwargs.setdefault(param, req.form.get(param))
            rset = req.execute(rql, kwargs)
        else:
            rset = None
        form2 = form and form.copy() or {}
        if formgroups:
            match = inputurl.match(uri)
            for key in formgroups:
                form2[key] = match.group(key)
        if "vtitle" in form2:
            form2['vtitle'] = req.__(form2['vtitle'])
        if form2:
            req.form.update(form2)
        return controller, rset
    return do_build_rset


class SchemaBasedRewriter(URLRewriter):
    """Here, the rules dict maps regexps or plain strings to callbacks
    that will be called with inputurl, uri, req, schema as parameters.
    """
    __regid__ = 'schemabased'
    rules = [
        # rgxp : callback
        (rgx('/search/(.+)'), build_rset(rql=r'Any X ORDERBY FTIRANK(X) DESC WHERE X has_text %(text)s',
                                         rgxgroups=[('text', 1)])),
        ]

    def rewrite(self, req, uri):
        # XXX this could be refacted with SimpleReqRewriter
        for data in self.rules:
            try:
                inputurl, callback, required_groups = data
            except ValueError:
                inputurl, callback = data
                required_groups = None
            if required_groups and not req.user.matching_groups(required_groups):
                continue
            if isinstance(inputurl, str):
                if inputurl == uri:
                    return callback(inputurl, uri, req, self._cw.vreg.schema)
            elif inputurl.match(uri): # it's a regexp
                return callback(inputurl, uri, req, self._cw.vreg.schema)
        else:
            self.debug("no schemabased rewrite rule found for %s", uri)
            raise KeyError(uri)
