# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Common utilies to format / send emails."""

__docformat__ = "restructuredtext en"

from base64 import b64encode, b64decode
from time import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.header import Header
from email.utils import formatdate
from socket import gethostname

def header(ustring):
    return Header(ustring.encode('UTF-8'), 'UTF-8')

def addrheader(uaddr, uname=None):
    # even if an email address should be ascii, encode it using utf8 since
    # automatic tests may generate non ascii email address
    addr = uaddr.encode('UTF-8')
    if uname:
        return '%s <%s>' % (header(uname).encode(), addr)
    return addr


def construct_message_id(appid, eid, withtimestamp=True):
    if withtimestamp:
        addrpart = 'eid=%s&timestamp=%.10f' % (eid, time())
    else:
        addrpart = 'eid=%s' % eid
    # we don't want any equal sign nor trailing newlines
    leftpart = b64encode(addrpart, '.-').rstrip().rstrip('=')
    return '<%s@%s.%s>' % (leftpart, appid, gethostname())


def parse_message_id(msgid, appid):
    if msgid[0] == '<':
        msgid = msgid[1:]
    if msgid[-1] == '>':
        msgid = msgid[:-1]
    try:
        values, qualif = msgid.split('@')
        padding = len(values) % 4
        values = b64decode(str(values + '='*padding), '.-')
        values = dict(v.split('=') for v in values.split('&'))
        fromappid, host = qualif.split('.', 1)
    except Exception:
        return None
    if appid != fromappid or host != gethostname():
        return None
    return values


def format_mail(uinfo, to_addrs, content, subject="",
                cc_addrs=(), msgid=None, references=(), config=None):
    """Sends an Email to 'e_addr' with content 'content', and subject 'subject'

    to_addrs and cc_addrs are expected to be a list of email address without
    name
    """
    assert type(content) is unicode, repr(content)
    msg = MIMEText(content.encode('UTF-8'), 'plain', 'UTF-8')
    # safety: keep only the first newline
    try:
        subject = subject.splitlines()[0]
        msg['Subject'] = header(subject)
    except IndexError:
        pass # no subject
    if uinfo.get('email'):
        email = uinfo['email']
    elif config and config['sender-addr']:
        email = unicode(config['sender-addr'])
    else:
        email = u''
    if uinfo.get('name'):
        name = uinfo['name']
    elif config and config['sender-name']:
        name = unicode(config['sender-name'])
    else:
        name = u''
    msg['From'] = addrheader(email, name)
    if config and config['sender-addr'] and config['sender-addr'] != email:
        appaddr = addrheader(config['sender-addr'], config['sender-name'])
        msg['Reply-to'] = '%s, %s' % (msg['From'], appaddr)
    elif email:
        msg['Reply-to'] = msg['From']
    if config is not None:
        msg['X-CW'] = config.appid
    unique_addrs = lambda addrs: sorted(set(addr for addr in addrs if addr is not None))
    msg['To'] = ', '.join(addrheader(addr) for addr in unique_addrs(to_addrs))
    if cc_addrs:
        msg['Cc'] = ', '.join(addrheader(addr) for addr in unique_addrs(cc_addrs))
    if msgid:
        msg['Message-id'] = msgid
    if references:
        msg['References'] = ', '.join(references)
    msg['Date'] = formatdate()
    return msg


class HtmlEmail(MIMEMultipart):

    def __init__(self, subject, textcontent, htmlcontent,
                 sendermail=None, sendername=None, recipients=None, ccrecipients=None):
        MIMEMultipart.__init__(self, 'related')
        self['Subject'] = header(subject)
        self.preamble = 'This is a multi-part message in MIME format.'
        # Attach alternative text message
        alternative = MIMEMultipart('alternative')
        self.attach(alternative)
        msgtext = MIMEText(textcontent.encode('UTF-8'), 'plain', 'UTF-8')
        alternative.attach(msgtext)
        # Attach html message
        msghtml = MIMEText(htmlcontent.encode('UTF-8'), 'html', 'UTF-8')
        alternative.attach(msghtml)
        if sendermail or sendername:
            self['From'] = addrheader(sendermail, sendername)
        if recipients:
            self['To'] = ', '.join(addrheader(addr) for addr in recipients if addr is not None)
        if ccrecipients:
            self['Cc'] = ', '.join(addrheader(addr) for addr in ccrecipients if addr is not None)

    def attach_image(self, data, htmlId):
        image = MIMEImage(data)
        image.add_header('Content-ID', '<%s>' % htmlId)
        self.attach(image)
