# copyright 2004-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb. If not, see <http://www.gnu.org/licenses/>.
"""unit tests for module cubicweb.server.schema2sql
"""

import os.path as osp

from logilab.common.testlib import TestCase, unittest_main
from logilab.database import get_db_helper

from yams.reader import SchemaLoader
from cubicweb.server import schema2sql

schema2sql.SET_DEFAULT = True

DATADIR = osp.abspath(osp.join(osp.dirname(__file__), 'data-schema2sql'))

schema = SchemaLoader().load([DATADIR])


EXPECTED_DATA_NO_DROP = """
CREATE TABLE Affaire(
 sujet varchar(128),
 ref varchar(12),
 inline_rel integer REFERENCES entities (eid)
);
CREATE INDEX idx_444e29ba3bd1f6c7ea89008613345d7b ON Affaire(inline_rel);

CREATE TABLE Company(
 name text
);

CREATE TABLE Datetest(
 dt1 timestamp,
 dt2 timestamp,
 d1 date,
 d2 date,
 t1 time,
 t2 time
, CONSTRAINT cstrf6a3dad792ba13c2cddcf61a2b737c00 CHECK(d1 <= CAST(clock_timestamp() AS DATE))
);

CREATE TABLE Division(
 name text
);

CREATE TABLE EPermission(
 name varchar(100) NOT NULL
);
CREATE INDEX idx_86fb596553c6f1ebc159422169f76c32 ON EPermission(name);

CREATE TABLE Eetype(
 name varchar(64) NOT NULL,
 description text,
 meta boolean,
 final boolean,
 initial_state integer REFERENCES entities (eid)
);
CREATE INDEX idx_f1f29b77c85f57921df19d2c29044d2d ON Eetype(name);
ALTER TABLE Eetype ADD CONSTRAINT key_f1f29b77c85f57921df19d2c29044d2d UNIQUE(name);
CREATE INDEX idx_27be7c0b18181bbdc76f3a54296dd81f ON Eetype(initial_state);

CREATE TABLE Employee(
);

CREATE TABLE Note(
 date varchar(10),
 type varchar(1),
 para varchar(512)
);

CREATE TABLE Person(
 nom varchar(64) NOT NULL,
 prenom varchar(64),
 sexe varchar(1) DEFAULT 'M',
 promo varchar(6),
 titre varchar(128),
 adel varchar(128),
 ass varchar(128),
 web varchar(128),
 tel integer,
 fax integer,
 datenaiss date,
 test boolean,
 salary float
, CONSTRAINT cstr151c2116c0c09de13fded0619d5b4aac CHECK(promo IN ('bon', 'pasbon'))
);
CREATE UNIQUE INDEX unique_e6c2d219772dbf1715597f7d9a6b3892 ON Person(nom,prenom);

CREATE TABLE Salaried(
 nom varchar(64) NOT NULL,
 prenom varchar(64),
 sexe varchar(1) DEFAULT 'M',
 promo varchar(6),
 titre varchar(128),
 adel varchar(128),
 ass varchar(128),
 web varchar(128),
 tel integer,
 fax integer,
 datenaiss date,
 test boolean,
 salary float
, CONSTRAINT cstr069569cf1791dba1a2726197c53aeb44 CHECK(promo IN ('bon', 'pasbon'))
);
CREATE UNIQUE INDEX unique_98da0f9de8588baa8966f0b1a6f850a3 ON Salaried(nom,prenom);

CREATE TABLE Societe(
 nom varchar(64),
 web varchar(128),
 tel integer,
 fax integer,
 rncs varchar(32),
 ad1 varchar(128),
 ad2 varchar(128),
 ad3 varchar(128),
 cp varchar(12),
 ville varchar(32)
, CONSTRAINT cstra0a1deaa997dcd5f9b83a77654d7c287 CHECK(fax <= tel)
);
ALTER TABLE Societe ADD CONSTRAINT key_abace82c402eba4a37ac54a7872607af UNIQUE(tel);

CREATE TABLE State(
 eid integer PRIMARY KEY REFERENCES entities (eid),
 name varchar(256) NOT NULL,
 description text
);
CREATE INDEX idx_fba3802ef9056558bb9c06b5c6ba9aab ON State(name);

CREATE TABLE Subcompany(
 name text
);

CREATE TABLE Subdivision(
 name text
);

CREATE TABLE pkginfo(
 modname varchar(30) NOT NULL,
 version varchar(10) DEFAULT '0.1' NOT NULL,
 copyright text NOT NULL,
 license varchar(3),
 short_desc varchar(80) NOT NULL,
 long_desc text NOT NULL,
 author varchar(100) NOT NULL,
 author_email varchar(100) NOT NULL,
 mailinglist varchar(100),
 debian_handler varchar(6)
, CONSTRAINT cstrbffed5ce7306d65a0db51182febd4a7b CHECK(license IN ('GPL', 'ZPL'))
, CONSTRAINT cstr2238b33d09bf7c441e0888be354c2444 CHECK(debian_handler IN ('machin', 'bidule'))
);


CREATE TABLE concerne_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_19e70eabae35becb48c247bc4a688170 PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_5ee7db9477832d6e0e847d9d9cd39f5f ON concerne_relation(eid_from);
CREATE INDEX idx_07f609872b384bb1e598cc355686a53c ON concerne_relation(eid_to);

CREATE TABLE division_of_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_ca129a4cfa4c185c7783654e9e97da5a PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_78da9d594180fecb68ef1eba0c17a975 ON division_of_relation(eid_from);
CREATE INDEX idx_0e6bd09d8d25129781928848e2f6d8d5 ON division_of_relation(eid_to);

CREATE TABLE evaluee_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_61aa7ea90ed7e43818c9865a3a7eb046 PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_69358dbe47990b4f8cf22af55b064dc5 ON evaluee_relation(eid_from);
CREATE INDEX idx_634663371244297334ff655a26d6cce3 ON evaluee_relation(eid_to);

CREATE TABLE next_state_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_24a1275472da1ccc1031f6c463cdaa95 PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_e5c1a2ddc41a057eaaf6bdf9f5c6b587 ON next_state_relation(eid_from);
CREATE INDEX idx_a3cf3cb065213186cf825e13037df826 ON next_state_relation(eid_to);

CREATE TABLE obj_wildcard_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_d252c56177735139c85aee463cd65703 PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_efbd9bd98c44bdfe2add479ab6704017 ON obj_wildcard_relation(eid_from);
CREATE INDEX idx_e8c168c66f9d6057ce14e644b8436808 ON obj_wildcard_relation(eid_to);

CREATE TABLE require_permission_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_24f38c4edaf84fdcc0f0d093fec3d5c7 PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_193987ddfd7c66bf43ded029ea363605 ON require_permission_relation(eid_from);
CREATE INDEX idx_f6dd784ff5161c4461a753591fe1de94 ON require_permission_relation(eid_to);

CREATE TABLE state_of_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_be6983bc3072230d2e22f7631a0c9e25 PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_5f17c14443de03bd1ef79750c89c2390 ON state_of_relation(eid_from);
CREATE INDEX idx_0ee453927e090f6eec01c412278dea9b ON state_of_relation(eid_to);

CREATE TABLE subcompany_of_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_25bee50df3b495a40a02aa39f832377f PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_1e6ee813030fec8d4439fc186ce752b0 ON subcompany_of_relation(eid_from);
CREATE INDEX idx_259f9ba242f4cb80b9b2f2f9a754fca7 ON subcompany_of_relation(eid_to);

CREATE TABLE subdivision_of_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_4d6f7368345676ebb66758ab71f60aef PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_a90a958166c767b50a7294e93858c1a8 ON subdivision_of_relation(eid_from);
CREATE INDEX idx_0360028629649b26da96044a12735ad4 ON subdivision_of_relation(eid_to);

CREATE TABLE subj_wildcard_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_712ea3ec0bc1976bddc93ceba0acff06 PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_4dbfa4a0d44aaa0f0816560fa8b81c22 ON subj_wildcard_relation(eid_from);
CREATE INDEX idx_09aa23f8a8b63189d05a63f8d49c7bc0 ON subj_wildcard_relation(eid_to);

CREATE TABLE sym_rel_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_c787b80522205c42402530580b0d307b PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_a46ed54f98cc4d91f0df5375d3ef73cb ON sym_rel_relation(eid_from);
CREATE INDEX idx_0faa43abe25fc83e9400a3b96daed2b2 ON sym_rel_relation(eid_to);

CREATE TABLE travaille_relation (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT key_d7b209a1f84d9cae74a98626ef0aba0b PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX idx_b00e86c772e6577ad7a7901dd0b257b2 ON travaille_relation(eid_from);
CREATE INDEX idx_970c052363294a9871a4824c9588e220 ON travaille_relation(eid_to);
"""


class SQLSchemaTC(TestCase):

    def test_known_values(self):
        dbhelper = get_db_helper('postgres')
        output = schema2sql.schema2sql(dbhelper, schema, skip_relations=('works_for',))
        self.assertMultiLineEqual(EXPECTED_DATA_NO_DROP.strip(), output.strip())


if __name__ == '__main__':
    unittest_main()
