from __future__ import absolute_import


from pyramid.view import view_config
from cubicweb.pyramid.resources import EntityResource, ETypeResource


@view_config(
    route_name='cwentities',
    context=EntityResource,
    request_method='DELETE')
def delete_entity(context, request):
    context.rset.one().cw_delete()
    request.response.status_int = 204
    return request.response


def includeme(config):
    config.add_route(
        'cwentities', '/{etype}/*traverse',
        factory=ETypeResource.from_match('etype'), match_is_etype='etype')
    config.scan(__name__)
