from __future__ import absolute_import


from pyramid.httpexceptions import HTTPNotFound
from pyramid.view import view_config
from pyramid_cubicweb.resources import EntityResource, ETypeResource


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
