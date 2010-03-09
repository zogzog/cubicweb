"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

"""unit tests for module cubicweb.server.sources.rql2sql"""

import sys

from logilab.common.testlib import TestCase, unittest_main, mock_object

from rql import BadRQLQuery
from indexer import get_indexer

#from cubicweb.server.sources.native import remove_unused_solutions
from cubicweb.server.sources.rql2sql import SQLGenerator, remove_unused_solutions

from rql.utils import register_function, FunctionDescr
# add a dumb registered procedure
class stockproc(FunctionDescr):
    supported_backends = ('postgres', 'sqlite', 'mysql')
try:
    register_function(stockproc)
except AssertionError, ex:
    pass # already registered

from cubicweb.devtools import TestServerConfiguration
from cubicweb.devtools.repotest import RQLGeneratorTC

config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = config.load_schema()
schema['in_state'].inlined = True
schema['state_of'].inlined = False
schema['comments'].inlined = False

PARSER = [
    (r"Personne P WHERE P nom 'Zig\'oto';",
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P
WHERE _P.cw_nom=Zig\'oto'''),

    (r'Personne P WHERE P nom ~= "Zig\"oto%";',
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P
WHERE _P.cw_nom ILIKE Zig"oto%'''),
    ]

BASIC = [

    ("Any AS WHERE AS is Affaire",
     '''SELECT _AS.cw_eid
FROM cw_Affaire AS _AS'''),

    ("Any X WHERE X is Affaire",
     '''SELECT _X.cw_eid
FROM cw_Affaire AS _X'''),

    ("Any X WHERE X eid 0",
     '''SELECT 0'''),

    ("Personne P",
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P'''),

    ("Personne P WHERE P test TRUE",
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P
WHERE _P.cw_test=TRUE'''),

    ("Personne P WHERE P test false",
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P
WHERE _P.cw_test=FALSE'''),

    ("Personne P WHERE P eid -1",
     '''SELECT -1'''),

    ("Personne P LIMIT 20 OFFSET 10",
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P
LIMIT 20
OFFSET 10'''),

    ("Personne P WHERE S is Societe, P travaille S, S nom 'Logilab';",
     '''SELECT rel_travaille0.eid_from
FROM cw_Societe AS _S, travaille_relation AS rel_travaille0
WHERE rel_travaille0.eid_to=_S.cw_eid AND _S.cw_nom=Logilab'''),

    ("Personne P WHERE P concerne A, A concerne S, S nom 'Logilab', S is Societe;",
     '''SELECT rel_concerne0.eid_from
FROM concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1, cw_Societe AS _S
WHERE rel_concerne0.eid_to=rel_concerne1.eid_from AND rel_concerne1.eid_to=_S.cw_eid AND _S.cw_nom=Logilab'''),

    ("Note N WHERE X evaluee N, X nom 'Logilab';",
     '''SELECT rel_evaluee0.eid_to
FROM cw_Division AS _X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_X.cw_eid AND _X.cw_nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_Personne AS _X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_X.cw_eid AND _X.cw_nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_Societe AS _X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_X.cw_eid AND _X.cw_nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_SubDivision AS _X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_X.cw_eid AND _X.cw_nom=Logilab'''),

    ("Note N WHERE X evaluee N, X nom in ('Logilab', 'Caesium');",
     '''SELECT rel_evaluee0.eid_to
FROM cw_Division AS _X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_X.cw_eid AND _X.cw_nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_Personne AS _X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_X.cw_eid AND _X.cw_nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_Societe AS _X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_X.cw_eid AND _X.cw_nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_SubDivision AS _X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_X.cw_eid AND _X.cw_nom IN(Logilab, Caesium)'''),

    ("Any X WHERE X creation_date TODAY, X is Affaire",
     '''SELECT _X.cw_eid
FROM cw_Affaire AS _X
WHERE DATE(_X.cw_creation_date)=CURRENT_DATE'''),

    ("Any N WHERE G is CWGroup, G name N, E eid 12, E read_permission G",
     '''SELECT _G.cw_name
FROM cw_CWGroup AS _G, read_permission_relation AS rel_read_permission0
WHERE rel_read_permission0.eid_from=12 AND rel_read_permission0.eid_to=_G.cw_eid'''),

    ('Any Y WHERE U login "admin", U login Y', # stupid but valid...
     """SELECT _U.cw_login
FROM cw_CWUser AS _U
WHERE _U.cw_login=admin"""),

    ('Any T WHERE T tags X, X is State',
     '''SELECT rel_tags0.eid_from
FROM cw_State AS _X, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=_X.cw_eid'''),

    ('Any X,Y WHERE X eid 0, Y eid 1, X concerne Y',
     '''SELECT 0, 1
FROM concerne_relation AS rel_concerne0
WHERE rel_concerne0.eid_from=0 AND rel_concerne0.eid_to=1'''),

    ("Any X WHERE X prenom 'lulu',"
     "EXISTS(X owned_by U, U in_group G, G name 'lulufanclub' OR G name 'managers');",
     '''SELECT _X.cw_eid
FROM cw_Personne AS _X
WHERE _X.cw_prenom=lulu AND EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, in_group_relation AS rel_in_group1, cw_CWGroup AS _G WHERE rel_owned_by0.eid_from=_X.cw_eid AND rel_in_group1.eid_from=rel_owned_by0.eid_to AND rel_in_group1.eid_to=_G.cw_eid AND ((_G.cw_name=lulufanclub) OR (_G.cw_name=managers)))'''),

    ("Any X WHERE X prenom 'lulu',"
     "NOT EXISTS(X owned_by U, U in_group G, G name 'lulufanclub' OR G name 'managers');",
     '''SELECT _X.cw_eid
FROM cw_Personne AS _X
WHERE _X.cw_prenom=lulu AND NOT EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, in_group_relation AS rel_in_group1, cw_CWGroup AS _G WHERE rel_owned_by0.eid_from=_X.cw_eid AND rel_in_group1.eid_from=rel_owned_by0.eid_to AND rel_in_group1.eid_to=_G.cw_eid AND ((_G.cw_name=lulufanclub) OR (_G.cw_name=managers)))'''),



]

ADVANCED= [
    ("Societe S WHERE S nom 'Logilab' OR S nom 'Caesium'",
     '''SELECT _S.cw_eid
FROM cw_Societe AS _S
WHERE ((_S.cw_nom=Logilab) OR (_S.cw_nom=Caesium))'''),

    ('Any X WHERE X nom "toto", X eid IN (9700, 9710, 1045, 674)',
    '''SELECT _X.cw_eid
FROM cw_Division AS _X
WHERE _X.cw_nom=toto AND _X.cw_eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT _X.cw_eid
FROM cw_Personne AS _X
WHERE _X.cw_nom=toto AND _X.cw_eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT _X.cw_eid
FROM cw_Societe AS _X
WHERE _X.cw_nom=toto AND _X.cw_eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT _X.cw_eid
FROM cw_SubDivision AS _X
WHERE _X.cw_nom=toto AND _X.cw_eid IN(9700, 9710, 1045, 674)'''),

    ('Any Y, COUNT(N) GROUPBY Y WHERE Y evaluee N;',
     '''SELECT rel_evaluee0.eid_from, COUNT(rel_evaluee0.eid_to)
FROM evaluee_relation AS rel_evaluee0
GROUP BY rel_evaluee0.eid_from'''),

    ("Any X WHERE X concerne B or C concerne X",
     '''SELECT _X.cw_eid
FROM concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1, cw_Affaire AS _X
WHERE ((rel_concerne0.eid_from=_X.cw_eid) OR (rel_concerne1.eid_to=_X.cw_eid))'''),

    ("Any X WHERE X travaille S or X concerne A",
     '''SELECT _X.cw_eid
FROM concerne_relation AS rel_concerne1, cw_Personne AS _X, travaille_relation AS rel_travaille0
WHERE ((rel_travaille0.eid_from=_X.cw_eid) OR (rel_concerne1.eid_from=_X.cw_eid))'''),

    ("Any N WHERE A evaluee N or N ecrit_par P",
     '''SELECT _N.cw_eid
FROM cw_Note AS _N, evaluee_relation AS rel_evaluee0
WHERE ((rel_evaluee0.eid_to=_N.cw_eid) OR (_N.cw_ecrit_par IS NOT NULL))'''),

    ("Any N WHERE A evaluee N or EXISTS(N todo_by U)",
     '''SELECT _N.cw_eid
FROM cw_Note AS _N, evaluee_relation AS rel_evaluee0
WHERE ((rel_evaluee0.eid_to=_N.cw_eid) OR (EXISTS(SELECT 1 FROM todo_by_relation AS rel_todo_by1 WHERE rel_todo_by1.eid_from=_N.cw_eid)))'''),

    ("Any N WHERE A evaluee N or N todo_by U",
     '''SELECT _N.cw_eid
FROM cw_Note AS _N, evaluee_relation AS rel_evaluee0, todo_by_relation AS rel_todo_by1
WHERE ((rel_evaluee0.eid_to=_N.cw_eid) OR (rel_todo_by1.eid_from=_N.cw_eid))'''),

    ("Any X WHERE X concerne B or C concerne X, B eid 12, C eid 13",
     '''SELECT _X.cw_eid
FROM concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1, cw_Affaire AS _X
WHERE ((rel_concerne0.eid_from=_X.cw_eid AND rel_concerne0.eid_to=12) OR (rel_concerne1.eid_from=13 AND rel_concerne1.eid_to=_X.cw_eid))'''),

    ('Any X WHERE X created_by U, X concerne B OR C concerne X, B eid 12, C eid 13',
     '''SELECT rel_created_by0.eid_from
FROM concerne_relation AS rel_concerne1, concerne_relation AS rel_concerne2, created_by_relation AS rel_created_by0
WHERE ((rel_concerne1.eid_from=rel_created_by0.eid_from AND rel_concerne1.eid_to=12) OR (rel_concerne2.eid_from=13 AND rel_concerne2.eid_to=rel_created_by0.eid_from))'''),

    ('Any P WHERE P travaille_subdivision S1 OR P travaille_subdivision S2, S1 nom "logilab", S2 nom "caesium"',
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P, cw_SubDivision AS _S1, cw_SubDivision AS _S2, travaille_subdivision_relation AS rel_travaille_subdivision0, travaille_subdivision_relation AS rel_travaille_subdivision1
WHERE ((rel_travaille_subdivision0.eid_from=_P.cw_eid AND rel_travaille_subdivision0.eid_to=_S1.cw_eid) OR (rel_travaille_subdivision1.eid_from=_P.cw_eid AND rel_travaille_subdivision1.eid_to=_S2.cw_eid)) AND _S1.cw_nom=logilab AND _S2.cw_nom=caesium'''),

    ('Any X WHERE T tags X',
     '''SELECT rel_tags0.eid_to
FROM tags_relation AS rel_tags0'''),

    ('Any X WHERE X in_basket B, B eid 12',
     '''SELECT rel_in_basket0.eid_from
FROM in_basket_relation AS rel_in_basket0
WHERE rel_in_basket0.eid_to=12'''),

    ('Any SEN,RN,OEN WHERE X from_entity SE, SE eid 44, X relation_type R, R eid 139, X to_entity OE, OE eid 42, R name RN, SE name SEN, OE name OEN',
     '''SELECT _SE.cw_name, _R.cw_name, _OE.cw_name
FROM cw_CWAttribute AS _X, cw_CWEType AS _OE, cw_CWEType AS _SE, cw_CWRType AS _R
WHERE _X.cw_from_entity=44 AND _SE.cw_eid=44 AND _X.cw_relation_type=139 AND _R.cw_eid=139 AND _X.cw_to_entity=42 AND _OE.cw_eid=42
UNION ALL
SELECT _SE.cw_name, _R.cw_name, _OE.cw_name
FROM cw_CWEType AS _OE, cw_CWEType AS _SE, cw_CWRType AS _R, cw_CWRelation AS _X
WHERE _X.cw_from_entity=44 AND _SE.cw_eid=44 AND _X.cw_relation_type=139 AND _R.cw_eid=139 AND _X.cw_to_entity=42 AND _OE.cw_eid=42'''),

    # Any O WHERE NOT S corrected_in O, S eid %(x)s, S concerns P, O version_of P, O in_state ST, NOT ST name "published", O modification_date MTIME ORDERBY MTIME DESC LIMIT 9
    ('Any O WHERE NOT S ecrit_par O, S eid 1, S inline1 P, O inline2 P',
     '''SELECT _O.cw_eid
FROM cw_Note AS _S, cw_Personne AS _O
WHERE NOT EXISTS(SELECT 1 WHERE _S.cw_ecrit_par=_O.cw_eid) AND _S.cw_eid=1 AND _O.cw_inline2=_S.cw_inline1'''),

    ('DISTINCT Any S ORDERBY stockproc(SI) WHERE NOT S ecrit_par O, S para SI',
     '''SELECT T1.C0 FROM (SELECT DISTINCT _S.cw_eid AS C0, STOCKPROC(_S.cw_para) AS C1
FROM cw_Note AS _S
WHERE _S.cw_ecrit_par IS NULL
ORDER BY 2) AS T1'''),

    ('Any N WHERE N todo_by U, N is Note, U eid 2, N filed_under T, T eid 3',
     # N would actually be invarient if U eid 2 had given a specific type to U
     '''SELECT _N.cw_eid
FROM cw_Note AS _N, filed_under_relation AS rel_filed_under1, todo_by_relation AS rel_todo_by0
WHERE rel_todo_by0.eid_from=_N.cw_eid AND rel_todo_by0.eid_to=2 AND rel_filed_under1.eid_from=_N.cw_eid AND rel_filed_under1.eid_to=3'''),

    ('Any N WHERE N todo_by U, U eid 2, P evaluee N, P eid 3',
     '''SELECT rel_evaluee1.eid_to
FROM evaluee_relation AS rel_evaluee1, todo_by_relation AS rel_todo_by0
WHERE rel_evaluee1.eid_to=rel_todo_by0.eid_from AND rel_todo_by0.eid_to=2 AND rel_evaluee1.eid_from=3'''),


    (' Any X,U WHERE C owned_by U, NOT X owned_by U, C eid 1, X eid 2',
     '''SELECT 2, rel_owned_by0.eid_to
FROM owned_by_relation AS rel_owned_by0
WHERE rel_owned_by0.eid_from=1 AND NOT EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by1 WHERE rel_owned_by1.eid_from=2 AND rel_owned_by0.eid_to=rel_owned_by1.eid_to)'''),

    ('Any GN WHERE X in_group G, G name GN, (G name "managers" OR EXISTS(X copain T, T login in ("comme", "cochon")))',
     '''SELECT _G.cw_name
FROM cw_CWGroup AS _G, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_to=_G.cw_eid AND ((_G.cw_name=managers) OR (EXISTS(SELECT 1 FROM copain_relation AS rel_copain1, cw_CWUser AS _T WHERE rel_copain1.eid_from=rel_in_group0.eid_from AND rel_copain1.eid_to=_T.cw_eid AND _T.cw_login IN(comme, cochon))))'''),

    ('Any C WHERE C is Card, EXISTS(X documented_by C)',
      """SELECT _C.cw_eid
FROM cw_Card AS _C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_to=_C.cw_eid)"""),

    ('Any C WHERE C is Card, EXISTS(X documented_by C, X eid 12)',
      """SELECT _C.cw_eid
FROM cw_Card AS _C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_from=12 AND rel_documented_by0.eid_to=_C.cw_eid)"""),

    ('Any T WHERE C is Card, C title T, EXISTS(X documented_by C, X eid 12)',
      """SELECT _C.cw_title
FROM cw_Card AS _C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_from=12 AND rel_documented_by0.eid_to=_C.cw_eid)"""),

    ('Any GN,L WHERE X in_group G, X login L, G name GN, EXISTS(X copain T, T login L, T login IN("comme", "cochon"))',
     '''SELECT _G.cw_name, _X.cw_login
FROM cw_CWGroup AS _G, cw_CWUser AS _X, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=_X.cw_eid AND rel_in_group0.eid_to=_G.cw_eid AND EXISTS(SELECT 1 FROM copain_relation AS rel_copain1, cw_CWUser AS _T WHERE rel_copain1.eid_from=_X.cw_eid AND rel_copain1.eid_to=_T.cw_eid AND _T.cw_login=_X.cw_login AND _T.cw_login IN(comme, cochon))'''),

    ('Any X,S, MAX(T) GROUPBY X,S ORDERBY S WHERE X is CWUser, T tags X, S eid IN(32), X in_state S',
     '''SELECT _X.cw_eid, 32, MAX(rel_tags0.eid_from)
FROM cw_CWUser AS _X, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=_X.cw_eid AND _X.cw_in_state=32
GROUP BY _X.cw_eid'''),

    ('Any COUNT(S),CS GROUPBY CS ORDERBY 1 DESC LIMIT 10 WHERE S is Affaire, C is Societe, S concerne C, C nom CS, (EXISTS(S owned_by 1)) OR (EXISTS(S documented_by N, N title "published"))',
     '''SELECT COUNT(rel_concerne0.eid_from), _C.cw_nom
FROM concerne_relation AS rel_concerne0, cw_Societe AS _C
WHERE rel_concerne0.eid_to=_C.cw_eid AND ((EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by1 WHERE rel_concerne0.eid_from=rel_owned_by1.eid_from AND rel_owned_by1.eid_to=1)) OR (EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by2, cw_Card AS _N WHERE rel_concerne0.eid_from=rel_documented_by2.eid_from AND rel_documented_by2.eid_to=_N.cw_eid AND _N.cw_title=published)))
GROUP BY _C.cw_nom
ORDER BY 1 DESC
LIMIT 10'''),

    ('Any X WHERE Y evaluee X, Y is CWUser',
     '''SELECT rel_evaluee0.eid_to
