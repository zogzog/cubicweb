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
"""Associate url's path to view identifier / rql queries.

CubicWeb finds all registered URLPathEvaluators, orders them according
to their ``priority`` attribute and calls their ``evaluate_path()``
method. The first that returns something and doesn't raise a
``PathDontMatch`` exception wins.

Here is the default evaluator chain:

1. :class:`cubicweb.web.views.urlpublishing.RawPathEvaluator` handles
   unique url segments that match exactly one of the registered
   controller's *__regid__*. Urls such as */view?*, */edit?*, */json?*
   fall in that category;

2. :class:`cubicweb.web.views.urlpublishing.EidPathEvaluator` handles
   unique url segments that are eids (e.g. */1234*);

3. :class:`cubicweb.web.views.urlpublishing.URLRewriteEvaluator`
   selects all urlrewriter components, sorts them according to their
   priority, call their ``rewrite()`` method, the first one that
   doesn't raise a ``KeyError`` wins. This is where the
   :mod:`cubicweb.web.views.urlrewrite` and
   :class:`cubicweb.web.views.urlrewrite.SimpleReqRewriter` comes into
   play;

4. :class:`cubicweb.web.views.urlpublishing.RestPathEvaluator` handles
   urls based on entity types and attributes : <etype>((/<attribute
   name>])?/<attribute value>)?  This is why ``cwuser/carlos`` works;

5. :class:`cubicweb.web.views.urlpublishing.ActionPathEvaluator`
   handles any of the previous paths with an additional trailing
   "/<action>" segment, <action> being one of the registered actions'
   __regid__.


.. note::

 Actionpath executes a query whose results is lost
 because of redirecting instead of direct traversal.
"""


from rql import TypeResolverException

from cubicweb import RegistryException
from cubicweb.web import NotFound, Redirect, component, views


class PathDontMatch(Exception):
    """exception used by url evaluators to notify they can't evaluate
    a path
    """

class URLPublisherComponent(component.Component):
    """Associate url path to view identifier / rql queries, by
    applying a chain of urlpathevaluator components.

    An evaluator is a URLPathEvaluator subclass with an .evaluate_path
    method taking the request object and the path to publish as
    argument.  It will either return a publishing method identifier
    and an rql query on success or raise a `PathDontMatch` exception
    on failure. URL evaluators are called according to their
    `priority` attribute, with 0 as the greatest priority and greater
    values as lower priority. The first evaluator returning a result
    or raising something else than `PathDontMatch` will stop the
    handlers chain.
    """
    __regid__ = 'urlpublisher'
    vreg = None # XXX necessary until property for deprecation warning is on appobject

    def __init__(self, vreg, default_method='view'):
        super(URLPublisherComponent, self).__init__()
        self.vreg = vreg
        self.default_method = default_method
        evaluators = []
        for evaluatorcls in vreg['components']['urlpathevaluator']:
            # instantiation needed
            evaluator = evaluatorcls(self)
            evaluators.append(evaluator)
        self.evaluators = sorted(evaluators, key=lambda x: x.priority)

    def process(self, req, path):
        """Given a URL (essentially characterized by a path on the
        server, but additional information may be found in the request
        object), return a publishing method identifier
        (e.g. controller) and an optional result set.

        :type req: `cubicweb.web.request.CubicWebRequestBase`
        :param req: the request object

        :type path: str
        :param path: the path of the resource to publish. If empty, None or "/"
                     "view" is used as the default path.

        :rtype: tuple(str, `cubicweb.rset.ResultSet` or None)
        :return: the publishing method identifier and an optional result set

        :raise NotFound: if no handler is able to decode the given path
        """
        parts = [part for part in path.split('/')
                 if part != ''] or [self.default_method]
        language_mode = self.vreg.config.get('language-mode')
        if (language_mode == 'url-prefix'
                and parts and parts[0] in self.vreg.config.available_languages()):
            # language from URL
            req.set_language(parts.pop(0))
            path = '/'.join(parts)
            # if parts only contains lang, use 'view' default path
            if not parts:
                parts = (self.default_method,)
        elif language_mode in ('http-negotiation', 'url-prefix'):
            # negotiated language
            lang = req.negotiated_language()
            if lang:
                req.set_language(lang)
        if req.form.get('rql'):
            if parts[0] in self.vreg['controllers']:
                return parts[0], None
            return 'view', None
        for evaluator in self.evaluators:
            try:
                pmid, rset = evaluator.evaluate_path(req, parts[:])
                break
            except PathDontMatch:
                continue
        else:
            raise NotFound(path)
        if pmid is None:
            pmid = self.default_method
        return pmid, rset


