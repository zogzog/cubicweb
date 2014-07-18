# copyright 2011-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from cubicweb.sobjects.cwxmlparser import CWEntityXMLParser

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
 <CWUser eid="5" cwuri="http://pouet.org/5" cwsource="system">
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
  <in_state role="subject">
    <State cwuri="http://pouet.org/11" eid="11" name="activated"/>
  </in_state>
 </CWUser>
</rset>
'''.splitlines())

RELATEDXML = {
    'http://pouet.org/6': u'''
<rset size="1">
 <EmailAddress eid="6" cwuri="http://pouet.org/6">
  <address>syt@logilab.fr</address>
  <modification_date>2010-04-13 14:35:56</modification_date>
  <creation_date>2010-04-13 14:35:56</creation_date>
  <tags role="object">
    <Tag cwuri="http://pouet.org/9" eid="9"/>
  </tags>
 </EmailAddress>
</rset>
''',
    'http://pouet.org/7': u'''
<rset size="1">
 <CWGroup eid="7" cwuri="http://pouet.org/7">
  <name>users</name>
  <tags role="object">
    <Tag cwuri="http://pouet.org/9" eid="9"/>
  </tags>
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


OTHERXML = ''.join(u'''
<rset size="1">
 <CWUser eid="5" cwuri="http://pouet.org/5" cwsource="myfeed">
  <login>sthenault</login>
  <upassword>toto</upassword>
  <last_login_time>2011-01-25 14:14:06</last_login_time>
  <creation_date>2010-01-22 10:27:59</creation_date>
  <modification_date>2011-01-25 14:14:06</modification_date>
  <in_group role="subject">
    <CWGroup cwuri="http://pouet.org/7" eid="7"/>
  </in_group>
 </CWUser>
</rset>
'''.splitlines()
)