FROM cw_CWUser AS _Y, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=_Y.cw_eid'''),

    ('Any L WHERE X login "admin", X identity Y, Y login L',
     '''SELECT _Y.cw_login
FROM cw_CWUser AS _X, cw_CWUser AS _Y
WHERE _X.cw_login=admin AND _X.cw_eid=_Y.cw_eid'''),

    ('Any L WHERE X login "admin", NOT X identity Y, Y login L',
     '''SELECT _Y.cw_login
FROM cw_CWUser AS _X, cw_CWUser AS _Y
WHERE _X.cw_login=admin AND NOT _X.cw_eid=_Y.cw_eid'''),

    ('Any L WHERE X login "admin", X identity Y?, Y login L',
     '''SELECT _Y.cw_login
FROM cw_CWUser AS _X LEFT OUTER JOIN cw_CWUser AS _Y ON (_X.cw_eid=_Y.cw_eid)
WHERE _X.cw_login=admin'''),

    ('Any XN ORDERBY XN WHERE X name XN, X is IN (Basket,Folder,Tag)',
     '''SELECT _X.cw_name
FROM cw_Basket AS _X
UNION ALL
SELECT _X.cw_name
FROM cw_Folder AS _X
UNION ALL
SELECT _X.cw_name
FROM cw_Tag AS _X
ORDER BY 1'''),

    # DISTINCT, can use relation under exists scope as principal
    ('DISTINCT Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), EXISTS(X read_permission Y)',
     '''SELECT DISTINCT _X.cw_eid, rel_read_permission0.eid_to
FROM cw_CWEType AS _X, read_permission_relation AS rel_read_permission0
WHERE _X.cw_name=CWGroup AND rel_read_permission0.eid_to IN(1, 2, 3) AND EXISTS(SELECT 1 WHERE rel_read_permission0.eid_from=_X.cw_eid)'''),

    # no distinct, Y can't be invariant
    ('Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), EXISTS(X read_permission Y)',
     '''SELECT _X.cw_eid, _Y.cw_eid
FROM cw_CWEType AS _X, cw_CWGroup AS _Y
WHERE _X.cw_name=CWGroup AND _Y.cw_eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=_X.cw_eid AND rel_read_permission0.eid_to=_Y.cw_eid)
UNION ALL
SELECT _X.cw_eid, _Y.cw_eid
FROM cw_CWEType AS _X, cw_RQLExpression AS _Y
WHERE _X.cw_name=CWGroup AND _Y.cw_eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=_X.cw_eid AND rel_read_permission0.eid_to=_Y.cw_eid)'''),

    # DISTINCT but NEGED exists, can't be invariant
    ('DISTINCT Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), NOT EXISTS(X read_permission Y)',
     '''SELECT DISTINCT _X.cw_eid, _Y.cw_eid
FROM cw_CWEType AS _X, cw_CWGroup AS _Y
WHERE _X.cw_name=CWGroup AND _Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=_X.cw_eid AND rel_read_permission0.eid_to=_Y.cw_eid)
UNION
SELECT DISTINCT _X.cw_eid, _Y.cw_eid
FROM cw_CWEType AS _X, cw_RQLExpression AS _Y
WHERE _X.cw_name=CWGroup AND _Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=_X.cw_eid AND rel_read_permission0.eid_to=_Y.cw_eid)'''),

    # should generate the same query as above
    ('DISTINCT Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), NOT X read_permission Y',
     '''SELECT DISTINCT _X.cw_eid, _Y.cw_eid
FROM cw_CWEType AS _X, cw_CWGroup AS _Y
WHERE _X.cw_name=CWGroup AND _Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=_X.cw_eid AND rel_read_permission0.eid_to=_Y.cw_eid)
UNION
SELECT DISTINCT _X.cw_eid, _Y.cw_eid
FROM cw_CWEType AS _X, cw_RQLExpression AS _Y
WHERE _X.cw_name=CWGroup AND _Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=_X.cw_eid AND rel_read_permission0.eid_to=_Y.cw_eid)'''),

    # neged relation, can't be inveriant
    ('Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), NOT X read_permission Y',
     '''SELECT _X.cw_eid, _Y.cw_eid