class URLPathEvaluator(component.Component):
    __abstract__ = True
    __regid__ = 'urlpathevaluator'
    vreg = None # XXX necessary until property for deprecation warning is on appobject

    def __init__(self, urlpublisher):
        self.urlpublisher = urlpublisher
        self.vreg = urlpublisher.vreg


class RawPathEvaluator(URLPathEvaluator):
    """handle path of the form::

        <publishing_method>?parameters...
    """
    priority = 0
    def evaluate_path(self, req, parts):
        if len(parts) == 1 and parts[0] in self.vreg['controllers']:
            return parts[0], None
        raise PathDontMatch()


class EidPathEvaluator(URLPathEvaluator):
    """handle path with the form::

        <eid>
    """
    priority = 1
    def evaluate_path(self, req, parts):
        if len(parts) != 1:
            raise PathDontMatch()
        try:
            rset = req.execute('Any X WHERE X eid %(x)s', {'x': int(parts[0])})
        except ValueError:
            raise PathDontMatch()
        if rset.rowcount == 0:
            raise NotFound()
        return None, rset


class RestPathEvaluator(URLPathEvaluator):
    """handle path with the form::

        <etype>[[/<attribute name>]/<attribute value>]*
    """
    priority = 3

    def evaluate_path(self, req, parts):
        if not (0 < len(parts) < 4):
            raise PathDontMatch()
        try:
            etype = self.vreg.case_insensitive_etypes[parts.pop(0).lower()]
        except KeyError:
            raise PathDontMatch()
        cls = self.vreg['etypes'].etype_class(etype)
        if parts:
            if len(parts) == 2:
                attrname = parts.pop(0).lower()
                try:
                    cls.e_schema.subjrels[attrname]
                except KeyError:
                    raise PathDontMatch()
            else:
                attrname = cls.cw_rest_attr_info()[0]
            value = req.url_unquote(parts.pop(0))
            return self.handle_etype_attr(req, cls, attrname, value)
        return self.handle_etype(req, cls)

    def set_vid_for_rset(self, req, cls, rset):  # cls is there to ease overriding
        if rset.rowcount == 0:
            raise NotFound()
        if 'vid' not in req.form:
            # check_table=False tells vid_from_rset not to try to use a table view if fetch_rql
            # include some non final relation
            req.form['vid'] = views.vid_from_rset(req, rset, req.vreg.schema,
                                                  check_table=False)

    def handle_etype(self, req, cls):
        rset = req.execute(cls.fetch_rql(req.user))
        self.set_vid_for_rset(req, cls, rset)
        return None, rset

    def handle_etype_attr(self, req, cls, attrname, value):
        st = cls.fetch_rqlst(req.user, ordermethod=None)
        st.add_constant_restriction(st.get_variable('X'), attrname,
                                    'x', 'Substitute')
        if attrname == 'eid':
            try:
                rset = req.execute(st.as_string(), {'x': int(value)})
            except (ValueError, TypeResolverException):
                # conflicting eid/type
                raise PathDontMatch()
        else:
            rset = req.execute(st.as_string(), {'x': value})
        self.set_vid_for_rset(req, cls, rset)
        return None, rset


class URLRewriteEvaluator(URLPathEvaluator):
    """tries to find a rewrite rule to apply

    URL rewrite rule definitions are stored in URLRewriter objects
    """
    priority = 2

    def evaluate_path(self, req, parts):
        # uri <=> req._twreq.path or req._twreq.uri
        uri = req.url_unquote('/' + '/'.join(parts))
        evaluators = sorted(self.vreg['urlrewriting'].all_objects(),
                            key=lambda x: x.priority, reverse=True)
        for rewritercls in evaluators:
            rewriter = rewritercls(req)
            try:
                # XXX we might want to chain url rewrites
                return rewriter.rewrite(req, uri)
            except KeyError:
                continue
        raise PathDontMatch()


class ActionPathEvaluator(URLPathEvaluator):
    """handle path with the form::

    <any evaluator path>/<action>
    """
    priority = 4

    def evaluate_path(self, req, parts):
        if len(parts) < 2:
            raise PathDontMatch()
        # remove last part and see if this is something like an actions
        # if so, call
        # XXX bad smell: refactor to simpler code
        try:
            actionsreg = self.vreg['actions']
            requested = parts.pop(-1)
            actions = actionsreg[requested]
        except RegistryException:
            raise PathDontMatch()
        for evaluator in self.urlpublisher.evaluators:
            if evaluator is self or evaluator.priority == 0:
                continue
            try:
                pmid, rset = evaluator.evaluate_path(req, parts[:])
            except PathDontMatch:
                continue
            else:
                try:
                    action = actionsreg._select_best(actions, req, rset=rset)
                    if action is not None:
                        raise Redirect(action.url())
                except RegistryException:
                    pass # continue searching
        raise PathDontMatch()
