from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.views.xmlrss import SERIALIZERS

class EntityXMLViewTC(CubicWebTC):
    """see also cw.sobjects.test.unittest_parsers"""
    def test(self):
        rels = ['tags-object', 'in_group-subject',
                'in_state-subject', 'use_email-subject']
        with self.admin_access.web_request(relation=rels) as req:
            self.assertMultiLineEqual(
                req.user.view('xml'),
                '''\
<CWUser eid="6" cwuri="http://testing.fr/cubicweb/6" cwsource="system">
  <login>admin</login>
  <upassword/>
  <firstname/>
  <surname/>
  <last_login_time/>
  <creation_date>%(cdate)s</creation_date>
  <modification_date>%(mdate)s</modification_date>
  <tags role="object">
  </tags>
  <in_group role="subject">
    <CWGroup eid="%(group_eid)s" cwuri="http://testing.fr/cubicweb/%(group_eid)s"/>
  </in_group>
  <in_state role="subject">
    <State eid="%(state_eid)s" cwuri="http://testing.fr/cubicweb/%(state_eid)s" name="activated"/>
  </in_state>
  <use_email role="subject">
  </use_email>
</CWUser>
''' % {'cdate': SERIALIZERS['Datetime'](req.user.creation_date),
       'mdate': SERIALIZERS['Datetime'](req.user.modification_date),
       'state_eid': req.user.in_state[0].eid,
       'group_eid': req.user.in_group[0].eid})


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
