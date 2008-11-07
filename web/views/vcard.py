"""vcard import / export

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.common.view import EntityView

_ = unicode 

VCARD_PHONE_TYPES = {'home': 'HOME', 'office': 'WORK', 'mobile': 'CELL', 'fax': 'FAX'}

class VCardEUserView(EntityView):
    """export a person information as a vcard"""
    id = 'vcard'
    title = _('vcard')
    templatable = False
    content_type = 'text/x-vcard'
    accepts = ('EUser',)
        

    def set_request_content_type(self):
        """overriden to set a .vcf filename"""
        self.req.set_content_type(self.content_type, filename='vcard.vcf')
        
    def cell_call(self, row, col):
        self.vcard_header()
        self.vcard_content(self.complete_entity(row, col))
        self.vcard_footer()

    def vcard_header(self):
        self.w(u'BEGIN:vcard\n')
        self.w(u'VERSION:3.0\n')
        
    def vcard_footer(self):
        self.w(u'NOTE:this card has been generated by CubicWeb\n')
        self.w(u'END:vcard\n')
        
    def vcard_content(self, entity):
        who = u'%s %s' % (entity.surname or '',
                          entity.firstname or '')
        w = self.w
        w(u'FN:%s\n' % who)
        w(u'N:%s;;;;\n' % entity.login)
        w(u'TITLE:%s\n' % who)
        for email in entity.use_email:
            w(u'EMAIL;TYPE=INTERNET:%s\n' % email.address)

from logilab.common.deprecation import class_renamed
VCardEuserView = class_renamed('VCardEuserView', VCardEUserView)