class CWEntityXMLParserTC(CubicWebTC):
    """/!\ this test use a pre-setup database /!\, if you modify above xml,
    REMOVE THE DATABASE TEMPLATE else it won't be considered
    """
    test_db_id = 'xmlparser'

    @classmethod
    def pre_setup_database(cls, cnx, config):
        myfeed = cnx.create_entity('CWSource', name=u'myfeed', type=u'datafeed',
                                   parser=u'cw.entityxml', url=BASEXML)
        myotherfeed = cnx.create_entity('CWSource', name=u'myotherfeed', type=u'datafeed',
                                        parser=u'cw.entityxml', url=OTHERXML)
        cnx.commit()
        myfeed.init_mapping([(('CWUser', 'use_email', '*'),
                              u'role=subject\naction=copy'),
                             (('CWUser', 'in_group', '*'),
                              u'role=subject\naction=link\nlinkattr=name'),
                             (('CWUser', 'in_state', '*'),
                              u'role=subject\naction=link\nlinkattr=name'),
                             (('*', 'tags', '*'),
                              u'role=object\naction=link-or-create\nlinkattr=name'),
                            ])
        myotherfeed.init_mapping([(('CWUser', 'in_group', '*'),
                                   u'role=subject\naction=link\nlinkattr=name'),
                                  (('CWUser', 'in_state', '*'),
                                   u'role=subject\naction=link\nlinkattr=name'),
                                  ])
        cnx.create_entity('Tag', name=u'hop')
        cnx.commit()

    def test_complete_url(self):
        dfsource = self.repo.sources_by_uri['myfeed']
        with self.admin_access.repo_cnx() as cnx:
            parser = dfsource._get_parser(cnx)
            self.assertEqual(parser.complete_url('http://www.cubicweb.org/CWUser'),
                             'http://www.cubicweb.org/CWUser?relation=tags-object&relation=in_group-subject&relation=in_state-subject&relation=use_email-subject')
            self.assertEqual(parser.complete_url('http://www.cubicweb.org/cwuser'),
                             'http://www.cubicweb.org/cwuser?relation=tags-object&relation=in_group-subject&relation=in_state-subject&relation=use_email-subject')
            self.assertEqual(parser.complete_url('http://www.cubicweb.org/cwuser?vid=rdf&relation=hop'),
                             'http://www.cubicweb.org/cwuser?relation=hop&relation=tags-object&relation=in_group-subject&relation=in_state-subject&relation=use_email-subject&vid=rdf')
            self.assertEqual(parser.complete_url('http://www.cubicweb.org/?rql=cwuser&vid=rdf&relation=hop'),
                             'http://www.cubicweb.org/?rql=cwuser&relation=hop&vid=rdf')
            self.assertEqual(parser.complete_url('http://www.cubicweb.org/?rql=cwuser&relation=hop'),
                             'http://www.cubicweb.org/?rql=cwuser&relation=hop')


    def test_actions(self):
        dfsource = self.repo.sources_by_uri['myfeed']
        self.assertEqual(dfsource.mapping,
                         {u'CWUser': {
                             (u'in_group', u'subject', u'link'): [
                                 (u'CWGroup', {u'linkattr': u'name'})],
                             (u'in_state', u'subject', u'link'): [
                                 (u'State', {u'linkattr': u'name'})],
                             (u'tags', u'object', u'link-or-create'): [
                                 (u'Tag', {u'linkattr': u'name'})],
                             (u'use_email', u'subject', u'copy'): [
                                 (u'EmailAddress', {})]
                             },
                          u'CWGroup': {
                             (u'tags', u'object', u'link-or-create'): [
                                 (u'Tag', {u'linkattr': u'name'})],
                             },
                          u'EmailAddress': {
                             (u'tags', u'object', u'link-or-create'): [
                                 (u'Tag', {u'linkattr': u'name'})],
                             },
                          })
        with self.repo.internal_cnx() as cnx:
            stats = dfsource.pull_data(cnx, force=True, raise_on_error=True)
            self.assertEqual(sorted(stats), ['checked', 'created', 'updated'])
            self.assertEqual(len(stats['created']), 2)
            self.assertEqual(stats['updated'], set())

        with self.admin_access.web_request() as req:
            user = req.execute('CWUser X WHERE X login "sthenault"').get_entity(0, 0)
            self.assertEqual(user.creation_date, datetime(2010, 01, 22, 10, 27, 59))
            self.assertEqual(user.modification_date, datetime(2011, 01, 25, 14, 14, 06))
            self.assertEqual(user.cwuri, 'http://pouet.org/5')
            self.assertEqual(user.cw_source[0].name, 'myfeed')
            self.assertEqual(user.absolute_url(), 'http://pouet.org/5')
            self.assertEqual(len(user.use_email), 1)
            # copy action
            email = user.use_email[0]
            self.assertEqual(email.address, 'syt@logilab.fr')
            self.assertEqual(email.cwuri, 'http://pouet.org/6')
            self.assertEqual(email.absolute_url(), 'http://pouet.org/6')
            self.assertEqual(email.cw_source[0].name, 'myfeed')
            self.assertEqual(len(email.reverse_tags), 1)
            self.assertEqual(email.reverse_tags[0].name, 'hop')
            # link action
            self.assertFalse(req.execute('CWGroup X WHERE X name "unknown"'))
            groups = sorted([g.name for g in user.in_group])
            self.assertEqual(groups, ['users'])
            group = user.in_group[0]
            self.assertEqual(len(group.reverse_tags), 1)
            self.assertEqual(group.reverse_tags[0].name, 'hop')
            # link or create action
            tags = set([(t.name, t.cwuri.replace(str(t.eid), ''), t.cw_source[0].name)
                        for t in user.reverse_tags])
            self.assertEqual(tags, set((('hop', 'http://testing.fr/cubicweb/', 'system'),
                                        ('unknown', 'http://testing.fr/cubicweb/', 'system')))
                             )
        with self.repo.internal_cnx() as cnx:
            stats = dfsource.pull_data(cnx, force=True, raise_on_error=True)
            self.assertEqual(stats['created'], set())
            self.assertEqual(len(stats['updated']), 0)
            self.assertEqual(len(stats['checked']), 2)
            self.repo._type_source_cache.clear()
            self.repo._extid_cache.clear()
            stats = dfsource.pull_data(cnx, force=True, raise_on_error=True)
            self.assertEqual(stats['created'], set())
            self.assertEqual(len(stats['updated']), 0)
            self.assertEqual(len(stats['checked']), 2)

            # test move to system source
            cnx.execute('SET X cw_source S WHERE X eid %(x)s, S name "system"', {'x': email.eid})
            cnx.commit()
            rset = cnx.execute('EmailAddress X WHERE X address "syt@logilab.fr"')
            self.assertEqual(len(rset), 1)
            e = rset.get_entity(0, 0)
            self.assertEqual(e.eid, email.eid)
            self.assertEqual(e.cw_metainformation(), {'source': {'type': u'native', 'uri': u'system',
                                                                 'use-cwuri-as-url': False},
                                                      'type': 'EmailAddress',
                                                      'extid': None})
            self.assertEqual(e.cw_source[0].name, 'system')
            self.assertEqual(e.reverse_use_email[0].login, 'sthenault')
            # test everything is still fine after source synchronization
            stats = dfsource.pull_data(cnx, force=True, raise_on_error=True)
            rset = cnx.execute('EmailAddress X WHERE X address "syt@logilab.fr"')
            self.assertEqual(len(rset), 1)
            e = rset.get_entity(0, 0)
            self.assertEqual(e.eid, email.eid)
            self.assertEqual(e.cw_metainformation(), {'source': {'type': u'native', 'uri': u'system',
                                                                 'use-cwuri-as-url': False},
                                                      'type': 'EmailAddress',
                                                      'extid': None})
            self.assertEqual(e.cw_source[0].name, 'system')
            self.assertEqual(e.reverse_use_email[0].login, 'sthenault')
            cnx.commit()

            # test delete entity
            e.cw_delete()
            cnx.commit()
            # test everything is still fine after source synchronization
            stats = dfsource.pull_data(cnx, force=True, raise_on_error=True)
            rset = cnx.execute('EmailAddress X WHERE X address "syt@logilab.fr"')
            self.assertEqual(len(rset), 0)
            rset = cnx.execute('Any X WHERE X use_email E, X login "sthenault"')
            self.assertEqual(len(rset), 0)

    def test_external_entity(self):
        dfsource = self.repo.sources_by_uri['myotherfeed']
        with self.repo.internal_cnx() as cnx:
            stats = dfsource.pull_data(cnx, force=True, raise_on_error=True)
            user = cnx.execute('CWUser X WHERE X login "sthenault"').get_entity(0, 0)
            self.assertEqual(user.creation_date, datetime(2010, 01, 22, 10, 27, 59))
            self.assertEqual(user.modification_date, datetime(2011, 01, 25, 14, 14, 06))
            self.assertEqual(user.cwuri, 'http://pouet.org/5')
            self.assertEqual(user.cw_source[0].name, 'myfeed')

    def test_noerror_missing_fti_attribute(self):
        dfsource = self.repo.sources_by_uri['myfeed']
        with self.repo.internal_cnx() as cnx:
            parser = dfsource._get_parser(cnx)
            dfsource.process_urls(parser, ['''
<rset size="1">
 <Card eid="50" cwuri="http://pouet.org/50" cwsource="system">
  <title>how-to</title>
 </Card>
</rset>
'''], raise_on_error=True)

    def test_noerror_unspecified_date(self):
        dfsource = self.repo.sources_by_uri['myfeed']
        with self.repo.internal_cnx() as cnx:
            parser = dfsource._get_parser(cnx)
            dfsource.process_urls(parser, ['''
<rset size="1">
 <Card eid="50" cwuri="http://pouet.org/50" cwsource="system">
  <title>how-to</title>
  <content>how-to</content>
  <synopsis>how-to</synopsis>
  <creation_date/>
 </Card>
</rset>
'''], raise_on_error=True)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
