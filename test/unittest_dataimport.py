# -*- coding: utf-8 -*-

import datetime as DT
from StringIO import StringIO

from logilab.common.testlib import TestCase, unittest_main

from cubicweb import dataimport
from cubicweb.devtools.testlib import CubicWebTC


class RQLObjectStoreTC(CubicWebTC):

    def test_all(self):
        with self.admin_access.repo_cnx() as cnx:
            store = dataimport.RQLObjectStore(cnx)
            group_eid = store.create_entity('CWGroup', name=u'grp').eid
            user_eid = store.create_entity('CWUser', login=u'lgn', upassword=u'pwd').eid
            store.relate(user_eid, 'in_group', group_eid)
            cnx.commit()

        with self.admin_access.repo_cnx() as cnx:
            users = cnx.execute('CWUser X WHERE X login "lgn"')
            self.assertEqual(1, len(users))
            self.assertEqual(user_eid, users.one().eid)
            groups = cnx.execute('CWGroup X WHERE U in_group X, U login "lgn"')
            self.assertEqual(1, len(users))
            self.assertEqual(group_eid, groups.one().eid)


class CreateCopyFromBufferTC(TestCase):

    # test converters

    def test_convert_none(self):
        cnvt = dataimport._copyfrom_buffer_convert_None
        self.assertEqual('NULL', cnvt(None))

    def test_convert_number(self):
        cnvt = dataimport._copyfrom_buffer_convert_number
        self.assertEqual('42', cnvt(42))
        self.assertEqual('42', cnvt(42L))
        self.assertEqual('42.42', cnvt(42.42))

    def test_convert_string(self):
        cnvt = dataimport._copyfrom_buffer_convert_string
        # simple
        self.assertEqual('babar', cnvt('babar'))
        # unicode
        self.assertEqual('\xc3\xa9l\xc3\xa9phant', cnvt(u'éléphant'))
        self.assertEqual('\xe9l\xe9phant', cnvt(u'éléphant', encoding='latin1'))
        self.assertEqual('babar#', cnvt('babar\t', replace_sep='#'))
        self.assertRaises(ValueError, cnvt, 'babar\t')

    def test_convert_date(self):
        cnvt = dataimport._copyfrom_buffer_convert_date
        self.assertEqual('0666-01-13', cnvt(DT.date(666, 1, 13)))

    def test_convert_time(self):
        cnvt = dataimport._copyfrom_buffer_convert_time
        self.assertEqual('06:06:06.000100', cnvt(DT.time(6, 6, 6, 100)))

    def test_convert_datetime(self):
        cnvt = dataimport._copyfrom_buffer_convert_datetime
        self.assertEqual('0666-06-13 06:06:06.000000', cnvt(DT.datetime(666, 6, 13, 6, 6, 6)))

    # test buffer
    def test_create_copyfrom_buffer_tuple(self):
        cnvt = dataimport._create_copyfrom_buffer
        data = ((42, 42L, 42.42, u'éléphant', DT.date(666, 1, 13), DT.time(6, 6, 6), DT.datetime(666, 6, 13, 6, 6, 6)),
                (6, 6L, 6.6, u'babar', DT.date(2014, 1, 14), DT.time(4, 2, 1), DT.datetime(2014, 1, 1, 0, 0, 0)))
        results = dataimport._create_copyfrom_buffer(data)
        # all columns
        expected = '''42\t42\t42.42\téléphant\t0666-01-13\t06:06:06.000000\t0666-06-13 06:06:06.000000
6\t6\t6.6\tbabar\t2014-01-14\t04:02:01.000000\t2014-01-01 00:00:00.000000'''
        self.assertMultiLineEqual(expected, results.getvalue())
        # selected columns
        results = dataimport._create_copyfrom_buffer(data, columns=(1, 3, 6))
        expected = '''42\téléphant\t0666-06-13 06:06:06.000000
6\tbabar\t2014-01-01 00:00:00.000000'''
        self.assertMultiLineEqual(expected, results.getvalue())

    def test_create_copyfrom_buffer_dict(self):
        cnvt = dataimport._create_copyfrom_buffer
        data = (dict(integer=42, double=42.42, text=u'éléphant', date=DT.datetime(666, 6, 13, 6, 6, 6)),
                dict(integer=6, double=6.6, text=u'babar', date=DT.datetime(2014, 1, 1, 0, 0, 0)))
        results = dataimport._create_copyfrom_buffer(data, ('integer', 'text'))
        expected = '''42\téléphant\n6\tbabar'''
        self.assertMultiLineEqual(expected, results.getvalue())


class UcsvreaderTC(TestCase):

    def test_empty_lines_skipped(self):
        stream = StringIO('''a,b,c,d,
1,2,3,4,
,,,,
,,,,
''')
        self.assertEqual([[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u''],
                          ],
                         list(dataimport.ucsvreader(stream)))
        stream.seek(0)
        self.assertEqual([[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u''],
                          [u'', u'', u'', u'', u''],
                          [u'', u'', u'', u'', u'']
                          ],
                         list(dataimport.ucsvreader(stream, skip_empty=False)))

    def test_skip_first(self):
        stream = StringIO('a,b,c,d,\n'
                          '1,2,3,4,\n')
        reader = dataimport.ucsvreader(stream, skipfirst=True,
                                       ignore_errors=True)
        self.assertEqual(list(reader),
                         [[u'1', u'2', u'3', u'4', u'']])

        stream.seek(0)
        reader = dataimport.ucsvreader(stream, skipfirst=True,
                                       ignore_errors=False)
        self.assertEqual(list(reader),
                         [[u'1', u'2', u'3', u'4', u'']])

        stream.seek(0)
        reader = dataimport.ucsvreader(stream, skipfirst=False,
                                       ignore_errors=True)
        self.assertEqual(list(reader),
                         [[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u'']])

        stream.seek(0)
        reader = dataimport.ucsvreader(stream, skipfirst=False,
                                       ignore_errors=False)
        self.assertEqual(list(reader),
                         [[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u'']])


class MetaGeneratorTC(CubicWebTC):

    def test_dont_generate_relation_to_internal_manager(self):
        with self.admin_access.repo_cnx() as cnx:
            metagen = dataimport.MetaGenerator(cnx)
            self.assertIn('created_by', metagen.etype_rels)
            self.assertIn('owned_by', metagen.etype_rels)
        with self.repo.internal_cnx() as cnx:
            metagen = dataimport.MetaGenerator(cnx)
            self.assertNotIn('created_by', metagen.etype_rels)
            self.assertNotIn('owned_by', metagen.etype_rels)

    def test_dont_generate_specified_values(self):
        with self.admin_access.repo_cnx() as cnx:
            metagen = dataimport.MetaGenerator(cnx)
            # hijack gen_modification_date to ensure we don't go through it
            metagen.gen_modification_date = None
            md = DT.datetime.now() - DT.timedelta(days=1)
            entity, rels = metagen.base_etype_dicts('CWUser')
            entity.cw_edited.update(dict(modification_date=md))
            with cnx.ensure_cnx_set:
                metagen.init_entity(entity)
            self.assertEqual(entity.cw_edited['modification_date'], md)


if __name__ == '__main__':
    unittest_main()