FROM cw_CWEType AS _X, cw_CWGroup AS _Y
WHERE _X.cw_name=CWGroup AND _Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=_X.cw_eid AND rel_read_permission0.eid_to=_Y.cw_eid)
UNION ALL
SELECT _X.cw_eid, _Y.cw_eid
FROM cw_CWEType AS _X, cw_RQLExpression AS _Y
WHERE _X.cw_name=CWGroup AND _Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=_X.cw_eid AND rel_read_permission0.eid_to=_Y.cw_eid)'''),

    ('Any MAX(X)+MIN(X), N GROUPBY N WHERE X name N, X is IN (Basket, Folder, Tag);',
     '''SELECT (MAX(T1.C0) + MIN(T1.C0)), T1.C1 FROM (SELECT _X.cw_eid AS C0, _X.cw_name AS C1
FROM cw_Basket AS _X
UNION ALL
SELECT _X.cw_eid AS C0, _X.cw_name AS C1
FROM cw_Folder AS _X
UNION ALL
SELECT _X.cw_eid AS C0, _X.cw_name AS C1
FROM cw_Tag AS _X) AS T1
GROUP BY T1.C1'''),

    ('Any MAX(X)+MIN(LENGTH(D)), N GROUPBY N ORDERBY 1, N, DF WHERE X data_name N, X data D, X data_format DF;',
     '''SELECT (MAX(T1.C1) + MIN(LENGTH(T1.C0))), T1.C2 FROM (SELECT _X.cw_data AS C0, _X.cw_eid AS C1, _X.cw_data_name AS C2, _X.cw_data_format AS C3
FROM cw_File AS _X
UNION ALL
SELECT _X.cw_data AS C0, _X.cw_eid AS C1, _X.cw_data_name AS C2, _X.cw_data_format AS C3
FROM cw_Image AS _X) AS T1
GROUP BY T1.C2,T1.C3
ORDER BY 1,2,T1.C3'''),

    ('DISTINCT Any S ORDERBY R WHERE A is Affaire, A sujet S, A ref R',
     '''SELECT T1.C0 FROM (SELECT DISTINCT _A.cw_sujet AS C0, _A.cw_ref AS C1
FROM cw_Affaire AS _A
ORDER BY 2) AS T1'''),

    ('DISTINCT Any MAX(X)+MIN(LENGTH(D)), N GROUPBY N ORDERBY 2, DF WHERE X data_name N, X data D, X data_format DF;',
     '''SELECT T1.C0,T1.C1 FROM (SELECT DISTINCT (MAX(T1.C1) + MIN(LENGTH(T1.C0))) AS C0, T1.C2 AS C1, T1.C3 AS C2 FROM (SELECT DISTINCT _X.cw_data AS C0, _X.cw_eid AS C1, _X.cw_data_name AS C2, _X.cw_data_format AS C3
FROM cw_File AS _X
UNION
SELECT DISTINCT _X.cw_data AS C0, _X.cw_eid AS C1, _X.cw_data_name AS C2, _X.cw_data_format AS C3
FROM cw_Image AS _X) AS T1
GROUP BY T1.C2,T1.C3
ORDER BY 2,3) AS T1
'''),

    # ambiguity in EXISTS() -> should union the sub-query
    ('Any T WHERE T is Tag, NOT T name in ("t1", "t2"), EXISTS(T tags X, X is IN (CWUser, CWGroup))',
     '''SELECT _T.cw_eid
FROM cw_Tag AS _T
WHERE NOT (_T.cw_name IN(t1, t2)) AND EXISTS(SELECT 1 FROM tags_relation AS rel_tags0, cw_CWGroup AS _X WHERE rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=_X.cw_eid UNION SELECT 1 FROM tags_relation AS rel_tags1, cw_CWUser AS _X WHERE rel_tags1.eid_from=_T.cw_eid AND rel_tags1.eid_to=_X.cw_eid)'''),

    # must not use a relation in EXISTS scope to inline a variable
    ('Any U WHERE U eid IN (1,2), EXISTS(X owned_by U)',
     '''SELECT _U.cw_eid
FROM cw_CWUser AS _U
WHERE _U.cw_eid IN(1, 2) AND EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE rel_owned_by0.eid_to=_U.cw_eid)'''),

    ('Any U WHERE EXISTS(U eid IN (1,2), X owned_by U)',
     '''SELECT _U.cw_eid
FROM cw_CWUser AS _U
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE _U.cw_eid IN(1, 2) AND rel_owned_by0.eid_to=_U.cw_eid)'''),

    ('Any COUNT(U) WHERE EXISTS (P owned_by U, P is IN (Note, Affaire))',
     '''SELECT COUNT(_U.cw_eid)
FROM cw_CWUser AS _U
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, cw_Affaire AS _P WHERE rel_owned_by0.eid_from=_P.cw_eid AND rel_owned_by0.eid_to=_U.cw_eid UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, cw_Note AS _P WHERE rel_owned_by1.eid_from=_P.cw_eid AND rel_owned_by1.eid_to=_U.cw_eid)'''),

    ('Any MAX(X)',
     '''SELECT MAX(_X.eid)
FROM entities AS _X'''),

    ('Any MAX(X) WHERE X is Note',
     '''SELECT MAX(_X.cw_eid)
FROM cw_Note AS _X'''),

    ('Any X WHERE X eid > 12',
     '''SELECT _X.eid
FROM entities AS _X
WHERE _X.eid>12'''),

    ('Any X WHERE X eid > 12, X is Note',
     """SELECT _X.eid
FROM entities AS _X
WHERE _X.type='Note' AND _X.eid>12"""),

    ('Any X, T WHERE X eid > 12, X title T, X is IN (Bookmark, Card)',
     """SELECT _X.cw_eid, _X.cw_title
FROM cw_Bookmark AS _X
WHERE _X.cw_eid>12
UNION ALL
SELECT _X.cw_eid, _X.cw_title
FROM cw_Card AS _X
WHERE _X.cw_eid>12"""),

    ('Any X',
     '''SELECT _X.eid
FROM entities AS _X'''),

    ('Any X GROUPBY X WHERE X eid 12',
     '''SELECT 12'''),

    ('Any X GROUPBY X ORDERBY Y WHERE X eid 12, X login Y',
     '''SELECT _X.cw_eid
FROM cw_CWUser AS _X
WHERE _X.cw_eid=12
GROUP BY _X.cw_eid,_X.cw_login
ORDER BY _X.cw_login'''),

    ('Any U,COUNT(X) GROUPBY U WHERE U eid 12, X owned_by U HAVING COUNT(X) > 10',
     '''SELECT rel_owned_by0.eid_to, COUNT(rel_owned_by0.eid_from)
FROM owned_by_relation AS rel_owned_by0
WHERE rel_owned_by0.eid_to=12
GROUP BY rel_owned_by0.eid_to
HAVING COUNT(rel_owned_by0.eid_from)>10'''),

    ('DISTINCT Any X ORDERBY stockproc(X) WHERE U login X',
     '''SELECT T1.C0 FROM (SELECT DISTINCT _U.cw_login AS C0, STOCKPROC(_U.cw_login) AS C1
FROM cw_CWUser AS _U
ORDER BY 2) AS T1'''),

    ('DISTINCT Any X ORDERBY Y WHERE B bookmarked_by X, X login Y',
     '''SELECT T1.C0 FROM (SELECT DISTINCT _X.cw_eid AS C0, _X.cw_login AS C1
FROM bookmarked_by_relation AS rel_bookmarked_by0, cw_CWUser AS _X
WHERE rel_bookmarked_by0.eid_to=_X.cw_eid
ORDER BY 2) AS T1'''),

    ('DISTINCT Any X ORDERBY SN WHERE X in_state S, S name SN',
     '''SELECT T1.C0 FROM (SELECT DISTINCT _X.cw_eid AS C0, _S.cw_name AS C1
FROM cw_Affaire AS _X, cw_State AS _S
WHERE _X.cw_in_state=_S.cw_eid
UNION
SELECT DISTINCT _X.cw_eid AS C0, _S.cw_name AS C1
FROM cw_CWUser AS _X, cw_State AS _S
WHERE _X.cw_in_state=_S.cw_eid
UNION
SELECT DISTINCT _X.cw_eid AS C0, _S.cw_name AS C1
FROM cw_Note AS _X, cw_State AS _S
WHERE _X.cw_in_state=_S.cw_eid
ORDER BY 2) AS T1'''),

    ('Any O,AA,AB,AC ORDERBY AC DESC '
     'WHERE NOT S use_email O, S eid 1, O is EmailAddress, O address AA, O alias AB, O modification_date AC, '
     'EXISTS(A use_email O, EXISTS(A identity B, NOT B in_group D, D name "guests", D is CWGroup), A is CWUser), B eid 2',
     '''SELECT _O.cw_eid, _O.cw_address, _O.cw_alias, _O.cw_modification_date
FROM cw_EmailAddress AS _O
WHERE NOT EXISTS(SELECT 1 FROM use_email_relation AS rel_use_email0 WHERE rel_use_email0.eid_from=1 AND rel_use_email0.eid_to=_O.cw_eid) AND EXISTS(SELECT 1 FROM use_email_relation AS rel_use_email1 WHERE rel_use_email1.eid_to=_O.cw_eid AND EXISTS(SELECT 1 FROM cw_CWGroup AS _D WHERE rel_use_email1.eid_from=2 AND NOT EXISTS(SELECT 1 FROM in_group_relation AS rel_in_group2 WHERE rel_in_group2.eid_from=2 AND rel_in_group2.eid_to=_D.cw_eid) AND _D.cw_name=guests))
ORDER BY 4 DESC'''),


    ("Any X WHERE X eid 0, X eid 0",
     '''SELECT 0'''),

    ("Any X WHERE X eid 0, X eid 0, X test TRUE",
     '''SELECT _X.cw_eid
FROM cw_Personne AS _X
WHERE _X.cw_eid=0 AND _X.cw_eid=0 AND _X.cw_test=TRUE'''),

    ("Any X,GROUP_CONCAT(TN) GROUPBY X ORDERBY XN WHERE T tags X, X name XN, T name TN, X is CWGroup",
     '''SELECT _X.cw_eid, GROUP_CONCAT(_T.cw_name)
FROM cw_CWGroup AS _X, cw_Tag AS _T, tags_relation AS rel_tags0
WHERE rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=_X.cw_eid
GROUP BY _X.cw_eid,_X.cw_name
ORDER BY _X.cw_name'''),

    ("Any X,GROUP_CONCAT(TN) GROUPBY X ORDERBY XN WHERE T tags X, X name XN, T name TN",
     '''SELECT T1.C0, GROUP_CONCAT(T1.C1) FROM (SELECT _X.cw_eid AS C0, _T.cw_name AS C1, _X.cw_name AS C2
FROM cw_CWGroup AS _X, cw_Tag AS _T, tags_relation AS rel_tags0
WHERE rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=_X.cw_eid
UNION ALL
SELECT _X.cw_eid AS C0, _T.cw_name AS C1, _X.cw_name AS C2
FROM cw_State AS _X, cw_Tag AS _T, tags_relation AS rel_tags0
WHERE rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=_X.cw_eid
UNION ALL
SELECT _X.cw_eid AS C0, _T.cw_name AS C1, _X.cw_name AS C2
FROM cw_Tag AS _T, cw_Tag AS _X, tags_relation AS rel_tags0
WHERE rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=_X.cw_eid) AS T1
GROUP BY T1.C0,T1.C2
ORDER BY T1.C2'''),

    ]

MULTIPLE_SEL = [
    ("DISTINCT Any X,Y where P is Personne, P nom X , P prenom Y;",
     '''SELECT DISTINCT _P.cw_nom, _P.cw_prenom
