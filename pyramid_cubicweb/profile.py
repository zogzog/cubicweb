import cProfile
import itertools
from pyramid.view import view_config


@view_config(route_name='profile_ping')
def ping(request):
    request.response.text = u'pong'
    return request.response


@view_config(route_name='profile_cnx')
def cnx(request):
    request.cw_cnx
    request.response.text = u'pong'
    return request.response


def wsgi_profile(app, filename='program.prof', dump_every=50):
    profile = cProfile.Profile()

    counter = itertools.count(1)

    def application(environ, start_response):
        profile.enable()
        try:
            return app(environ, start_response)
        finally:
            profile.disable()
            if not counter.next() % dump_every:
                print "Dump profile stats to %s" % filename
                profile.create_stats()
                profile.dump_stats(filename)

    return application
