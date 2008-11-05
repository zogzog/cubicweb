"""Common utilies to format / semd emails.

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage
from email.Header import Header


def header(ustring):
    return Header(ustring.encode('UTF-8'), 'UTF-8')

def addrheader(uaddr, uname=None):
    # even if an email address should be ascii, encode it using utf8 since
    # application tests may generate non ascii email address
    addr = uaddr.encode('UTF-8') 
    if uname:
        return '%s <%s>' % (header(uname).encode(), addr)
    return addr


def format_mail(uinfo, to_addrs, content, subject="",
                cc_addrs=(), msgid=None, references=(), config=None):
    """Sends an Email to 'e_addr' with content 'content', and subject 'subject'

    to_addrs and cc_addrs are expected to be a list of email address without
    name
    """
    assert type(content) is unicode, repr(content)
    msg = MIMEText(content.encode('UTF-8'), 'plain', 'UTF-8')
    # safety: keep only the first newline
    subject = subject.splitlines()[0]
    msg['Subject'] = header(subject)
    if uinfo.get('email'):
        email = uinfo['email']
    elif config and config['sender-addr']:
        email = unicode(config['sender-addr'])
    else:
        email = u''
    if uinfo.get('name'):
        name = uinfo['name']
    elif config and config['sender-addr']:
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
    msg['To'] = ', '.join(addrheader(addr) for addr in to_addrs if addr is not None)
    if cc_addrs:
        msg['Cc'] = ', '.join(addrheader(addr) for addr in cc_addrs if addr is not None)
    if msgid:
        msg['Message-id'] = msgid
    if references:
        msg['References'] = ', '.join(references)
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
