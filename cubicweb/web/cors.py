# copyright 2014-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

"""A set of utility functions to handle CORS requests

Unless specified, all references in this file are related to:
  http://www.w3.org/TR/cors

The provided implementation roughly follows:
  http://www.html5rocks.com/static/images/cors_server_flowchart.png

See also:
  https://developer.mozilla.org/en-US/docs/HTTP/Access_control_CORS

"""

from six.moves.urllib.parse import urlsplit

from cubicweb.web import LOGGER
info = LOGGER.info

class CORSFailed(Exception):
    """Raised when cross origin resource sharing checks failed"""


class CORSPreflight(Exception):
    """Raised when cross origin resource sharing checks detects the
    request as a valid preflight request"""


def process_request(req, config):
    """
    Process a request to apply CORS specification algorithms

    Check whether the CORS specification is respected and set corresponding
    headers to ensure response complies with the specification.

    In case of non-compliance, no CORS-related header is set.
    """
    base_url = urlsplit(req.base_url())
    expected_host = '://'.join((base_url.scheme, base_url.netloc))
    if not req.get_header('Origin') or req.get_header('Origin') == expected_host:
        # not a CORS request, nothing to do
        return
    try:
        # handle cross origin resource sharing (CORS)
        if req.http_method() == 'OPTIONS':
            if req.get_header('Access-Control-Request-Method'):
                # preflight CORS request
                process_preflight(req, config)
        else: # Simple CORS or actual request
            process_simple(req, config)
    except CORSFailed as exc:
        info('Cross origin resource sharing failed: %s' % exc)
    except CORSPreflight:
        info('Cross origin resource sharing: valid Preflight request %s')
        raise

def process_preflight(req, config):
    """cross origin resource sharing (preflight)
    Cf http://www.w3.org/TR/cors/#resource-preflight-requests
    """
    origin = check_origin(req, config)
    allowed_methods = set(config['access-control-allow-methods'])
    allowed_headers = set(config['access-control-allow-headers'])
    try:
        method = req.get_header('Access-Control-Request-Method')
    except ValueError:
        raise CORSFailed('Access-Control-Request-Method is incorrect')
    if method not in allowed_methods:
        raise CORSFailed('Method is not allowed')
    try:
        req.get_header('Access-Control-Request-Headers', ())
    except ValueError:
        raise CORSFailed('Access-Control-Request-Headers is incorrect')
    req.set_header('Access-Control-Allow-Methods', allowed_methods, raw=False)
    req.set_header('Access-Control-Allow-Headers', allowed_headers, raw=False)

    process_common(req, config, origin)
    raise CORSPreflight()

def process_simple(req, config):
    """Handle the Simple Cross-Origin Request case
    """
    origin = check_origin(req, config)
    exposed_headers = config['access-control-expose-headers']
    if exposed_headers:
        req.set_header('Access-Control-Expose-Headers', exposed_headers, raw=False)
    process_common(req, config, origin)

def process_common(req, config, origin):
    req.set_header('Access-Control-Allow-Origin', origin)
    # in CW, we always support credential/authentication
    req.set_header('Access-Control-Allow-Credentials', 'true')

def check_origin(req, config):
    origin = req.get_header('Origin').lower()
    allowed_origins = config.get('access-control-allow-origin')
    if not allowed_origins:
        raise CORSFailed('access-control-allow-origin is not configured')
    if '*' not in allowed_origins and origin not in allowed_origins:
        raise CORSFailed('Origin is not allowed')
    # bit of sanity check; see "6.3 Security"
    myhost = urlsplit(req.base_url()).netloc
    host = req.get_header('Host')
    if host != myhost:
        info('cross origin resource sharing detected possible '
             'DNS rebinding attack Host header != host of base_url: '
             '%s != %s' % (host, myhost))
        raise CORSFailed('Host header and hostname do not match')
    # include "Vary: Origin" header (see 6.4)
    req.headers_out.addHeader('Vary', 'Origin')
    return origin
