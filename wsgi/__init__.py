"""This package contains all WSGI specific code for cubicweb

NOTE: this package borrows a lot of code to Django
      (http://www.djangoproject.com) and to the wsgiref module
      of the python2.5's stdlib.

WSGI corresponding PEP: http://www.python.org/dev/peps/pep-0333/

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from email import message, message_from_string
from Cookie import SimpleCookie
from StringIO import StringIO
from cgi import parse_header, parse_qsl
from pprint import pformat as _pformat


def pformat(obj):
    """pretty prints `obj` if possible"""
    try:
        return _pformat(obj)
    except:
        return u'<could not parse>'
    
def qs2dict(qs):
    """transforms a query string into a regular python dict"""
    result = {}
    for key, value in parse_qsl(qs, True):
        result.setdefault(key, []).append(value)
    return result

def normalize_header(header):
    """returns a normalized header name
    
    >>> normalize_header('User_Agent')
    'User-agent'
    """
    return header.replace('_', '-').capitalize()

def safe_copyfileobj(fsrc, fdst, length=16*1024, size=0):
    """
    THIS COMES FROM DJANGO
    A version of shutil.copyfileobj that will not read more than 'size' bytes.
    This makes it safe from clients sending more than CONTENT_LENGTH bytes of
    data in the body.
    """
    if not size:
        return
    while size > 0:
        buf = fsrc.read(min(length, size))
        if not buf:
            break
        fdst.write(buf)
        size -= len(buf)

def parse_file_upload(header_dict, post_data):
    """This is adapted FROM DJANGO"""
    raw_message = '\r\n'.join('%s:%s' % pair for pair in header_dict.iteritems())
    raw_message += '\r\n\r\n' + post_data
    msg = message_from_string(raw_message)
    post, files = {}, {}
    for submessage in msg.get_payload():
        name_dict = parse_header(submessage['Content-Disposition'])[1]
        key = name_dict['name']
        # name_dict is something like {'name': 'file', 'filename': 'test.txt'} for file uploads
        # or {'name': 'blah'} for POST fields
        # We assume all uploaded files have a 'filename' set.
        if 'filename' in name_dict:
            assert type([]) != type(submessage.get_payload()), "Nested MIME messages are not supported"
            if not name_dict['filename'].strip():
                continue
            # IE submits the full path, so trim everything but the basename.
            # (We can't use os.path.basename because that uses the server's
            # directory separator, which may not be the same as the
            # client's one.)
            filename = name_dict['filename'][name_dict['filename'].rfind("\\")+1:]
            mimetype = 'Content-Type' in submessage and submessage['Content-Type'] or None
            content = StringIO(submessage.get_payload())
            files[key] = [filename, mimetype, content]
        else:
            post.setdefault(key, []).append(submessage.get_payload())
    return post, files