FROM cw_Personne AS _P'''),
    ("Any X,Y where P is Personne, P nom X , P prenom Y, not P nom NULL;",
     '''SELECT _P.cw_nom, _P.cw_prenom
FROM cw_Personne AS _P
WHERE NOT (_P.cw_nom IS NULL)'''),
    ("Personne X,Y where X nom NX, Y nom NX, X eid XE, not Y eid XE",
     '''SELECT _X.cw_eid, _Y.cw_eid
FROM cw_Personne AS _X, cw_Personne AS _Y
WHERE _Y.cw_nom=_X.cw_nom AND NOT (_Y.cw_eid=_X.cw_eid)''')
    ]

NEGATIONS = [
    ("Personne X WHERE NOT X evaluee Y;",
     '''SELECT _X.cw_eid
FROM cw_Personne AS _X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=_X.cw_eid)'''),

    ("Note N WHERE NOT X evaluee N, X eid 0",
     '''SELECT _N.cw_eid
FROM cw_Note AS _N
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=0 AND rel_evaluee0.eid_to=_N.cw_eid)'''),

    ('Any X WHERE NOT X travaille S, X is Personne',
     '''SELECT _X.cw_eid
FROM cw_Personne AS _X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=_X.cw_eid)'''),

    ("Personne P where not P datenaiss TODAY",
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P
WHERE NOT (DATE(_P.cw_datenaiss)=CURRENT_DATE)'''),

    ("Personne P where NOT P concerne A",
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_from=_P.cw_eid)'''),

    ("Affaire A where not P concerne A",
     '''SELECT _A.cw_eid
FROM cw_Affaire AS _A
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_to=_A.cw_eid)'''),
    ("Personne P where not P concerne A, A sujet ~= 'TEST%'",
     '''SELECT _P.cw_eid
FROM cw_Affaire AS _A, cw_Personne AS _P
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_from=_P.cw_eid AND rel_concerne0.eid_to=_A.cw_eid) AND _A.cw_sujet ILIKE TEST%'''),

    ('Any S WHERE NOT T eid 28258, T tags S',
     '''SELECT rel_tags0.eid_to
FROM tags_relation AS rel_tags0
WHERE NOT (rel_tags0.eid_from=28258)'''),

    ('Any S WHERE T is Tag, T name TN, NOT T eid 28258, T tags S, S name SN',
     '''SELECT _S.cw_eid
FROM cw_CWGroup AS _S, cw_Tag AS _T, tags_relation AS rel_tags0
WHERE NOT (_T.cw_eid=28258) AND rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=_S.cw_eid
UNION ALL
SELECT _S.cw_eid
FROM cw_State AS _S, cw_Tag AS _T, tags_relation AS rel_tags0
WHERE NOT (_T.cw_eid=28258) AND rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=_S.cw_eid
UNION ALL
SELECT _S.cw_eid
FROM cw_Tag AS _S, cw_Tag AS _T, tags_relation AS rel_tags0
WHERE NOT (_T.cw_eid=28258) AND rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=_S.cw_eid'''),

    ('Any X,Y WHERE X created_by Y, X eid 5, NOT Y eid 6',
     '''SELECT 5, rel_created_by0.eid_to
FROM created_by_relation AS rel_created_by0
WHERE rel_created_by0.eid_from=5 AND NOT (rel_created_by0.eid_to=6)'''),

    ('Note X WHERE NOT Y evaluee X',
     '''SELECT _X.cw_eid
FROM cw_Note AS _X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_to=_X.cw_eid)'''),

    ('Any Y WHERE NOT Y evaluee X',
     '''SELECT _Y.cw_eid
FROM cw_CWUser AS _Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=_Y.cw_eid)
UNION ALL
SELECT _Y.cw_eid
FROM cw_Division AS _Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=_Y.cw_eid)
UNION ALL
SELECT _Y.cw_eid
FROM cw_Personne AS _Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=_Y.cw_eid)
UNION ALL
SELECT _Y.cw_eid
FROM cw_Societe AS _Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=_Y.cw_eid)
UNION ALL
SELECT _Y.cw_eid
FROM cw_SubDivision AS _Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=_Y.cw_eid)'''),

    ('Any X WHERE NOT Y evaluee X, Y is CWUser',
     '''SELECT _X.cw_eid
FROM cw_Note AS _X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0,cw_CWUser AS _Y WHERE rel_evaluee0.eid_from=_Y.cw_eid AND rel_evaluee0.eid_to=_X.cw_eid)'''),

    ('Any X,RT WHERE X relation_type RT, NOT X is CWAttribute',
     '''SELECT _X.cw_eid, _X.cw_relation_type
FROM cw_CWRelation AS _X
WHERE _X.cw_relation_type IS NOT NULL'''),

    ('Any K,V WHERE P is CWProperty, P pkey K, P value V, NOT P for_user U',
     '''SELECT _P.cw_pkey, _P.cw_value
FROM cw_CWProperty AS _P
WHERE _P.cw_for_user IS NULL'''),

    ('Any S WHERE NOT X in_state S, X is IN(Affaire, CWUser)',
     '''SELECT _S.cw_eid
FROM cw_State AS _S
WHERE NOT EXISTS(SELECT 1 FROM cw_Affaire AS _X WHERE _X.cw_in_state=_S.cw_eid)
INTERSECT
SELECT _S.cw_eid
FROM cw_State AS _S
WHERE NOT EXISTS(SELECT 1 FROM cw_CWUser AS _X WHERE _X.cw_in_state=_S.cw_eid)'''),

    ('Any S WHERE NOT(X in_state S, S name "somename"), X is CWUser',
     '''SELECT _S.cw_eid
FROM cw_State AS _S
WHERE NOT EXISTS(SELECT 1 FROM cw_CWUser AS _X WHERE _X.cw_in_state=_S.cw_eid AND _S.cw_name=somename)'''),
   
# XXXFIXME fail
#         ('Any X,RT WHERE X relation_type RT?, NOT X is CWAttribute',
#      '''SELECT _X.cw_eid, _X.cw_relation_type
# FROM cw_CWRelation AS _X'''),
]

