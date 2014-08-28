from cubicweb.web.request import CubicWebRequestBase
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.web.application import CubicWebPublisher


class CubicWebPyramidRequest(CubicWebRequestBase):
    def __init__(self, request):
        self._request = request

        self.path = request.upath_info

        vreg = request.registry['cubicweb.appli'].vreg
        https = request.scheme == 'https'

        post = request.params
        headers_in = request.headers

        super(CubicWebPyramidRequest, self).__init__(vreg, https, post,
                                                     headers=headers_in)

    def is_secure(self):
        return self._request.scheme == 'https'

    def relative_path(self, includeparams=True):
        path = self._request.path[1:]
        if includeparams and self._request.query_string:
            return '%s?%s' % (path, self._request.query_string)
        return path

    def instance_uri(self):
        return self._request.application_url

    def get_full_path(self):
        path = self._request.path
        if self._request.query_string:
            return '%s?%s' % (path, self._request.query_string)
        return path

    def http_method(self):
        return self._request.method

    def _set_status_out(self, value):
        self._request.response.status_int = value

    def _get_status_out(self):
        return self._request.response.status_int

    status_out = property(_get_status_out, _set_status_out)


class CubicWebPyramidHandler(object):
    def __init__(self, appli):
        self.appli = appli

    def __call__(self, request):
        req = CubicWebPyramidRequest(request)
        request.response.body = self.appli.handle_request(req, req.path)
        request.response.headers.clear()
        for k, v in req.headers_out.getAllRawHeaders():
            for item in v:
                request.response.headers.add(k, item)
        return request.response


def includeme(config):
    appid = config.registry.settings['cubicweb.instance']
    cwconfig = CubicWebConfiguration.config_for(appid)

    cwappli = CubicWebPublisher(cwconfig.repository(), cwconfig)
    handler = CubicWebPyramidHandler(cwappli)

    config.registry['cubicweb.appli'] = cwappli
    config.registry['cubicweb.handler'] = handler

    config.add_notfound_view(handler)
