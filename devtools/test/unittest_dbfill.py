# -*- coding: iso-8859-1 -*-
"""unit tests for database value generator

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import os.path as osp
import re

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.schema import Schema, EntitySchema
from cubicweb.devtools.fill import ValueGenerator, make_tel
from cubicweb.devtools import ApptestConfiguration

DATADIR = osp.join(osp.abspath(osp.dirname(__file__)), 'data')
ISODATE_SRE = re.compile('(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$')


class MyValueGenerator(ValueGenerator):

    def generate_Bug_severity(self, index):
        return u'dangerous'

    def generate_Any_description(self, index, format=None):
        return u'yo'


class ValueGeneratorTC(TestCase):
    """test case for ValueGenerator"""

    def _choice_func(self, etype, attrname):
        try:
            return getattr(self, '_available_%s_%s' % (etype, attrname))(etype, attrname)
        except AttributeError:
            return None

    def _available_Person_firstname(self, etype, attrname):
        return [f.strip() for f in file(osp.join(DATADIR, 'firstnames.txt'))]


    def setUp(self):
        config = ApptestConfiguration('data')
        config.bootstrap_cubes()
        schema = config.load_schema()
        e_schema = schema.entity_schema('Person')
        self.person_valgen = ValueGenerator(e_schema, self._choice_func)
        e_schema = schema.entity_schema('Bug')
        self.bug_valgen = MyValueGenerator(e_schema)
        self.config = config

    def _check_date(self, date):
        """checks that 'date' is well-formed"""
        year = date.year
        month = date.month
        day = date.day
        self.failUnless(day in range(1, 29), '%s not in [0;28]' % day)
        self.failUnless(month in range(1, 13), '%s not in [1;12]' % month)
        self.failUnless(year in range(2000, 2005),
                        '%s not in [2000;2004]' % year)


    def test_string(self):
        """test string generation"""
        surname = self.person_valgen._generate_value('surname', 12)
        self.assertEquals(surname, u'é&surname12')

    def test_domain_value(self):
        """test value generation from a given domain value"""
        firstname = self.person_valgen._generate_value('firstname', 12)
        possible_choices = self._choice_func('Person', 'firstname')
        self.failUnless(firstname in possible_choices,
                        '%s not in %s' % (firstname, possible_choices))

    def test_choice(self):
        """test choice generation"""
        # Test for random index
        for index in range(5):
            sx_value = self.person_valgen._generate_value('civility', index)
            self.failUnless(sx_value in ('Mr', 'Mrs', 'Ms'))

    def test_integer(self):
        """test integer generation"""
        # Test for random index
        for index in range(5):
            cost_value = self.bug_valgen._generate_value('cost', index)
            self.failUnless(cost_value in range(index+1))

    def test_date(self):
        """test date generation"""
        # Test for random index
        for index in range(5):
            date_value = self.person_valgen._generate_value('birthday', index)
            self._check_date(date_value)

    def test_phone(self):
        """tests make_tel utility"""
        self.assertEquals(make_tel(22030405), '22 03 04 05')


    def test_customized_generation(self):
        self.assertEquals(self.bug_valgen._generate_value('severity', 12),
                          u'dangerous')
        self.assertEquals(self.bug_valgen._generate_value('description', 12),
                          u'yo')
        self.assertEquals(self.person_valgen._generate_value('description', 12),
                          u'yo')



class ConstraintInsertionTC(TestCase):

    def test_writeme(self):
        self.skip('Test automatic insertion / Schema Constraints')


if __name__ == '__main__':
    unittest_main()
