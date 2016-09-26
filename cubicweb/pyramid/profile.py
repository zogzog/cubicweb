""" Tools for profiling.

See :ref:`profiling`."""
from __future__ import print_function

import cProfile
import itertools

from pyramid.view import view_config


@view_config(route_name='profile_ping')
def ping(request):
    """ View that handle '/_profile/ping'

    It simply reply 'ping', without requiring connection to the repository.
    It is a useful as a comparison point to evaluate the actual overhead of
    more costly views.
    """
    request.response.text = u'pong'
    return request.response


@view_config(route_name='profile_cnx')
def cnx(request):
    """ View that handle '/_profile/cnx'

    Same as :func:`ping`, but it first ask for a connection to the repository.
    Useful to evaluate the overhead of opening a connection.
    """
    request.cw_cnx
    request.response.text = u'pong'
    return request.response


def wsgi_profile(app, filename='program.prof', dump_every=50):
    """ A WSGI middleware for profiling

    It enable the profiler before passing the request to the underlying
    application, and disable it just after.

    The stats will be dumped after ``dump_every`` requests

    :param filename: The filename to dump the stats to.
    :param dump_every: Number of requests after which to dump the stats.
    """

    profile = cProfile.Profile()

    counter = itertools.count(1)

    def application(environ, start_response):
        profile.enable()
        try:
            return app(environ, start_response)
        finally:
            profile.disable()
            if not counter.next() % dump_every:
                print("Dump profile stats to %s" % filename)
                profile.create_stats()
                profile.dump_stats(filename)

    return application
