from pyramid import security
from pyramid.httpexceptions import HTTPSeeOther

from cubicweb.web.application import CubicWebPublisher

from cubicweb.web import (
    StatusResponse, DirectResponse, Redirect, NotFound, LogOut,
    RemoteCallFailed, InvalidSession, RequestError, PublishException)


class PyramidSessionHandler(object):
    """A CW Session handler that rely on the pyramid API to fetch the needed
    informations"""

    def __init__(self, appli):
        self.appli = appli

    def get_session(self, req):
        return req._request.cw_session

    def logout(self, req, goto_url):
        raise LogOut(url=goto_url)


class CubicWebPyramidHandler(object):
    def __init__(self, appli):
        self.appli = appli

    def __call__(self, request):
        """
        Handler that mimics what CubicWebPublisher.main_handle_request does and
        call CubicWebPyramidHandler.core_handle.

        """
        # XXX In a later version of this handler, we need to by-pass
        # core_handle and CubicWebPublisher altogether so that the various CW
        # exceptions are converted to their pyramid equivalent.

        req = request.cw_request

        # XXX The main handler of CW forbid anonymous https connections
        # I guess we can drop this "feature" but in doubt I leave this comment
        # so we don't forget about it. (cdevienne)

        try:
            content = self.appli.core_handle(req, req.path)

            if content is not None:
                request.response.body = content
            request.response.headers.clear()
            for k, v in req.headers_out.getAllRawHeaders():
                for item in v:
                    request.response.headers.add(k, item)
        except LogOut as ex:
            # The actual 'logging out' logic should be in separated function
            # that is accessible by the pyramid views
            headers = security.forget(request)
            raise HTTPSeeOther(ex.url, headers=headers)
        except Redirect as ex:
            raise HTTPSeeOther(ex.url)
        # except AuthenticationError:
        # XXX I don't think it makes sens to catch this ex here (cdevienne)

        return request.response


def includeme(config):
    # Set up a defaut route to handle non-catched urls.
    # This is to keep legacy compatibility for cubes that makes use of the
    # cubicweb controllers.
    cwconfig = config.registry['cubicweb.config']
    repository = config.registry['cubicweb.repository']
    cwappli = CubicWebPublisher(
        repository, cwconfig,
        session_handler_fact=PyramidSessionHandler)
    handler = CubicWebPyramidHandler(cwappli)

    config.registry['cubicweb.appli'] = cwappli
    config.registry['cubicweb.handler'] = handler

    config.add_route('catchall', pattern='*path')
    config.add_view(handler, route_name='catchall')