OUTER_JOIN = [
    ('Any X,S WHERE X travaille S?',
     '''SELECT _X.cw_eid, rel_travaille0.eid_to
FROM cw_Personne AS _X LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=_X.cw_eid)'''
    ),
    ('Any S,X WHERE X? travaille S, S is Societe',
     '''SELECT _S.cw_eid, rel_travaille0.eid_from
FROM cw_Societe AS _S LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_to=_S.cw_eid)'''
    ),

    ('Any N,A WHERE N inline1 A?',
     '''SELECT _N.cw_eid, _N.cw_inline1
FROM cw_Note AS _N'''),

    ('Any SN WHERE X from_state S?, S name SN',
     '''SELECT _S.cw_name
FROM cw_TrInfo AS _X LEFT OUTER JOIN cw_State AS _S ON (_X.cw_from_state=_S.cw_eid)'''
    ),

    ('Any A,N WHERE N? inline1 A',
     '''SELECT _A.cw_eid, _N.cw_eid
FROM cw_Affaire AS _A LEFT OUTER JOIN cw_Note AS _N ON (_N.cw_inline1=_A.cw_eid)'''
    ),

    ('Any A,B,C,D,E,F,G WHERE A eid 12,A creation_date B,A modification_date C,A comment D,A from_state E?,A to_state F?,A wf_info_for G?',
    '''SELECT _A.cw_eid, _A.cw_creation_date, _A.cw_modification_date, _A.cw_comment, _A.cw_from_state, _A.cw_to_state, _A.cw_wf_info_for
FROM cw_TrInfo AS _A
WHERE _A.cw_eid=12'''),

    ('Any FS,TS,C,D,U ORDERBY D DESC WHERE WF wf_info_for X,WF from_state FS?, WF to_state TS, WF comment C,WF creation_date D, WF owned_by U, X eid 1',
     '''SELECT _WF.cw_from_state, _WF.cw_to_state, _WF.cw_comment, _WF.cw_creation_date, rel_owned_by0.eid_to
FROM cw_TrInfo AS _WF, owned_by_relation AS rel_owned_by0
WHERE _WF.cw_wf_info_for=1 AND _WF.cw_to_state IS NOT NULL AND rel_owned_by0.eid_from=_WF.cw_eid
ORDER BY 4 DESC'''),

    ('Any X WHERE X is Affaire, S is Societe, EXISTS(X owned_by U OR (X concerne S?, S owned_by U))',
     '''SELECT _X.cw_eid
FROM cw_Affaire AS _X
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, cw_CWUser AS _U, cw_Affaire AS _A LEFT OUTER JOIN concerne_relation AS rel_concerne1 ON (rel_concerne1.eid_from=_A.cw_eid) LEFT OUTER JOIN cw_Societe AS _S ON (rel_concerne1.eid_to=_S.cw_eid), owned_by_relation AS rel_owned_by2 WHERE ((rel_owned_by0.eid_from=_A.cw_eid AND rel_owned_by0.eid_to=_U.cw_eid) OR (rel_owned_by2.eid_from=_S.cw_eid AND rel_owned_by2.eid_to=_U.cw_eid)) AND _X.cw_eid=_A.cw_eid)'''),

    ('Any C,M WHERE C travaille G?, G evaluee M?, G is Societe',
     '''SELECT _C.cw_eid, rel_evaluee1.eid_to
FROM cw_Personne AS _C LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=_C.cw_eid) LEFT OUTER JOIN cw_Societe AS _G ON (rel_travaille0.eid_to=_G.cw_eid) LEFT OUTER JOIN evaluee_relation AS rel_evaluee1 ON (rel_evaluee1.eid_from=_G.cw_eid)'''
     ),

    ('Any A,C WHERE A documented_by C?, (C is NULL) OR (EXISTS(C require_permission F, '
     'F name "read", F require_group E, U in_group E)), U eid 1',
     '''SELECT _A.cw_eid, rel_documented_by0.eid_to
FROM cw_Affaire AS _A LEFT OUTER JOIN documented_by_relation AS rel_documented_by0 ON (rel_documented_by0.eid_from=_A.cw_eid)
WHERE ((rel_documented_by0.eid_to IS NULL) OR (EXISTS(SELECT 1 FROM require_permission_relation AS rel_require_permission1, cw_CWPermission AS _F, require_group_relation AS rel_require_group2, in_group_relation AS rel_in_group3 WHERE rel_documented_by0.eid_to=rel_require_permission1.eid_from AND rel_require_permission1.eid_to=_F.cw_eid AND _F.cw_name=read AND rel_require_group2.eid_from=_F.cw_eid AND rel_in_group3.eid_to=rel_require_group2.eid_to AND rel_in_group3.eid_from=1)))'''),

    ("Any X WHERE X eid 12, P? connait X",
     '''SELECT _X.cw_eid
FROM cw_Personne AS _X LEFT OUTER JOIN connait_relation AS rel_connait0 ON (rel_connait0.eid_to=12)
WHERE _X.cw_eid=12'''
    ),

    ('Any GN, TN ORDERBY GN WHERE T tags G?, T name TN, G name GN',
    '''
SELECT _T0.C1, _T.cw_name
FROM cw_Tag AS _T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=_T.cw_eid) LEFT OUTER JOIN (SELECT _G.cw_eid AS C0, _G.cw_name AS C1
FROM cw_CWGroup AS _G
UNION ALL
SELECT _G.cw_eid AS C0, _G.cw_name AS C1
FROM cw_State AS _G
UNION ALL
SELECT _G.cw_eid AS C0, _G.cw_name AS C1
FROM cw_Tag AS _G) AS _T0 ON (rel_tags0.eid_to=_T0.C0)
ORDER BY 1'''),


    # optional variable with additional restriction
    ('Any T,G WHERE T tags G?, G name "hop", G is CWGroup',
     '''SELECT _T.cw_eid, _G.cw_eid
FROM cw_Tag AS _T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=_T.cw_eid) LEFT OUTER JOIN cw_CWGroup AS _G ON (rel_tags0.eid_to=_G.cw_eid AND _G.cw_name=hop)'''),

    # optional variable with additional invariant restriction
    ('Any T,G WHERE T tags G?, G eid 12',
     '''SELECT _T.cw_eid, rel_tags0.eid_to
FROM cw_Tag AS _T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=_T.cw_eid AND rel_tags0.eid_to=12)'''),

    # optional variable with additional restriction appearing before the relation
    ('Any T,G WHERE G name "hop", T tags G?, G is CWGroup',
     '''SELECT _T.cw_eid, _G.cw_eid
FROM cw_Tag AS _T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=_T.cw_eid) LEFT OUTER JOIN cw_CWGroup AS _G ON (rel_tags0.eid_to=_G.cw_eid AND _G.cw_name=hop)'''),

    # optional variable with additional restriction on inlined relation
    # XXX the expected result should be as the query below. So what, raise BadRQLQuery ?
    ('Any T,G,S WHERE T tags G?, G in_state S, S name "hop", G is CWUser',
     '''SELECT _T.cw_eid, _G.cw_eid, _S.cw_eid
FROM cw_State AS _S, cw_Tag AS _T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=_T.cw_eid) LEFT OUTER JOIN cw_CWUser AS _G ON (rel_tags0.eid_to=_G.cw_eid)
WHERE _G.cw_in_state=_S.cw_eid AND _S.cw_name=hop
'''),

    # optional variable with additional invariant restriction on an inlined relation
    ('Any T,G,S WHERE T tags G, G in_state S?, S eid 1, G is CWUser',
     '''SELECT rel_tags0.eid_from, _G.cw_eid, _G.cw_in_state
FROM cw_CWUser AS _G, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=_G.cw_eid AND (_G.cw_in_state=1 OR _G.cw_in_state IS NULL)'''),

    # two optional variables with additional invariant restriction on an inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S eid 1, G is CWUser',
     '''SELECT _T.cw_eid, _G.cw_eid, _G.cw_in_state
FROM cw_Tag AS _T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=_T.cw_eid) LEFT OUTER JOIN cw_CWUser AS _G ON (rel_tags0.eid_to=_G.cw_eid AND (_G.cw_in_state=1 OR _G.cw_in_state IS NULL))'''),

    # two optional variables with additional restriction on an inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S name "hop", G is CWUser',
     '''SELECT _T.cw_eid, _G.cw_eid, _S.cw_eid
FROM cw_Tag AS _T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=_T.cw_eid) LEFT OUTER JOIN cw_CWUser AS _G ON (rel_tags0.eid_to=_G.cw_eid) LEFT OUTER JOIN cw_State AS _S ON (_G.cw_in_state=_S.cw_eid AND _S.cw_name=hop)'''),

    # two optional variables with additional restriction on an ambigous inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S name "hop"',
     '''
SELECT _T.cw_eid, _T0.C0, _T0.C1
FROM cw_Tag AS _T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=_T.cw_eid) LEFT OUTER JOIN (SELECT _G.cw_eid AS C0, _S.cw_eid AS C1
FROM cw_Affaire AS _G LEFT OUTER JOIN cw_State AS _S ON (_G.cw_in_state=_S.cw_eid AND _S.cw_name=hop)
UNION ALL
SELECT _G.cw_eid AS C0, _S.cw_eid AS C1
FROM cw_CWUser AS _G LEFT OUTER JOIN cw_State AS _S ON (_G.cw_in_state=_S.cw_eid AND _S.cw_name=hop)
UNION ALL
SELECT _G.cw_eid AS C0, _S.cw_eid AS C1
FROM cw_Note AS _G LEFT OUTER JOIN cw_State AS _S ON (_G.cw_in_state=_S.cw_eid AND _S.cw_name=hop) ) AS _T0 ON (rel_tags0.eid_to=_T0.C0)'''),

    ('Any O,AD  WHERE NOT S inline1 O, S eid 123, O todo_by AD?',
     '''SELECT _O.cw_eid, rel_todo_by0.eid_to
FROM cw_Affaire AS _O LEFT OUTER JOIN todo_by_relation AS rel_todo_by0 ON (rel_todo_by0.eid_from=_O.cw_eid), cw_Note AS _S
WHERE NOT EXISTS(SELECT 1 WHERE _S.cw_inline1=_O.cw_eid) AND _S.cw_eid=123''')
    ]

VIRTUAL_VARS = [

    ('Any X WHERE X is CWUser, X creation_date > D1, Y creation_date D1, Y login "SWEB09"',
     '''SELECT _X.cw_eid
FROM cw_CWUser AS _X, cw_CWUser AS _Y
WHERE _X.cw_creation_date>_Y.cw_creation_date AND _Y.cw_login=SWEB09'''),

    ('Any X WHERE X is CWUser, Y creation_date D1, Y login "SWEB09", X creation_date > D1',
     '''SELECT _X.cw_eid
FROM cw_CWUser AS _X, cw_CWUser AS _Y
WHERE _Y.cw_login=SWEB09 AND _X.cw_creation_date>_Y.cw_creation_date'''),

    ('Personne P WHERE P travaille S, S tel T, S fax T, S is Societe',
     '''SELECT rel_travaille0.eid_from
FROM cw_Societe AS _S, travaille_relation AS rel_travaille0
WHERE rel_travaille0.eid_to=_S.cw_eid AND _S.cw_tel=_S.cw_fax'''),

    ("Personne P where X eid 0, X creation_date D, P datenaiss < D, X is Affaire",
     '''SELECT _P.cw_eid
FROM cw_Affaire AS _X, cw_Personne AS _P
WHERE _X.cw_eid=0 AND _P.cw_datenaiss<_X.cw_creation_date'''),

    ("Any N,T WHERE N is Note, N type T;",
     '''SELECT _N.cw_eid, _N.cw_type
FROM cw_Note AS _N'''),

    ("Personne P where X is Personne, X tel T, X fax F, P fax T+F",
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P, cw_Personne AS _X
WHERE _P.cw_fax=(_X.cw_tel + _X.cw_fax)'''),

    ("Personne P where X tel T, X fax F, P fax IN (T,F)",
     '''SELECT _P.cw_eid
FROM cw_Division AS _X, cw_Personne AS _P
WHERE _P.cw_fax IN(_X.cw_tel, _X.cw_fax)
UNION ALL
SELECT _P.cw_eid
FROM cw_Personne AS _P, cw_Personne AS _X
WHERE _P.cw_fax IN(_X.cw_tel, _X.cw_fax)
UNION ALL
SELECT _P.cw_eid
FROM cw_Personne AS _P, cw_Societe AS _X
WHERE _P.cw_fax IN(_X.cw_tel, _X.cw_fax)
UNION ALL
SELECT _P.cw_eid
FROM cw_Personne AS _P, cw_SubDivision AS _X
WHERE _P.cw_fax IN(_X.cw_tel, _X.cw_fax)'''),

    ("Personne P where X tel T, X fax F, P fax IN (T,F,0832542332)",
     '''SELECT _P.cw_eid
FROM cw_Division AS _X, cw_Personne AS _P
WHERE _P.cw_fax IN(_X.cw_tel, _X.cw_fax, 832542332)
UNION ALL
SELECT _P.cw_eid
FROM cw_Personne AS _P, cw_Personne AS _X
WHERE _P.cw_fax IN(_X.cw_tel, _X.cw_fax, 832542332)
UNION ALL
SELECT _P.cw_eid
FROM cw_Personne AS _P, cw_Societe AS _X
WHERE _P.cw_fax IN(_X.cw_tel, _X.cw_fax, 832542332)
UNION ALL
SELECT _P.cw_eid
FROM cw_Personne AS _P, cw_SubDivision AS _X
WHERE _P.cw_fax IN(_X.cw_tel, _X.cw_fax, 832542332)'''),
    ]

FUNCS = [
    ("Any COUNT(P) WHERE P is Personne",
     '''SELECT COUNT(_P.cw_eid)
FROM cw_Personne AS _P'''),
    ]

SYMETRIC = [
    ('Any P WHERE X eid 0, X connait P',
     '''SELECT DISTINCT _P.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS _P
WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=_P.cw_eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=_P.cw_eid)'''
     ),

    ('Any P WHERE X connait P',
    '''SELECT DISTINCT _P.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS _P
WHERE (rel_connait0.eid_to=_P.cw_eid OR rel_connait0.eid_from=_P.cw_eid)'''
    ),

    ('Any X WHERE X connait P',
    '''SELECT DISTINCT _X.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS _X
WHERE (rel_connait0.eid_from=_X.cw_eid OR rel_connait0.eid_to=_X.cw_eid)'''
     ),

    ('Any P WHERE X eid 0, NOT X connait P',
     '''SELECT _P.cw_eid
FROM cw_Personne AS _P
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=_P.cw_eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=_P.cw_eid))'''),

    ('Any P WHERE NOT X connait P',
    '''SELECT _P.cw_eid
FROM cw_Personne AS _P
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_to=_P.cw_eid OR rel_connait0.eid_from=_P.cw_eid))'''),

    ('Any X WHERE NOT X connait P',
    '''SELECT _X.cw_eid
FROM cw_Personne AS _X
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_from=_X.cw_eid OR rel_connait0.eid_to=_X.cw_eid))'''),

    ('Any P WHERE X connait P, P nom "nom"',
     '''SELECT DISTINCT _P.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS _P
