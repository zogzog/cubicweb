# copyright 2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from datetime import datetime

from cubicweb.devtools.testlib import CubicWebTC

from cubicweb.sobjects.parsers import CWEntityXMLParser

orig_parse = CWEntityXMLParser.parse

def parse(self, url):
    try:
        url = RELATEDXML[url.split('?')[0]]
    except KeyError:
        pass
    return orig_parse(self, url)

def setUpModule():
    CWEntityXMLParser.parse = parse

def tearDownModule():
    CWEntityXMLParser.parse = orig_parse


BASEXML = ''.join(u'''
<rset size="1">
 <CWUser eid="5" cwuri="http://pouet.org/5">
  <login>sthenault</login>
  <upassword>toto</upassword>
  <last_login_time>2011-01-25 14:14:06</last_login_time>
  <creation_date>2010-01-22 10:27:59</creation_date>
  <modification_date>2011-01-25 14:14:06</modification_date>
  <use_email role="subject">
    <EmailAddress cwuri="http://pouet.org/6" eid="6"/>
  </use_email>
  <in_group role="subject">
    <CWGroup cwuri="http://pouet.org/7" eid="7"/>
    <CWGroup cwuri="http://pouet.org/8" eid="8"/>
  </in_group>
  <tags role="object">
    <Tag cwuri="http://pouet.org/9" eid="9"/>
    <Tag cwuri="http://pouet.org/10" eid="10"/>
  </tags>
 </CWUser>
</rset>
'''.splitlines())

RELATEDXML ={
    'http://pouet.org/6': u'''
<rset size="1">
 <EmailAddress eid="6" cwuri="http://pouet.org/6">
  <address>syt@logilab.fr</address>
  <modification_date>2010-04-13 14:35:56</modification_date>
  <creation_date>2010-04-13 14:35:56</creation_date>
 </EmailAddress>
</rset>
''',
    'http://pouet.org/7': u'''
<rset size="1">
 <CWGroup eid="7" cwuri="http://pouet.org/7">
  <name>users</name>
 </CWGroup>
</rset>
''',
    'http://pouet.org/8': u'''
<rset size="1">
 <CWGroup eid="8" cwuri="http://pouet.org/8">
  <name>unknown</name>
 </CWGroup>
</rset>
''',
    'http://pouet.org/9': u'''
<rset size="1">
 <Tag eid="9" cwuri="http://pouet.org/9">
  <name>hop</name>
 </Tag>
</rset>
''',
    'http://pouet.org/10': u'''
<rset size="1">
 <Tag eid="10" cwuri="http://pouet.org/10">
  <name>unknown</name>
 </Tag>
</rset>
''',
    }

class CWEntityXMLParserTC(CubicWebTC):
    def setup_database(self):
        req = self.request()
        source = req.create_entity('CWSource', name=u'myfeed', type=u'datafeed',
                                   parser=u'cw.entityxml', url=BASEXML)
        self.commit()
        source.init_mapping([(('CWUser', 'use_email', '*'),
                              u'role=subject\naction=copy'),
                             (('CWUser', 'in_group', '*'),
                              u'role=subject\naction=link\nlinkattr=name'),
                             (('*', 'tags', 'CWUser'),
                              u'role=object\naction=link-or-create\nlinkattr=name'),
                            ])
        req.create_entity('Tag', name=u'hop')

    def test_actions(self):
        dfsource = self.repo.sources_by_uri['myfeed']
        self.assertEqual(dfsource.mapping,
                         {u'CWUser': {
                             (u'in_group', u'subject', u'link'): [
                                 (u'CWGroup', {u'linkattr': u'name'})],
                             (u'tags', u'object', u'link-or-create'): [
                                 (u'Tag', {u'linkattr': u'name'})],
                             (u'use_email', u'subject', u'copy'): [
                                 (u'EmailAddress', {})]
                             }
                          })
        session = self.repo.internal_session()
        stats = dfsource.pull_data(session, force=True)
        self.assertEqual(sorted(stats.keys()), ['created', 'updated'])
        self.assertEqual(len(stats['created']), 2)
        self.assertEqual(stats['updated'], set())

        user = self.execute('CWUser X WHERE X login "sthenault"').get_entity(0, 0)
        self.assertEqual(user.creation_date, datetime(2010, 01, 22, 10, 27, 59))
        self.assertEqual(user.modification_date, datetime(2011, 01, 25, 14, 14, 06))
        self.assertEqual(user.cwuri, 'http://pouet.org/5')
        self.assertEqual(user.cw_source[0].name, 'myfeed')
        self.assertEqual(len(user.use_email), 1)
        # copy action
        email = user.use_email[0]
        self.assertEqual(email.address, 'syt@logilab.fr')
        self.assertEqual(email.cwuri, 'http://pouet.org/6')
        self.assertEqual(email.cw_source[0].name, 'myfeed')
        # link action
        self.assertFalse(self.execute('CWGroup X WHERE X name "unknown"'))
        groups = sorted([g.name for g in user.in_group])
        self.assertEqual(groups, ['users'])
        # link or create action
        tags = sorted([t.name for t in user.reverse_tags])
        self.assertEqual(tags, ['hop', 'unknown'])
        tag = self.execute('Tag X WHERE X name "unknown"').get_entity(0, 0)
        self.assertEqual(tag.cwuri, 'http://testing.fr/cubicweb/%s' % tag.eid)
        self.assertEqual(tag.cw_source[0].name, 'system')

        stats = dfsource.pull_data(session, force=True)
        self.assertEqual(stats['created'], set())
        self.assertEqual(len(stats['updated']), 2)
        self.repo._type_source_cache.clear()
        self.repo._extid_cache.clear()
        stats = dfsource.pull_data(session, force=True)
        self.assertEqual(stats['created'], set())
        self.assertEqual(len(stats['updated']), 2)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
