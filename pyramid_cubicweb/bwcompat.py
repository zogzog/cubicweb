from pyramid import security
from pyramid import tweens
from pyramid.httpexceptions import HTTPSeeOther
from pyramid import httpexceptions

import cubicweb
import cubicweb.web

from cubicweb.web.application import CubicWebPublisher

from cubicweb.web import LogOut

from pyramid_cubicweb.core import cw_to_pyramid


class PyramidSessionHandler(object):
    """A CW Session handler that rely on the pyramid API to fetch the needed
    informations.

    It implements the :class:`cubicweb.web.application.CookieSessionHandler`
    API.
    """

    def __init__(self, appli):
        self.appli = appli

    def get_session(self, req):
        return req._request.cw_session

    def logout(self, req, goto_url):
        raise LogOut(url=goto_url)


class CubicWebPyramidHandler(object):
    """ A Pyramid request handler that rely on a cubicweb instance to do the
    whole job

    :param appli: A CubicWeb 'Application' object.
    """
    def __init__(self, appli):
        self.appli = appli

    def __call__(self, request):
        """
        Handler that mimics what CubicWebPublisher.main_handle_request and
        CubicWebPublisher.core_handle do
        """

        # XXX The main handler of CW forbid anonymous https connections
        # I guess we can drop this "feature" but in doubt I leave this comment
        # so we don't forget about it. (cdevienne)

        req = request.cw_request
        vreg = request.registry['cubicweb.registry']

        try:
            content = None
            try:
                with cw_to_pyramid(request):
                    ctrlid, rset = self.appli.url_resolver.process(req,
                                                                   req.path)

                    try:
                        controller = vreg['controllers'].select(
                            ctrlid, req, appli=self.appli)
                    except cubicweb.NoSelectableObject:
                        raise httpexceptions.HTTPUnauthorized(
                            req._('not authorized'))

                    req.update_search_state()
                    content = controller.publish(rset=rset)

                    # XXX this auto-commit should be handled by the cw_request
                    # cleanup or the pyramid transaction manager.
                    # It is kept here to have the ValidationError handling bw
                    # compatible
                    if req.cnx:
                        txuuid = req.cnx.commit()
                        # commited = True
                        if txuuid is not None:
                            req.data['last_undoable_transaction'] = txuuid
            except cubicweb.web.ValidationError as ex:
                # XXX The validation_error_handler implementation is light, we
                # should redo it better in cw_to_pyramid, so it can be properly
                # handled when raised from a cubicweb view.
                # BUT the real handling of validation errors should be done
                # earlier in the controllers, not here. In the end, the
                # ValidationError should never by handled here.
                content = self.appli.validation_error_handler(req, ex)
            except cubicweb.web.RemoteCallFailed as ex:
                # XXX The default pyramid error handler (or one that we provide
                # for this exception) should be enough
                # content = self.appli.ajax_error_handler(req, ex)
                raise
            except cubicweb.web.NotFound as ex:
                raise httpexceptions.HTTPNotFound(ex.message)

            if content is not None:
                request.response.body = content

            # XXX CubicWebPyramidRequest.headers_out should
            # access directly the pyramid response headers.
            request.response.headers.clear()
            for k, v in req.headers_out.getAllRawHeaders():
                for item in v:
                    request.response.headers.add(k, item)

        except LogOut as ex:
            # The actual 'logging out' logic should be in separated function
            # that is accessible by the pyramid views
            headers = security.forget(request)
            raise HTTPSeeOther(ex.url, headers=headers)
        except cubicweb.AuthenticationError:
            # Will occur upon access to req.cnx which is a
            # cubicweb.dbapi._NeedAuthAccessMock.
            if not content:
                content = vreg['views'].main_template(req, 'login')
                request.response.body = content

        return request.response


class TweenHandler(object):
    """ A Pyramid tween handler that submit unhandled requests to a Cubicweb
    handler.

    The CubicWeb handler to use is expected to be in the pyramid registry, at
    key ``'cubicweb.handler'``.
    """
    def __init__(self, handler, registry):
        self.handler = handler
        self.cwhandler = registry['cubicweb.handler']

    def __call__(self, request):
        if request.path.startswith('/https/'):
            request.environ['PATH_INFO'] = request.environ['PATH_INFO'][6:]
            assert not request.path.startswith('/https/')
            request.scheme = 'https'
        try:
            response = self.handler(request)
        except httpexceptions.HTTPNotFound:
            response = self.cwhandler(request)
        return response


def includeme(config):
    """ Set up a tween app that will handle the request if the main application
    raises a HTTPNotFound exception.

    This is to keep legacy compatibility for cubes that makes use of the
    cubicweb urlresolvers.

    It provides, for now, support for cubicweb controllers, but this feature
    will be reimplemented separatly in a less compatible way.

    It is automatically included by the configuration system, but can be
    disabled in the :ref:`pyramid_settings`:

    .. code-block:: ini

        cubicweb.bwcompat = no
    """
    cwconfig = config.registry['cubicweb.config']
    repository = config.registry['cubicweb.repository']
    cwappli = CubicWebPublisher(
        repository, cwconfig,
        session_handler_fact=PyramidSessionHandler)
    cwhandler = CubicWebPyramidHandler(cwappli)

    config.registry['cubicweb.appli'] = cwappli
    config.registry['cubicweb.handler'] = cwhandler

    config.add_tween(
        'pyramid_cubicweb.bwcompat.TweenHandler', under=tweens.EXCVIEW)