WHERE (rel_connait0.eid_to=_P.cw_eid OR rel_connait0.eid_from=_P.cw_eid) AND _P.cw_nom=nom'''),

    ('Any X WHERE X connait P, P nom "nom"',
     '''SELECT DISTINCT _X.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS _P, cw_Personne AS _X
WHERE (rel_connait0.eid_from=_X.cw_eid AND rel_connait0.eid_to=_P.cw_eid OR rel_connait0.eid_to=_X.cw_eid AND rel_connait0.eid_from=_P.cw_eid) AND _P.cw_nom=nom'''
    ),

    ('Any X ORDERBY X DESC LIMIT 9 WHERE E eid 0, E connait X',
    '''SELECT DISTINCT _X.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS _X
WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=_X.cw_eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=_X.cw_eid)
ORDER BY 1 DESC
LIMIT 9'''
     ),

    ('DISTINCT Any P WHERE P connait S OR S connait P, S nom "chouette"',
     '''SELECT DISTINCT _P.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS _P, cw_Personne AS _S
WHERE (rel_connait0.eid_from=_P.cw_eid AND rel_connait0.eid_to=_S.cw_eid OR rel_connait0.eid_to=_P.cw_eid AND rel_connait0.eid_from=_S.cw_eid) AND _S.cw_nom=chouette'''
     )
    ]

INLINE = [
    ('Any P, L WHERE N ecrit_par P, P nom L, N eid 0',
     '''SELECT _P.cw_eid, _P.cw_nom
FROM cw_Note AS _N, cw_Personne AS _P
WHERE _N.cw_ecrit_par=_P.cw_eid AND _N.cw_eid=0'''),

    ('Any N WHERE NOT N ecrit_par P, P nom "toto"',
     '''SELECT _N.cw_eid
FROM cw_Note AS _N, cw_Personne AS _P
WHERE NOT EXISTS(SELECT 1 WHERE _N.cw_ecrit_par=_P.cw_eid) AND _P.cw_nom=toto'''),

    ('Any P WHERE N ecrit_par P, N eid 0',
    '''SELECT _N.cw_ecrit_par
FROM cw_Note AS _N
WHERE _N.cw_ecrit_par IS NOT NULL AND _N.cw_eid=0'''),

    ('Any P WHERE N ecrit_par P, P is Personne, N eid 0',
    '''SELECT _P.cw_eid
FROM cw_Note AS _N, cw_Personne AS _P
WHERE _N.cw_ecrit_par=_P.cw_eid AND _N.cw_eid=0'''),

    ('Any P WHERE NOT N ecrit_par P, P is Personne, N eid 512',
     '''SELECT _P.cw_eid
FROM cw_Note AS _N, cw_Personne AS _P
WHERE NOT EXISTS(SELECT 1 WHERE _N.cw_ecrit_par=_P.cw_eid) AND _N.cw_eid=512'''),

    ('Any S,ES,T WHERE S state_of ET, ET name "CWUser", ES allowed_transition T, T destination_state S',
     '''SELECT _T.cw_destination_state, rel_allowed_transition1.eid_from, _T.cw_eid
FROM allowed_transition_relation AS rel_allowed_transition1, cw_Transition AS _T, cw_Workflow AS _ET, state_of_relation AS rel_state_of0
WHERE _T.cw_destination_state=rel_state_of0.eid_from AND rel_state_of0.eid_to=_ET.cw_eid AND _ET.cw_name=CWUser AND rel_allowed_transition1.eid_to=_T.cw_eid'''),

    ('Any O WHERE S eid 0, S in_state O',
     '''SELECT _S.cw_in_state
FROM cw_Affaire AS _S
WHERE _S.cw_eid=0 AND _S.cw_in_state IS NOT NULL
UNION ALL
SELECT _S.cw_in_state
FROM cw_CWUser AS _S
WHERE _S.cw_eid=0 AND _S.cw_in_state IS NOT NULL
UNION ALL
SELECT _S.cw_in_state
FROM cw_Note AS _S
WHERE _S.cw_eid=0 AND _S.cw_in_state IS NOT NULL'''),

    ('Any X WHERE NOT Y for_user X, X eid 123',
     '''SELECT 123
WHERE NOT EXISTS(SELECT 1 FROM cw_CWProperty AS _Y WHERE _Y.cw_for_user=123)
'''),

    ]

INTERSECT = [
    ('Any SN WHERE NOT X in_state S, S name SN',
     '''SELECT _S.cw_name
FROM cw_State AS _S
WHERE NOT EXISTS(SELECT 1 FROM cw_Affaire AS _X WHERE _X.cw_in_state=_S.cw_eid)
INTERSECT
SELECT _S.cw_name
FROM cw_State AS _S
WHERE NOT EXISTS(SELECT 1 FROM cw_CWUser AS _X WHERE _X.cw_in_state=_S.cw_eid)
INTERSECT
SELECT _S.cw_name
FROM cw_State AS _S
WHERE NOT EXISTS(SELECT 1 FROM cw_Note AS _X WHERE _X.cw_in_state=_S.cw_eid)'''),

    ('Any PN WHERE NOT X travaille S, X nom PN, S is IN(Division, Societe)',
     '''SELECT _X.cw_nom
FROM cw_Personne AS _X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0,cw_Division AS _S WHERE rel_travaille0.eid_from=_X.cw_eid AND rel_travaille0.eid_to=_S.cw_eid)
INTERSECT
SELECT _X.cw_nom
FROM cw_Personne AS _X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0,cw_Societe AS _S WHERE rel_travaille0.eid_from=_X.cw_eid AND rel_travaille0.eid_to=_S.cw_eid)'''),

    ('Any PN WHERE NOT X travaille S, S nom PN, S is IN(Division, Societe)',
     '''SELECT _S.cw_nom
FROM cw_Division AS _S
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_to=_S.cw_eid)
UNION ALL
SELECT _S.cw_nom
FROM cw_Societe AS _S
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_to=_S.cw_eid)'''),

    ('Personne X WHERE NOT X travaille S, S nom "chouette"',
     '''SELECT _X.cw_eid
FROM cw_Division AS _S, cw_Personne AS _X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=_X.cw_eid AND rel_travaille0.eid_to=_S.cw_eid) AND _S.cw_nom=chouette
UNION ALL
SELECT _X.cw_eid
FROM cw_Personne AS _X, cw_Societe AS _S
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=_X.cw_eid AND rel_travaille0.eid_to=_S.cw_eid) AND _S.cw_nom=chouette
UNION ALL
SELECT _X.cw_eid
FROM cw_Personne AS _X, cw_SubDivision AS _S
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=_X.cw_eid AND rel_travaille0.eid_to=_S.cw_eid) AND _S.cw_nom=chouette'''),

    ('Any X WHERE X is ET, ET eid 2',
     '''SELECT rel_is0.eid_from
FROM is_relation AS rel_is0
WHERE rel_is0.eid_to=2'''),

    ]
from logilab.common.adbh import ADV_FUNC_HELPER_DIRECTORY

class CWRQLTC(RQLGeneratorTC):
    schema = schema

    def test_nonregr_sol(self):
        delete = self.rqlhelper.parse(
            'DELETE X read_permission READ_PERMISSIONSUBJECT,X add_permission ADD_PERMISSIONSUBJECT,'
            'X in_basket IN_BASKETSUBJECT,X delete_permission DELETE_PERMISSIONSUBJECT,'
            'X update_permission UPDATE_PERMISSIONSUBJECT,'
            'X created_by CREATED_BYSUBJECT,X is ISSUBJECT,X is_instance_of IS_INSTANCE_OFSUBJECT,'
            'X owned_by OWNED_BYSUBJECT,X specializes SPECIALIZESSUBJECT,ISOBJECT is X,'
            'SPECIALIZESOBJECT specializes X,IS_INSTANCE_OFOBJECT is_instance_of X,'
            'TO_ENTITYOBJECT to_entity X,FROM_ENTITYOBJECT from_entity X '
            'WHERE X is CWEType')
        self.rqlhelper.compute_solutions(delete)
        def var_sols(var):
            s = set()
            for sol in delete.solutions:
                s.add(sol.get(var))
            return s
        self.assertEquals(var_sols('FROM_ENTITYOBJECT'), set(('CWAttribute', 'CWRelation')))
        self.assertEquals(var_sols('FROM_ENTITYOBJECT'), delete.defined_vars['FROM_ENTITYOBJECT'].stinfo['possibletypes'])
        self.assertEquals(var_sols('ISOBJECT'),
                          set(x.type for x in self.schema.entities() if not x.final))
        self.assertEquals(var_sols('ISOBJECT'), delete.defined_vars['ISOBJECT'].stinfo['possibletypes'])


class PostgresSQLGeneratorTC(RQLGeneratorTC):
    schema = schema

    #capture = True
    def setUp(self):
        RQLGeneratorTC.setUp(self)
        indexer = get_indexer('postgres', 'utf8')
        dbms_helper = ADV_FUNC_HELPER_DIRECTORY['postgres']
        dbms_helper.fti_uid_attr = indexer.uid_attr
        dbms_helper.fti_table = indexer.table
        dbms_helper.fti_restriction_sql = indexer.restriction_sql
        dbms_helper.fti_need_distinct_query = indexer.need_distinct
        self.o = SQLGenerator(schema, dbms_helper)

    def _norm_sql(self, sql):
        return sql.strip()

    def _check(self, rql, sql, varmap=None, args=None):
        if args is None:
            args = {'text': 'hip hop momo'}
        try:
            union = self._prepare(rql)
            r, nargs = self.o.generate(union, args,
                                      varmap=varmap)
            args.update(nargs)
            self.assertLinesEquals((r % args).strip(), self._norm_sql(sql), striplines=True)
        except Exception, ex:
            if 'r' in locals():
                try:
                    print (r%args).strip()
                except KeyError:
                    print 'strange, missing substitution'
                    print r, nargs
                print '!='
                print sql.strip()
            raise

    def _parse(self, rqls):
        for rql, sql in rqls:
            yield self._check, rql, sql

    def _checkall(self, rql, sql):
        try:
            rqlst = self._prepare(rql)
            r, args = self.o.generate(rqlst)
            self.assertEqual((r.strip(), args), sql)
        except Exception, ex:
            print rql
            if 'r' in locals():
                print r.strip()
                print '!='
                print sql[0].strip()
            raise
        return

    def test1(self):
        self._checkall('Any count(RDEF) WHERE RDEF relation_type X, X eid %(x)s',
                       ("""SELECT COUNT(T1.C0) FROM (SELECT _RDEF.cw_eid AS C0
FROM cw_CWAttribute AS _RDEF
WHERE _RDEF.cw_relation_type=%(x)s
UNION ALL
SELECT _RDEF.cw_eid AS C0
FROM cw_CWRelation AS _RDEF
WHERE _RDEF.cw_relation_type=%(x)s) AS T1""", {}),
                       )

    def test2(self):
        self._checkall('Any X WHERE C comments X, C eid %(x)s',
                       ('''SELECT rel_comments0.eid_to
