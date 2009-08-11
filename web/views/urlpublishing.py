"""associate url's path to view identifier / rql queries

It currently handle url's path with the forms

* <publishing_method>

* minimal REST publishing:
  * <eid>
  * <etype>[/<attribute name>/<attribute value>]*

* folder navigation


You can actually control URL (more exactly path) resolution using URL path
evaluator.

XXX actionpath and folderpath execute a query whose results is lost
because of redirecting instead of direct traversal

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"

from rql import TypeResolverException

from cubicweb import RegistryException, typed_eid
from cubicweb.web import NotFound, Redirect
from cubicweb.web.component import Component, Component


class PathDontMatch(Exception):
    """exception used by url evaluators to notify they can't evaluate
    a path
    """

class URLPublisherComponent(Component):
    """associate url's path to view identifier / rql queries,
    by applying a chain of urlpathevaluator components.

    An evaluator is a URLPathEvaluator subclass with a .evaluate_path
    method taking the request object and the path to publish as
    argument.  It will either returns a publishing method identifier
    and a rql query on success or raises a `PathDontMatch` exception
    on failure. URL evaluators are called according to their `priority`
    attribute, with 0 as the greatest priority and greater values as
    lower priority.  The first evaluator returning a result or raising
    something else than `PathDontMatch` will stop the handlers chain.
    """
    id = 'urlpublisher'

    def __init__(self, default_method='view'):
        super(URLPublisherComponent, self).__init__()
        self.default_method = default_method
        evaluators = []
        for evaluatorcls in self.vreg['components']['urlpathevaluator']:
            # instantiation needed
            evaluator = evaluatorcls(self)
            evaluators.append(evaluator)
        self.evaluators = sorted(evaluators, key=lambda x: x.priority)

    def process(self, req, path):
        """given an url (essentialy caracterized by a path on the server,
        but additional information may be found in the request object), return
        a publishing method identifier (eg controller) and an optional result
        set

        :type req: `cubicweb.web.Request`
        :param req: the request object

        :type path: str
        :param path: the path of the resource to publish

        :rtype: tuple(str, `cubicweb.common.utils.ResultSet` or None)
        :return: the publishing method identifier and an optional result set

        :raise NotFound: if no handler is able to decode the given path
        """
        parts = [part for part in path.split('/')
                 if part != ''] or (self.default_method,)
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


class URLPathEvaluator(Component):
    __abstract__ = True
    id = 'urlpathevaluator'

    def __init__(self, urlpublisher):
        self.urlpublisher = urlpublisher


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
            rset = req.execute('Any X WHERE X eid %(x)s',
                               {'x': typed_eid(parts[0])}, 'x')
        except ValueError:
            raise PathDontMatch()
        if rset.rowcount == 0:
            raise NotFound()
        return None, rset


class RestPathEvaluator(URLPathEvaluator):
    """handle path with the form::

        <etype>[[/<attribute name>]/<attribute value>]*
    """
    priority = 2

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
                    cls.e_schema.subject_relation(attrname)
                except KeyError:
                    raise PathDontMatch()
            else:
                attrname = cls._rest_attr_info()[0]
            value = req.url_unquote(parts.pop(0))
            rset = self.attr_rset(req, etype, attrname, value)
        else:
            rset = self.cls_rset(req, cls)
        if rset.rowcount == 0:
            raise NotFound()
        return None, rset

    def cls_rset(self, req, cls):
        return req.execute(cls.fetch_rql(req.user))

    def attr_rset(self, req, etype, attrname, value):
        rql = u'Any X WHERE X is %s, X %s %%(x)s' % (etype, attrname)
        if attrname == 'eid':
            try:
                rset = req.execute(rql, {'x': typed_eid(value)}, 'x')
            except (ValueError, TypeResolverException):
                # conflicting eid/type
                raise PathDontMatch()
        else:
            rset = req.execute(rql, {'x': value})
        return rset


class URLRewriteEvaluator(URLPathEvaluator):
    """tries to find a rewrite rule to apply

    URL rewrite rule definitions are stored in URLRewriter objects
    """
    priority = 3
    def evaluate_path(self, req, parts):
        # uri <=> req._twreq.path or req._twreq.uri
        uri = req.url_unquote('/' + '/'.join(parts))
        evaluators = sorted(self.vreg['urlrewriting'].all_objects(),
                            key=lambda x: x.priority, reverse=True)
        for rewritercls in evaluators:
            rewriter = rewritercls()
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
                except RegistryException:
                    continue
                else:
                    # XXX avoid redirect
                    raise Redirect(action.url())
        raise PathDontMatch()
