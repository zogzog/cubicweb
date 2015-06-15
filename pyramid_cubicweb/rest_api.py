from __future__ import absolute_import

from rql import TypeResolverException

from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPNotFound
from pyramid.view import view_config


class EntityResource(object):
    def __init__(self, request, cls, attrname, value):
        self.request = request
        self.cls = cls
        self.attrname = attrname
        self.value = value

    @reify
    def rset(self):
        st = self.cls.fetch_rqlst(self.request.cw_cnx.user, ordermethod=None)
        st.add_constant_restriction(st.get_variable('X'), self.attrname,
                                    'x', 'Substitute')
        if self.attrname == 'eid':
            try:
                rset = self.request.cw_request.execute(
                    st.as_string(), {'x': int(self.value)})
            except (ValueError, TypeResolverException):
                # conflicting eid/type
                raise HTTPNotFound()
        else:
            rset = self.request.cw_request.execute(
                st.as_string(), {'x': unicode(self.value)})
        return rset


class ETypeResource(object):
    @classmethod
    def from_match(cls, matchname):
        def factory(request):
            return cls(request, request.matchdict[matchname])
        return factory

    def __init__(self, request, etype):
        vreg = request.registry['cubicweb.registry']

        self.request = request
        self.etype = vreg.case_insensitive_etypes[etype.lower()]
        self.cls = vreg['etypes'].etype_class(self.etype)

    def __getitem__(self, value):
        attrname = self.cls.cw_rest_attr_info()[0]
        return EntityResource(self.request, self.cls, attrname, value)


class MatchIsETypePredicate(object):
    def __init__(self, matchname, config):
        self.matchname = matchname
        self.etypes = frozenset(
            k.lower() for k in config.registry['cubicweb.registry']['etypes'])

    def text(self):
        return 'match_is_etype = %s' % self.matchname

    phash = text

    def __call__(self, info, request):
        return info['match'][self.matchname].lower() in \
            request.registry['cubicweb.registry'].case_insensitive_etypes


@view_config(
    route_name='cwentities',
    context=EntityResource,
    request_method='DELETE')
def delete_entity(context, request):
    context.rset.one().cw_delete()
    request.response.status_int = 204
    return request.response


def includeme(config):
    config.add_route_predicate('match_is_etype', MatchIsETypePredicate)
    config.add_route(
        'cwentities', '/{etype}/*traverse',
        factory=ETypeResource.from_match('etype'), match_is_etype='etype')
    config.scan(__name__)