FROM comments_relation AS rel_comments0
WHERE rel_comments0.eid_from=%(x)s''', {})
                       )

    def test_cache_1(self):
        self._check('Any X WHERE X in_basket B, B eid 12',
                    '''SELECT rel_in_basket0.eid_from
FROM in_basket_relation AS rel_in_basket0
WHERE rel_in_basket0.eid_to=12''')

        self._check('Any X WHERE X in_basket B, B eid 12',
                    '''SELECT rel_in_basket0.eid_from
FROM in_basket_relation AS rel_in_basket0
WHERE rel_in_basket0.eid_to=12''')

    def test_varmap1(self):
        self._check('Any X,L WHERE X is CWUser, X in_group G, X login L, G name "users"',
                    '''SELECT T00.x, T00.l
FROM T00, cw_CWGroup AS _G, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=T00.x AND rel_in_group0.eid_to=_G.cw_eid AND _G.cw_name=users''',
                    varmap={'X': 'T00.x', 'X.login': 'T00.l'})

    def test_varmap2(self):
        self._check('Any X,L,GN WHERE X is CWUser, X in_group G, X login L, G name GN',
                    '''SELECT T00.x, T00.l, _G.cw_name
FROM T00, cw_CWGroup AS _G, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=T00.x AND rel_in_group0.eid_to=_G.cw_eid''',
                    varmap={'X': 'T00.x', 'X.login': 'T00.l'})

    def test_varmap3(self):
        self._check('Any %(x)s,D WHERE F data D, F is File',
                    'SELECT 728, _TDF0.C0\nFROM _TDF0',
                    args={'x': 728},
                    varmap={'F.data': '_TDF0.C0', 'D': '_TDF0.C0'})

    def test_is_null_transform(self):
        union = self._prepare('Any X WHERE X login %(login)s')
        r, args = self.o.generate(union, {'login': None})
        self.assertLinesEquals((r % args).strip(),
                               '''SELECT _X.cw_eid
FROM cw_CWUser AS _X
WHERE _X.cw_login IS NULL''')

    def test_parser_parse(self):
        for t in self._parse(PARSER):
            yield t

    def test_basic_parse(self):
        for t in self._parse(BASIC):
            yield t

    def test_advanced_parse(self):
        for t in self._parse(ADVANCED):
            yield t

    def test_outer_join_parse(self):
        for t in self._parse(OUTER_JOIN):
            yield t

    def test_virtual_vars_parse(self):
        for t in self._parse(VIRTUAL_VARS):
            yield t

    def test_multiple_sel_parse(self):
        for t in self._parse(MULTIPLE_SEL):
            yield t

    def test_functions(self):
        for t in self._parse(FUNCS):
            yield t

    def test_negation(self):
        for t in self._parse(NEGATIONS):
            yield t

    def test_intersection(self):
        for t in self._parse(INTERSECT):
            yield t

    def test_union(self):
        for t in self._parse((
            ('(Any N ORDERBY 1 WHERE X name N, X is State)'
             ' UNION '
             '(Any NN ORDERBY 1 WHERE XX name NN, XX is Transition)',
             '''(SELECT _X.cw_name
FROM cw_State AS _X
ORDER BY 1)
UNION ALL
(SELECT _XX.cw_name
FROM cw_Transition AS _XX
ORDER BY 1)'''),
            )):
            yield t

    def test_subquery(self):
        for t in self._parse((

            ('Any N ORDERBY 1 WITH N BEING '
             '((Any N WHERE X name N, X is State)'
             ' UNION '
             '(Any NN WHERE XX name NN, XX is Transition))',
             '''SELECT _T0.C0
FROM ((SELECT _X.cw_name AS C0
FROM cw_State AS _X)
UNION ALL
(SELECT _XX.cw_name AS C0
FROM cw_Transition AS _XX)) AS _T0
ORDER BY 1'''),

            ('Any N,NX ORDERBY NX WITH N,NX BEING '
             '((Any N,COUNT(X) GROUPBY N WHERE X name N, X is State HAVING COUNT(X)>1)'
             ' UNION '
             '(Any N,COUNT(X) GROUPBY N WHERE X name N, X is Transition HAVING COUNT(X)>1))',
             '''SELECT _T0.C0, _T0.C1
FROM ((SELECT _X.cw_name AS C0, COUNT(_X.cw_eid) AS C1
FROM cw_State AS _X
GROUP BY _X.cw_name
HAVING COUNT(_X.cw_eid)>1)
UNION ALL
(SELECT _X.cw_name AS C0, COUNT(_X.cw_eid) AS C1
FROM cw_Transition AS _X
GROUP BY _X.cw_name
HAVING COUNT(_X.cw_eid)>1)) AS _T0
ORDER BY 2'''),

            ('Any N,COUNT(X) GROUPBY N HAVING COUNT(X)>1 '
             'WITH X, N BEING ((Any X, N WHERE X name N, X is State) UNION '
             '                 (Any X, N WHERE X name N, X is Transition))',
             '''SELECT _T0.C1, COUNT(_T0.C0)
FROM ((SELECT _X.cw_eid AS C0, _X.cw_name AS C1
FROM cw_State AS _X)
UNION ALL
(SELECT _X.cw_eid AS C0, _X.cw_name AS C1
FROM cw_Transition AS _X)) AS _T0
GROUP BY _T0.C1
HAVING COUNT(_T0.C0)>1'''),

            ('Any ETN,COUNT(X) GROUPBY ETN WHERE X is ET, ET name ETN '
             'WITH X BEING ((Any X WHERE X is Societe) UNION (Any X WHERE X is Affaire, (EXISTS(X owned_by 1)) OR ((EXISTS(D concerne B?, B owned_by 1, X identity D, B is Note)) OR (EXISTS(F concerne E?, E owned_by 1, E is Societe, X identity F)))))',
             '''SELECT _ET.cw_name, COUNT(_T0.C0)
FROM ((SELECT _X.cw_eid AS C0
FROM cw_Societe AS _X)
UNION ALL
(SELECT _X.cw_eid AS C0
FROM cw_Affaire AS _X
WHERE ((EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE rel_owned_by0.eid_from=_X.cw_eid AND rel_owned_by0.eid_to=1)) OR (((EXISTS(SELECT 1 FROM cw_Affaire AS _D LEFT OUTER JOIN concerne_relation AS rel_concerne1 ON (rel_concerne1.eid_from=_D.cw_eid) LEFT OUTER JOIN cw_Note AS _B ON (rel_concerne1.eid_to=_B.cw_eid), owned_by_relation AS rel_owned_by2 WHERE rel_owned_by2.eid_from=_B.cw_eid AND rel_owned_by2.eid_to=1 AND _X.cw_eid=_D.cw_eid)) OR (EXISTS(SELECT 1 FROM cw_Affaire AS _F LEFT OUTER JOIN concerne_relation AS rel_concerne3 ON (rel_concerne3.eid_from=_F.cw_eid) LEFT OUTER JOIN cw_Societe AS _E ON (rel_concerne3.eid_to=_E.cw_eid), owned_by_relation AS rel_owned_by4 WHERE rel_owned_by4.eid_from=_E.cw_eid AND rel_owned_by4.eid_to=1 AND _X.cw_eid=_F.cw_eid))))))) AS _T0, cw_CWEType AS _ET, is_relation AS rel_is0
WHERE rel_is0.eid_from=_T0.C0 AND rel_is0.eid_to=_ET.cw_eid
GROUP BY _ET.cw_name'''),
            )):
            yield t


    def test_subquery_error(self):
        rql = ('Any N WHERE X name N WITH X BEING '
               '((Any X WHERE X is State)'
               ' UNION '
               ' (Any X WHERE X is Transition))')
        rqlst = self._prepare(rql)
        self.assertRaises(BadRQLQuery, self.o.generate, rqlst)

    def test_symmetric(self):
        for t in self._parse(SYMETRIC):
            yield t

    def test_inline(self):
        for t in self._parse(INLINE):
            yield t

    def test_has_text(self):
        for t in self._parse((
            ('Any X WHERE X has_text "toto tata"',
             """SELECT appears0.uid
FROM appears AS appears0
WHERE appears0.words @@ to_tsquery('default', 'toto&tata')"""),

            ('Personne X WHERE X has_text "toto tata"',
             """SELECT _X.eid
FROM appears AS appears0, entities AS _X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=_X.eid AND _X.type='Personne'"""),

            ('Personne X WHERE X has_text %(text)s',
             """SELECT _X.eid
FROM appears AS appears0, entities AS _X
WHERE appears0.words @@ to_tsquery('default', 'hip&hop&momo') AND appears0.uid=_X.eid AND _X.type='Personne'"""),

            ('Any X WHERE X has_text "toto tata", X name "tutu", X is IN (Basket,Folder)',
             """SELECT _X.cw_eid
FROM appears AS appears0, cw_Basket AS _X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=_X.cw_eid AND _X.cw_name=tutu
UNION ALL
SELECT _X.cw_eid
FROM appears AS appears0, cw_Folder AS _X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=_X.cw_eid AND _X.cw_name=tutu
"""),

            ('Personne X where X has_text %(text)s, X travaille S, S has_text %(text)s',
             """SELECT _X.eid
FROM appears AS appears0, appears AS appears2, entities AS _X, travaille_relation AS rel_travaille1
WHERE appears0.words @@ to_tsquery('default', 'hip&hop&momo') AND appears0.uid=_X.eid AND _X.type='Personne' AND _X.eid=rel_travaille1.eid_from AND appears2.uid=rel_travaille1.eid_to AND appears2.words @@ to_tsquery('default', 'hip&hop&momo')"""),
            )):
            yield t


    def test_from_clause_needed(self):
        queries = [("Any 1 WHERE EXISTS(T is CWGroup, T name 'managers')",
                    '''SELECT 1
WHERE EXISTS(SELECT 1 FROM cw_CWGroup AS _T WHERE _T.cw_name=managers)'''),
                   ('Any X,Y WHERE NOT X created_by Y, X eid 5, Y eid 6',
                    '''SELECT 5, 6
WHERE NOT EXISTS(SELECT 1 FROM created_by_relation AS rel_created_by0 WHERE rel_created_by0.eid_from=5 AND rel_created_by0.eid_to=6)'''),
                   ]
        for t in self._parse(queries):
            yield t

    def test_ambigous_exists_no_from_clause(self):
        self._check('Any COUNT(U) WHERE U eid 1, EXISTS (P owned_by U, P is IN (Note, Affaire))',
                    '''SELECT COUNT(1)
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, cw_Affaire AS _P WHERE rel_owned_by0.eid_from=_P.cw_eid AND rel_owned_by0.eid_to=1 UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, cw_Note AS _P WHERE rel_owned_by1.eid_from=_P.cw_eid AND rel_owned_by1.eid_to=1)''')

    def test_attr_map(self):
        def generate_ref(gen, linkedvar, rel):
            linkedvar.accept(gen)
            return 'VERSION_DATA(%s)' % linkedvar._q_sql
        self.o.attr_map['Affaire.ref'] = generate_ref
        try:
            self._check('Any R WHERE X ref R',
                        '''SELECT VERSION_DATA(_X.cw_eid)
