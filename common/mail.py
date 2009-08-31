"""Common utilies to format / semd emails.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from base64 import b64encode, b64decode
from itertools import repeat
from time import time
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage
from email.Header import Header
try:
    from socket import gethostname
except ImportError:
    def gethostname(): # gae
        return 'XXX'

from cubicweb.view import EntityView

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
    except:
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
    unique_addrs = lambda addrs: sorted(set(addr for addr in addrs if addr is not None))
    msg['To'] = ', '.join(addrheader(addr) for addr in unique_addrs(to_addrs))
    if cc_addrs:
        msg['Cc'] = ', '.join(addrheader(addr) for addr in unique_addrs(cc_addrs))
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


class NotificationView(EntityView):
    """abstract view implementing the "email" API (eg to simplify sending
    notification)
    """
    # XXX refactor this class to work with len(rset) > 1

    msgid_timestamp = True

    # this is usually the method to call
    def render_and_send(self, **kwargs):
        """generate and send an email message for this view"""
        delayed = kwargs.pop('delay_to_commit', None)
        for recipients, msg in self.render_emails(**kwargs):
            if delayed is None:
                self.send(recipients, msg)
            elif delayed:
                self.send_on_commit(recipients, msg)
            else:
                self.send_now(recipients, msg)

    def cell_call(self, row, col=0, **kwargs):
        self.w(self.req._(self.content) % self.context(**kwargs))

    def render_emails(self, **kwargs):
        """generate and send emails for this view (one per recipient)"""
        self._kwargs = kwargs
        recipients = self.recipients()
        if not recipients:
            self.info('skipping %s notification, no recipients', self.id)
            return
        if self.rset is not None:
            entity = self.entity(self.row or 0, self.col or 0)
            # if the view is using timestamp in message ids, no way to reference
            # previous email
            if not self.msgid_timestamp:
                refs = [self.construct_message_id(eid)
                        for eid in entity.notification_references(self)]
            else:
                refs = ()
            msgid = self.construct_message_id(entity.eid)
        else:
            refs = ()
            msgid = None
        userdata = self.req.user_data()
        origlang = self.req.lang
        for emailaddr, lang in recipients:
            self.req.set_language(lang)
            # since the same view (eg self) may be called multiple time and we
            # need a fresh stream at each iteration, reset it explicitly
            self.w = None
            # XXX call render before subject to set .row/.col attributes on the
            #     view
            content = self.render(row=0, col=0, **kwargs)
            subject = self.subject()
            msg = format_mail(userdata, [emailaddr], content, subject,
                              config=self.config, msgid=msgid, references=refs)
            yield [emailaddr], msg
        # restore language
        self.req.set_language(origlang)

    # recipients / email sending ###############################################

    def recipients(self):
        """return a list of 2-uple (email, language) to who this email should be
        sent
        """
        finder = self.vreg['components'].select('recipients_finder', self.req,
                                                rset=self.rset,
                                                row=self.row or 0,
                                                col=self.col or 0)
        return finder.recipients()

    def send_now(self, recipients, msg):
        self.config.sendmails([(msg, recipients)])

    def send_on_commit(self, recipients, msg):
        raise NotImplementedError

    send = send_now

    # email generation helpers #################################################

    def construct_message_id(self, eid):
        return construct_message_id(self.config.appid, eid, self.msgid_timestamp)

    def format_field(self, attr, value):
        return ':%(attr)s: %(value)s' % {'attr': attr, 'value': value}

    def format_section(self, attr, value):
        return '%(attr)s\n%(ul)s\n%(value)s\n' % {
            'attr': attr, 'ul': '-'*len(attr), 'value': value}

    def subject(self):
        entity = self.entity(self.row or 0, self.col or 0)
        subject = self.req._(self.message)
        etype = entity.dc_type()
        eid = entity.eid
        login = self.user_login()
        return self.req._('%(subject)s %(etype)s #%(eid)s (%(login)s)') % locals()

    def context(self, **kwargs):
        entity = self.entity(self.row or 0, self.col or 0)
        for key, val in kwargs.iteritems():
            if val and isinstance(val, unicode) and val.strip():
               kwargs[key] = self.req._(val)
        kwargs.update({'user': self.user_login(),
                       'eid': entity.eid,
                       'etype': entity.dc_type(),
                       'url': entity.absolute_url(),
                       'title': entity.dc_long_title(),})
        return kwargs

    def user_login(self):
        try:
            # if req is actually a session (we are on the server side), and we
            # have to prevent nested internal session
            return self.req.actual_session().user.login
        except AttributeError:
            return self.req.user.login