FROM cw_Affaire AS _X''')
            self._check('Any X WHERE X ref 1',
                        '''SELECT _X.cw_eid
FROM cw_Affaire AS _X
WHERE VERSION_DATA(_X.cw_eid)=1''')
        finally:
            self.o.attr_map.clear()


class SqliteSQLGeneratorTC(PostgresSQLGeneratorTC):

    def setUp(self):
        RQLGeneratorTC.setUp(self)
        indexer = get_indexer('sqlite', 'utf8')
        dbms_helper = ADV_FUNC_HELPER_DIRECTORY['sqlite']
        dbms_helper.fti_uid_attr = indexer.uid_attr
        dbms_helper.fti_table = indexer.table
        dbms_helper.fti_restriction_sql = indexer.restriction_sql
        dbms_helper.fti_need_distinct_query = indexer.need_distinct
        self.o = SQLGenerator(schema, dbms_helper)

    def _norm_sql(self, sql):
        return sql.strip().replace(' ILIKE ', ' LIKE ').replace('\nINTERSECT ALL\n', '\nINTERSECT\n')

    def test_union(self):
        for t in self._parse((
            ('(Any N ORDERBY 1 WHERE X name N, X is State)'
             ' UNION '
             '(Any NN ORDERBY 1 WHERE XX name NN, XX is Transition)',
             '''SELECT _X.cw_name
FROM cw_State AS _X
ORDER BY 1
UNION ALL
SELECT _XX.cw_name
FROM cw_Transition AS _XX
ORDER BY 1'''),
            )):
            yield t


    def test_subquery(self):
        # NOTE: no paren around UNION with sqlitebackend
        for t in self._parse((

            ('Any N ORDERBY 1 WITH N BEING '
             '((Any N WHERE X name N, X is State)'
             ' UNION '
             '(Any NN WHERE XX name NN, XX is Transition))',
             '''SELECT _T0.C0
FROM (SELECT _X.cw_name AS C0
FROM cw_State AS _X
UNION ALL
SELECT _XX.cw_name AS C0
FROM cw_Transition AS _XX) AS _T0
ORDER BY 1'''),

            ('Any N,NX ORDERBY NX WITH N,NX BEING '
             '((Any N,COUNT(X) GROUPBY N WHERE X name N, X is State HAVING COUNT(X)>1)'
             ' UNION '
             '(Any N,COUNT(X) GROUPBY N WHERE X name N, X is Transition HAVING COUNT(X)>1))',
             '''SELECT _T0.C0, _T0.C1
FROM (SELECT _X.cw_name AS C0, COUNT(_X.cw_eid) AS C1
FROM cw_State AS _X
GROUP BY _X.cw_name
HAVING COUNT(_X.cw_eid)>1
UNION ALL
SELECT _X.cw_name AS C0, COUNT(_X.cw_eid) AS C1
FROM cw_Transition AS _X
GROUP BY _X.cw_name
HAVING COUNT(_X.cw_eid)>1) AS _T0
ORDER BY 2'''),

            ('Any N,COUNT(X) GROUPBY N HAVING COUNT(X)>1 '
             'WITH X, N BEING ((Any X, N WHERE X name N, X is State) UNION '
             '                 (Any X, N WHERE X name N, X is Transition))',
             '''SELECT _T0.C1, COUNT(_T0.C0)
FROM (SELECT _X.cw_eid AS C0, _X.cw_name AS C1
FROM cw_State AS _X
UNION ALL
SELECT _X.cw_eid AS C0, _X.cw_name AS C1
FROM cw_Transition AS _X) AS _T0
GROUP BY _T0.C1
HAVING COUNT(_T0.C0)>1'''),
            )):
            yield t

    def test_has_text(self):
        for t in self._parse((
            ('Any X WHERE X has_text "toto tata"',
             """SELECT DISTINCT appears0.uid
FROM appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata'))"""),

            ('Any X WHERE X has_text %(text)s',
             """SELECT DISTINCT appears0.uid
FROM appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('hip', 'hop', 'momo'))"""),

            ('Personne X WHERE X has_text "toto tata"',
             """SELECT DISTINCT _X.eid
FROM appears AS appears0, entities AS _X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=_X.eid AND _X.type='Personne'"""),

            ('Any X WHERE X has_text "toto tata", X name "tutu", X is IN (Basket,Folder)',
             """SELECT DISTINCT _X.cw_eid
FROM appears AS appears0, cw_Basket AS _X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=_X.cw_eid AND _X.cw_name=tutu
UNION
SELECT DISTINCT _X.cw_eid
FROM appears AS appears0, cw_Folder AS _X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=_X.cw_eid AND _X.cw_name=tutu
"""),
            )):
            yield t



class MySQLGenerator(PostgresSQLGeneratorTC):

    def setUp(self):
        RQLGeneratorTC.setUp(self)
        indexer = get_indexer('mysql', 'utf8')
        dbms_helper = ADV_FUNC_HELPER_DIRECTORY['mysql']
        dbms_helper.fti_uid_attr = indexer.uid_attr
        dbms_helper.fti_table = indexer.table
        dbms_helper.fti_restriction_sql = indexer.restriction_sql
        dbms_helper.fti_need_distinct_query = indexer.need_distinct
        self.o = SQLGenerator(schema, dbms_helper)

    def _norm_sql(self, sql):
        sql = sql.strip().replace(' ILIKE ', ' LIKE ').replace('TRUE', '1').replace('FALSE', '0')
        newsql = []
        latest = None
        for line in sql.splitlines(False):
            firstword = line.split(None, 1)[0]
            if firstword == 'WHERE' and latest == 'SELECT':
                newsql.append('FROM (SELECT 1) AS _T')
            newsql.append(line)
            latest = firstword
        return '\n'.join(newsql)

    def test_from_clause_needed(self):
        queries = [("Any 1 WHERE EXISTS(T is CWGroup, T name 'managers')",
                    '''SELECT 1
FROM (SELECT 1) AS _T
WHERE EXISTS(SELECT 1 FROM cw_CWGroup AS _T WHERE _T.cw_name=managers)'''),
                   ('Any X,Y WHERE NOT X created_by Y, X eid 5, Y eid 6',
                    '''SELECT 5, 6
FROM (SELECT 1) AS _T
WHERE NOT EXISTS(SELECT 1 FROM created_by_relation AS rel_created_by0 WHERE rel_created_by0.eid_from=5 AND rel_created_by0.eid_to=6)'''),
                   ]
        for t in self._parse(queries):
            yield t


    def test_has_text(self):
        queries = [
            ('Any X WHERE X has_text "toto tata"',
             """SELECT appears0.uid
FROM appears AS appears0
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE)"""),
            ('Personne X WHERE X has_text "toto tata"',
             """SELECT _X.eid
FROM appears AS appears0, entities AS _X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=_X.eid AND _X.type='Personne'"""),
            ('Personne X WHERE X has_text %(text)s',
             """SELECT _X.eid
FROM appears AS appears0, entities AS _X
WHERE MATCH (appears0.words) AGAINST ('hip hop momo' IN BOOLEAN MODE) AND appears0.uid=_X.eid AND _X.type='Personne'"""),
            ('Any X WHERE X has_text "toto tata", X name "tutu", X is IN (Basket,Folder)',
             """SELECT _X.cw_eid
FROM appears AS appears0, cw_Basket AS _X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=_X.cw_eid AND _X.cw_name=tutu
UNION ALL
SELECT _X.cw_eid
FROM appears AS appears0, cw_Folder AS _X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=_X.cw_eid AND _X.cw_name=tutu
""")
            ]
        for t in self._parse(queries):
            yield t


    def test_ambigous_exists_no_from_clause(self):
        self._check('Any COUNT(U) WHERE U eid 1, EXISTS (P owned_by U, P is IN (Note, Affaire))',
                    '''SELECT COUNT(1)
FROM (SELECT 1) AS _T
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, cw_Affaire AS _P WHERE rel_owned_by0.eid_from=_P.cw_eid AND rel_owned_by0.eid_to=1 UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, cw_Note AS _P WHERE rel_owned_by1.eid_from=_P.cw_eid AND rel_owned_by1.eid_to=1)''')

    def test_groupby_multiple_outerjoins(self):
        self._check('Any A,U,P,group_concat(TN) GROUPBY A,U,P WHERE A is Affaire, A concerne N, N todo_by U?, T? tags A, T name TN, A todo_by P?',
                     '''SELECT _A.cw_eid, rel_todo_by1.eid_to, rel_todo_by3.eid_to, GROUP_CONCAT(_T.cw_name)
FROM concerne_relation AS rel_concerne0, cw_Affaire AS _A LEFT OUTER JOIN tags_relation AS rel_tags2 ON (rel_tags2.eid_to=_A.cw_eid) LEFT OUTER JOIN cw_Tag AS _T ON (rel_tags2.eid_from=_T.cw_eid) LEFT OUTER JOIN todo_by_relation AS rel_todo_by3 ON (rel_todo_by3.eid_from=_A.cw_eid), cw_Note AS _N LEFT OUTER JOIN todo_by_relation AS rel_todo_by1 ON (rel_todo_by1.eid_from=_N.cw_eid)
WHERE rel_concerne0.eid_from=_A.cw_eid AND rel_concerne0.eid_to=_N.cw_eid
GROUP BY _A.cw_eid,rel_todo_by1.eid_to,rel_todo_by3.eid_to''')


class removeUnsusedSolutionsTC(TestCase):
    def test_invariant_not_varying(self):
        rqlst = mock_object(defined_vars={})
        rqlst.defined_vars['A'] = mock_object(scope=rqlst, stinfo={'optrelations':False}, _q_invariant=True)
        rqlst.defined_vars['B'] = mock_object(scope=rqlst, stinfo={'optrelations':False}, _q_invariant=False)
        self.assertEquals(remove_unused_solutions(rqlst, [{'A': 'RugbyGroup', 'B': 'RugbyTeam'},
                                                          {'A': 'FootGroup', 'B': 'FootTeam'}], {}, None),
                          ([{'A': 'RugbyGroup', 'B': 'RugbyTeam'},
                            {'A': 'FootGroup', 'B': 'FootTeam'}],
                           {}, set('B'))
                          )

    def test_invariant_varying(self):
        rqlst = mock_object(defined_vars={})
        rqlst.defined_vars['A'] = mock_object(scope=rqlst, stinfo={'optrelations':False}, _q_invariant=True)
        rqlst.defined_vars['B'] = mock_object(scope=rqlst, stinfo={'optrelations':False}, _q_invariant=False)
        self.assertEquals(remove_unused_solutions(rqlst, [{'A': 'RugbyGroup', 'B': 'RugbyTeam'},
                                                          {'A': 'FootGroup', 'B': 'RugbyTeam'}], {}, None),
                          ([{'A': 'RugbyGroup', 'B': 'RugbyTeam'}], {}, set())
                          )

if __name__ == '__main__':
    unittest_main()
