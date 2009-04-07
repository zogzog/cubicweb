"""unit tests for module cubicweb.server.sources.rql2sql"""

import sys

from logilab.common.testlib import TestCase, unittest_main

from rql import BadRQLQuery
from indexer import get_indexer

#from cubicweb.server.sources.native import remove_unused_solutions
from cubicweb.server.sources.rql2sql import SQLGenerator

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
schema['comments'].inlined = False

PARSER = [
    (r"Personne P WHERE P nom 'Zig\'oto';",
     '''SELECT P.cw_eid
FROM cw_Personne AS P
WHERE P.cw_nom=Zig\'oto'''),

    (r'Personne P WHERE P nom ~= "Zig\"oto%";',
     '''SELECT P.cw_eid
FROM cw_Personne AS P
WHERE P.cw_nom ILIKE Zig"oto%'''),
    ]

BASIC = [

    ("Any X WHERE X is Affaire",
     '''SELECT X.cw_eid
FROM cw_Affaire AS X'''),
    
    ("Any X WHERE X eid 0",
     '''SELECT 0'''),
    
    ("Personne P",
     '''SELECT P.cw_eid
FROM cw_Personne AS P'''),

    ("Personne P WHERE P test TRUE",
     '''SELECT P.cw_eid
FROM cw_Personne AS P
WHERE P.cw_test=True'''),

    ("Personne P WHERE P test false",
     '''SELECT P.cw_eid
FROM cw_Personne AS P
WHERE P.cw_test=False'''),

    ("Personne P WHERE P eid -1",
     '''SELECT -1'''),

    ("Personne P LIMIT 20 OFFSET 10",
     '''SELECT P.cw_eid
FROM cw_Personne AS P
LIMIT 20
OFFSET 10'''),

    ("Personne P WHERE S is Societe, P travaille S, S nom 'Logilab';",
     '''SELECT rel_travaille0.eid_from
FROM cw_Societe AS S, travaille_relation AS rel_travaille0
WHERE rel_travaille0.eid_to=S.cw_eid AND S.cw_nom=Logilab'''),

    ("Personne P WHERE P concerne A, A concerne S, S nom 'Logilab', S is Societe;",
     '''SELECT rel_concerne0.eid_from
FROM concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1, cw_Societe AS S
WHERE rel_concerne0.eid_to=rel_concerne1.eid_from AND rel_concerne1.eid_to=S.cw_eid AND S.cw_nom=Logilab'''),

    ("Note N WHERE X evaluee N, X nom 'Logilab';",
     '''SELECT rel_evaluee0.eid_to
FROM cw_Division AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.cw_eid AND X.cw_nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_Personne AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.cw_eid AND X.cw_nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_Societe AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.cw_eid AND X.cw_nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_SubDivision AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.cw_eid AND X.cw_nom=Logilab'''),

    ("Note N WHERE X evaluee N, X nom in ('Logilab', 'Caesium');",
     '''SELECT rel_evaluee0.eid_to
FROM cw_Division AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.cw_eid AND X.cw_nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_Personne AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.cw_eid AND X.cw_nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_Societe AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.cw_eid AND X.cw_nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM cw_SubDivision AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.cw_eid AND X.cw_nom IN(Logilab, Caesium)'''),

    ("Any X WHERE X creation_date TODAY, X is Affaire",
     '''SELECT X.cw_eid
FROM cw_Affaire AS X
WHERE DATE(X.cw_creation_date)=CURRENT_DATE'''),

    ("Any N WHERE G is EGroup, G name N, E eid 12, E read_permission G",
     '''SELECT G.cw_name
FROM cw_EGroup AS G, read_permission_relation AS rel_read_permission0
WHERE rel_read_permission0.eid_from=12 AND rel_read_permission0.eid_to=G.cw_eid'''),

    ('Any Y WHERE U login "admin", U login Y', # stupid but valid...
     """SELECT U.cw_login
FROM cw_EUser AS U
WHERE U.cw_login=admin"""),

    ('Any T WHERE T tags X, X is State',
     '''SELECT rel_tags0.eid_from
FROM cw_State AS X, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=X.cw_eid'''),

    ('Any X,Y WHERE X eid 0, Y eid 1, X concerne Y',
     '''SELECT 0, 1
FROM concerne_relation AS rel_concerne0
WHERE rel_concerne0.eid_from=0 AND rel_concerne0.eid_to=1'''),

    ("Any X WHERE X prenom 'lulu',"
     "EXISTS(X owned_by U, U in_group G, G name 'lulufanclub' OR G name 'managers');",
     '''SELECT X.cw_eid
FROM cw_Personne AS X
WHERE X.cw_prenom=lulu AND EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, in_group_relation AS rel_in_group1, cw_EGroup AS G WHERE rel_owned_by0.eid_from=X.cw_eid AND rel_in_group1.eid_from=rel_owned_by0.eid_to AND rel_in_group1.eid_to=G.cw_eid AND ((G.cw_name=lulufanclub) OR (G.cw_name=managers)))'''),

    ("Any X WHERE X prenom 'lulu',"
     "NOT EXISTS(X owned_by U, U in_group G, G name 'lulufanclub' OR G name 'managers');",
     '''SELECT X.cw_eid
FROM cw_Personne AS X
WHERE X.cw_prenom=lulu AND NOT EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, in_group_relation AS rel_in_group1, cw_EGroup AS G WHERE rel_owned_by0.eid_from=X.cw_eid AND rel_in_group1.eid_from=rel_owned_by0.eid_to AND rel_in_group1.eid_to=G.cw_eid AND ((G.cw_name=lulufanclub) OR (G.cw_name=managers)))'''),
]

ADVANCED= [

    ("Societe S WHERE S nom 'Logilab' OR S nom 'Caesium'",
     '''SELECT S.cw_eid
FROM cw_Societe AS S
WHERE ((S.cw_nom=Logilab) OR (S.cw_nom=Caesium))'''),
    
    ('Any X WHERE X nom "toto", X eid IN (9700, 9710, 1045, 674)',
    '''SELECT X.cw_eid
FROM cw_Division AS X
WHERE X.cw_nom=toto AND X.cw_eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT X.cw_eid
FROM cw_Personne AS X
WHERE X.cw_nom=toto AND X.cw_eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT X.cw_eid
FROM cw_Societe AS X
WHERE X.cw_nom=toto AND X.cw_eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT X.cw_eid
FROM cw_SubDivision AS X
WHERE X.cw_nom=toto AND X.cw_eid IN(9700, 9710, 1045, 674)'''),

    ('Any Y, COUNT(N) GROUPBY Y WHERE Y evaluee N;',
     '''SELECT rel_evaluee0.eid_from, COUNT(rel_evaluee0.eid_to)
FROM evaluee_relation AS rel_evaluee0
GROUP BY rel_evaluee0.eid_from'''),

    ("Any X WHERE X concerne B or C concerne X",
     '''SELECT X.cw_eid
FROM concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1, cw_Affaire AS X
WHERE ((rel_concerne0.eid_from=X.cw_eid) OR (rel_concerne1.eid_to=X.cw_eid))'''),

    ("Any X WHERE X travaille S or X concerne A",
     '''SELECT X.cw_eid
FROM concerne_relation AS rel_concerne1, cw_Personne AS X, travaille_relation AS rel_travaille0
WHERE ((rel_travaille0.eid_from=X.cw_eid) OR (rel_concerne1.eid_from=X.cw_eid))'''),

    ("Any N WHERE A evaluee N or N ecrit_par P",
     '''SELECT N.cw_eid
FROM cw_Note AS N, evaluee_relation AS rel_evaluee0
WHERE ((rel_evaluee0.eid_to=N.cw_eid) OR (N.cw_ecrit_par IS NOT NULL))'''),

    ("Any N WHERE A evaluee N or EXISTS(N todo_by U)",
     '''SELECT N.cw_eid
FROM cw_Note AS N, evaluee_relation AS rel_evaluee0
WHERE ((rel_evaluee0.eid_to=N.cw_eid) OR (EXISTS(SELECT 1 FROM todo_by_relation AS rel_todo_by1 WHERE rel_todo_by1.eid_from=N.cw_eid)))'''),

    ("Any N WHERE A evaluee N or N todo_by U",
     '''SELECT N.cw_eid
FROM cw_Note AS N, evaluee_relation AS rel_evaluee0, todo_by_relation AS rel_todo_by1
WHERE ((rel_evaluee0.eid_to=N.cw_eid) OR (rel_todo_by1.eid_from=N.cw_eid))'''),
    
    ("Any X WHERE X concerne B or C concerne X, B eid 12, C eid 13",
     '''SELECT X.cw_eid
FROM concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1, cw_Affaire AS X
WHERE ((rel_concerne0.eid_from=X.cw_eid AND rel_concerne0.eid_to=12) OR (rel_concerne1.eid_from=13 AND rel_concerne1.eid_to=X.cw_eid))'''),

    ('Any X WHERE X created_by U, X concerne B OR C concerne X, B eid 12, C eid 13',
     '''SELECT rel_created_by0.eid_from
FROM concerne_relation AS rel_concerne1, concerne_relation AS rel_concerne2, created_by_relation AS rel_created_by0
WHERE ((rel_concerne1.eid_from=rel_created_by0.eid_from AND rel_concerne1.eid_to=12) OR (rel_concerne2.eid_from=13 AND rel_concerne2.eid_to=rel_created_by0.eid_from))'''),

    ('Any P WHERE P travaille_subdivision S1 OR P travaille_subdivision S2, S1 nom "logilab", S2 nom "caesium"',
     '''SELECT P.cw_eid
FROM cw_Personne AS P, cw_SubDivision AS S1, cw_SubDivision AS S2, travaille_subdivision_relation AS rel_travaille_subdivision0, travaille_subdivision_relation AS rel_travaille_subdivision1
WHERE ((rel_travaille_subdivision0.eid_from=P.cw_eid AND rel_travaille_subdivision0.eid_to=S1.cw_eid) OR (rel_travaille_subdivision1.eid_from=P.cw_eid AND rel_travaille_subdivision1.eid_to=S2.cw_eid)) AND S1.cw_nom=logilab AND S2.cw_nom=caesium'''),

    ('Any X WHERE T tags X',
     '''SELECT rel_tags0.eid_to
FROM tags_relation AS rel_tags0'''),
    
    ('Any X WHERE X in_basket B, B eid 12',
     '''SELECT rel_in_basket0.eid_from
FROM in_basket_relation AS rel_in_basket0
WHERE rel_in_basket0.eid_to=12'''),
    
    ('Any SEN,RN,OEN WHERE X from_entity SE, SE eid 44, X relation_type R, R eid 139, X to_entity OE, OE eid 42, R name RN, SE name SEN, OE name OEN',
     '''SELECT SE.cw_name, R.cw_name, OE.cw_name
FROM cw_EEType AS OE, cw_EEType AS SE, cw_EFRDef AS X, cw_ERType AS R
WHERE X.cw_from_entity=44 AND SE.cw_eid=44 AND X.cw_relation_type=139 AND R.cw_eid=139 AND X.cw_to_entity=42 AND OE.cw_eid=42
UNION ALL
SELECT SE.cw_name, R.cw_name, OE.cw_name
FROM cw_EEType AS OE, cw_EEType AS SE, cw_ENFRDef AS X, cw_ERType AS R
WHERE X.cw_from_entity=44 AND SE.cw_eid=44 AND X.cw_relation_type=139 AND R.cw_eid=139 AND X.cw_to_entity=42 AND OE.cw_eid=42'''),

    # Any O WHERE NOT S corrected_in O, S eid %(x)s, S concerns P, O version_of P, O in_state ST, NOT ST name "published", O modification_date MTIME ORDERBY MTIME DESC LIMIT 9
    ('Any O WHERE NOT S ecrit_par O, S eid 1, S inline1 P, O inline2 P',
     '''SELECT DISTINCT O.cw_eid
FROM cw_Note AS S, cw_Personne AS O
WHERE (S.cw_ecrit_par IS NULL OR S.cw_ecrit_par!=O.cw_eid) AND S.cw_eid=1 AND O.cw_inline2=S.cw_inline1'''),

    ('DISTINCT Any S ORDERBY stockproc(SI) WHERE NOT S ecrit_par O, S para SI',
     '''SELECT T1.C0 FROM (SELECT DISTINCT S.cw_eid AS C0, STOCKPROC(S.cw_para) AS C1
FROM cw_Note AS S
WHERE S.cw_ecrit_par IS NULL
ORDER BY 2) AS T1'''),

    ('Any N WHERE N todo_by U, N is Note, U eid 2, N filed_under T, T eid 3',
     # N would actually be invarient if U eid 2 had given a specific type to U
     '''SELECT N.cw_eid
FROM cw_Note AS N, filed_under_relation AS rel_filed_under1, todo_by_relation AS rel_todo_by0
WHERE rel_todo_by0.eid_from=N.cw_eid AND rel_todo_by0.eid_to=2 AND rel_filed_under1.eid_from=N.cw_eid AND rel_filed_under1.eid_to=3'''),

    ('Any N WHERE N todo_by U, U eid 2, P evaluee N, P eid 3',
     '''SELECT rel_evaluee1.eid_to
FROM evaluee_relation AS rel_evaluee1, todo_by_relation AS rel_todo_by0
WHERE rel_evaluee1.eid_to=rel_todo_by0.eid_from AND rel_todo_by0.eid_to=2 AND rel_evaluee1.eid_from=3'''),

    
    (' Any X,U WHERE C owned_by U, NOT X owned_by U, C eid 1, X eid 2',
     '''SELECT 2, rel_owned_by0.eid_to
FROM owned_by_relation AS rel_owned_by0
WHERE rel_owned_by0.eid_from=1 AND NOT EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by1 WHERE rel_owned_by1.eid_from=2 AND rel_owned_by0.eid_to=rel_owned_by1.eid_to)'''),

    ('Any GN WHERE X in_group G, G name GN, (G name "managers" OR EXISTS(X copain T, T login in ("comme", "cochon")))',
     '''SELECT G.cw_name
FROM cw_EGroup AS G, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_to=G.cw_eid AND ((G.cw_name=managers) OR (EXISTS(SELECT 1 FROM copain_relation AS rel_copain1, cw_EUser AS T WHERE rel_copain1.eid_from=rel_in_group0.eid_from AND rel_copain1.eid_to=T.cw_eid AND T.cw_login IN(comme, cochon))))'''),

    ('Any C WHERE C is Card, EXISTS(X documented_by C)',
      """SELECT C.cw_eid
FROM cw_Card AS C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_to=C.cw_eid)"""),
    
    ('Any C WHERE C is Card, EXISTS(X documented_by C, X eid 12)',
      """SELECT C.cw_eid
FROM cw_Card AS C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_from=12 AND rel_documented_by0.eid_to=C.cw_eid)"""),

    ('Any T WHERE C is Card, C title T, EXISTS(X documented_by C, X eid 12)',
      """SELECT C.cw_title
FROM cw_Card AS C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_from=12 AND rel_documented_by0.eid_to=C.cw_eid)"""),

    ('Any GN,L WHERE X in_group G, X login L, G name GN, EXISTS(X copain T, T login L, T login IN("comme", "cochon"))',
     '''SELECT G.cw_name, X.cw_login
FROM cw_EGroup AS G, cw_EUser AS X, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=X.cw_eid AND rel_in_group0.eid_to=G.cw_eid AND EXISTS(SELECT 1 FROM copain_relation AS rel_copain1, cw_EUser AS T WHERE rel_copain1.eid_from=X.cw_eid AND rel_copain1.eid_to=T.cw_eid AND T.cw_login=X.cw_login AND T.cw_login IN(comme, cochon))'''),

    ('Any X,S, MAX(T) GROUPBY X,S ORDERBY S WHERE X is EUser, T tags X, S eid IN(32), X in_state S',
     '''SELECT X.cw_eid, 32, MAX(rel_tags0.eid_from)
FROM cw_EUser AS X, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=X.cw_eid AND X.cw_in_state=32
GROUP BY X.cw_eid'''),

    ('Any COUNT(S),CS GROUPBY CS ORDERBY 1 DESC LIMIT 10 WHERE S is Affaire, C is Societe, S concerne C, C nom CS, (EXISTS(S owned_by 1)) OR (EXISTS(S documented_by N, N title "published"))',
     '''SELECT COUNT(rel_concerne0.eid_from), C.cw_nom
FROM concerne_relation AS rel_concerne0, cw_Societe AS C
WHERE rel_concerne0.eid_to=C.cw_eid AND ((EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by1 WHERE rel_concerne0.eid_from=rel_owned_by1.eid_from AND rel_owned_by1.eid_to=1)) OR (EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by2, cw_Card AS N WHERE rel_concerne0.eid_from=rel_documented_by2.eid_from AND rel_documented_by2.eid_to=N.cw_eid AND N.cw_title=published)))
GROUP BY C.cw_nom
ORDER BY 1 DESC
LIMIT 10'''),

    ('Any X WHERE Y evaluee X, Y is EUser',
     '''SELECT rel_evaluee0.eid_to
FROM cw_EUser AS Y, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=Y.cw_eid'''),

    ('Any L WHERE X login "admin", X identity Y, Y login L',
     '''SELECT Y.cw_login
FROM cw_EUser AS X, cw_EUser AS Y
WHERE X.cw_login=admin AND X.cw_eid=Y.cw_eid'''),

    ('Any L WHERE X login "admin", NOT X identity Y, Y login L',
     '''SELECT Y.cw_login
FROM cw_EUser AS X, cw_EUser AS Y
WHERE X.cw_login=admin AND NOT X.cw_eid=Y.cw_eid'''),
    
    ('Any L WHERE X login "admin", X identity Y?, Y login L',
     '''SELECT Y.cw_login
FROM cw_EUser AS X LEFT OUTER JOIN cw_EUser AS Y ON (X.cw_eid=Y.cw_eid)
WHERE X.cw_login=admin'''),

    ('Any XN ORDERBY XN WHERE X name XN',
     '''SELECT X.cw_name
FROM cw_Basket AS X
UNION ALL
SELECT X.cw_name
FROM cw_ECache AS X
UNION ALL
SELECT X.cw_name
FROM cw_EConstraintType AS X
UNION ALL
SELECT X.cw_name
FROM cw_EEType AS X
UNION ALL
SELECT X.cw_name
FROM cw_EGroup AS X
UNION ALL
SELECT X.cw_name
FROM cw_EPermission AS X
UNION ALL
SELECT X.cw_name
FROM cw_ERType AS X
UNION ALL
SELECT X.cw_name
FROM cw_File AS X
UNION ALL
SELECT X.cw_name
FROM cw_Folder AS X
UNION ALL
SELECT X.cw_name
FROM cw_Image AS X
UNION ALL
SELECT X.cw_name
FROM cw_State AS X
UNION ALL
SELECT X.cw_name
FROM cw_Tag AS X
UNION ALL
SELECT X.cw_name
FROM cw_Transition AS X
ORDER BY 1'''),

#    ('Any XN WHERE X name XN GROUPBY XN',
#     ''''''),
#    ('Any XN, COUNT(X) WHERE X name XN GROUPBY XN',
#     ''''''),

    # DISTINCT, can use relatin under exists scope as principal
    ('DISTINCT Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), EXISTS(X read_permission Y)',
     '''SELECT DISTINCT X.cw_eid, rel_read_permission0.eid_to
FROM cw_EEType AS X, read_permission_relation AS rel_read_permission0
WHERE X.cw_name=EGroup AND rel_read_permission0.eid_to IN(1, 2, 3) AND EXISTS(SELECT 1 WHERE rel_read_permission0.eid_from=X.cw_eid)
UNION
SELECT DISTINCT X.cw_eid, rel_read_permission0.eid_to
FROM cw_ERType AS X, read_permission_relation AS rel_read_permission0
WHERE X.cw_name=EGroup AND rel_read_permission0.eid_to IN(1, 2, 3) AND EXISTS(SELECT 1 WHERE rel_read_permission0.eid_from=X.cw_eid)'''),

    # no distinct, Y can't be invariant
    ('Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), EXISTS(X read_permission Y)',
     '''SELECT X.cw_eid, Y.cw_eid
FROM cw_EEType AS X, cw_EGroup AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION ALL
SELECT X.cw_eid, Y.cw_eid
FROM cw_EEType AS X, cw_RQLExpression AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION ALL
SELECT X.cw_eid, Y.cw_eid
FROM cw_EGroup AS Y, cw_ERType AS X
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION ALL
SELECT X.cw_eid, Y.cw_eid
FROM cw_ERType AS X, cw_RQLExpression AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)'''),

    # DISTINCT but NEGED exists, can't be invariant
    ('DISTINCT Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), NOT EXISTS(X read_permission Y)',
     '''SELECT DISTINCT X.cw_eid, Y.cw_eid
FROM cw_EEType AS X, cw_EGroup AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION
SELECT DISTINCT X.cw_eid, Y.cw_eid
FROM cw_EEType AS X, cw_RQLExpression AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION
SELECT DISTINCT X.cw_eid, Y.cw_eid
FROM cw_EGroup AS Y, cw_ERType AS X
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION
SELECT DISTINCT X.cw_eid, Y.cw_eid
FROM cw_ERType AS X, cw_RQLExpression AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)'''),

    # should generate the same query as above
    ('DISTINCT Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), NOT X read_permission Y',
     '''SELECT DISTINCT X.cw_eid, Y.cw_eid
FROM cw_EEType AS X, cw_EGroup AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION
SELECT DISTINCT X.cw_eid, Y.cw_eid
FROM cw_EEType AS X, cw_RQLExpression AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION
SELECT DISTINCT X.cw_eid, Y.cw_eid
FROM cw_EGroup AS Y, cw_ERType AS X
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION
SELECT DISTINCT X.cw_eid, Y.cw_eid
FROM cw_ERType AS X, cw_RQLExpression AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)'''),
    
    # neged relation, can't be inveriant
    ('Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), NOT X read_permission Y',
     '''SELECT X.cw_eid, Y.cw_eid
FROM cw_EEType AS X, cw_EGroup AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION ALL
SELECT X.cw_eid, Y.cw_eid
FROM cw_EEType AS X, cw_RQLExpression AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION ALL
SELECT X.cw_eid, Y.cw_eid
FROM cw_EGroup AS Y, cw_ERType AS X
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)
UNION ALL
SELECT X.cw_eid, Y.cw_eid
FROM cw_ERType AS X, cw_RQLExpression AS Y
WHERE X.cw_name=EGroup AND Y.cw_eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.cw_eid AND rel_read_permission0.eid_to=Y.cw_eid)'''),

    ('Any MAX(X)+MIN(X), N GROUPBY N WHERE X name N;',
     '''SELECT (MAX(T1.C0) + MIN(T1.C0)), T1.C1 FROM (SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_Basket AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_ECache AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_EConstraintType AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_EEType AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_EGroup AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_EPermission AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_ERType AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_File AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_Folder AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_Image AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_State AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_Tag AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_Transition AS X) AS T1
GROUP BY T1.C1'''),
    
    ('Any MAX(X)+MIN(LENGTH(D)), N GROUPBY N ORDERBY 1, N, DF WHERE X name N, X data D, X data_format DF;',
     '''SELECT (MAX(T1.C1) + MIN(LENGTH(T1.C0))), T1.C2 FROM (SELECT X.cw_data AS C0, X.cw_eid AS C1, X.cw_name AS C2, X.cw_data_format AS C3
FROM cw_File AS X
UNION ALL
SELECT X.cw_data AS C0, X.cw_eid AS C1, X.cw_name AS C2, X.cw_data_format AS C3
FROM cw_Image AS X) AS T1
GROUP BY T1.C2
ORDER BY 1,2,T1.C3'''),

    ('DISTINCT Any S ORDERBY R WHERE A is Affaire, A sujet S, A ref R',
     '''SELECT T1.C0 FROM (SELECT DISTINCT A.cw_sujet AS C0, A.cw_ref AS C1
FROM cw_Affaire AS A
ORDER BY 2) AS T1'''),
    
    ('DISTINCT Any MAX(X)+MIN(LENGTH(D)), N GROUPBY N ORDERBY 2, DF WHERE X name N, X data D, X data_format DF;',
     '''SELECT T1.C0,T1.C1 FROM (SELECT DISTINCT (MAX(T1.C1) + MIN(LENGTH(T1.C0))) AS C0, T1.C2 AS C1, T1.C3 AS C2 FROM (SELECT DISTINCT X.cw_data AS C0, X.cw_eid AS C1, X.cw_name AS C2, X.cw_data_format AS C3
FROM cw_File AS X
UNION
SELECT DISTINCT X.cw_data AS C0, X.cw_eid AS C1, X.cw_name AS C2, X.cw_data_format AS C3
FROM cw_Image AS X) AS T1
GROUP BY T1.C2,T1.C3
ORDER BY 2,3) AS T1
'''),

    # ambiguity in EXISTS() -> should union the sub-query
    ('Any T WHERE T is Tag, NOT T name in ("t1", "t2"), EXISTS(T tags X, X is IN (EUser, EGroup))',
     '''SELECT T.cw_eid
FROM cw_Tag AS T
WHERE NOT (T.cw_name IN(t1, t2)) AND EXISTS(SELECT 1 FROM tags_relation AS rel_tags0, cw_EGroup AS X WHERE rel_tags0.eid_from=T.cw_eid AND rel_tags0.eid_to=X.cw_eid UNION SELECT 1 FROM tags_relation AS rel_tags1, cw_EUser AS X WHERE rel_tags1.eid_from=T.cw_eid AND rel_tags1.eid_to=X.cw_eid)'''),

    # must not use a relation in EXISTS scope to inline a variable 
    ('Any U WHERE U eid IN (1,2), EXISTS(X owned_by U)',
     '''SELECT U.cw_eid
FROM cw_EUser AS U
WHERE U.cw_eid IN(1, 2) AND EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE rel_owned_by0.eid_to=U.cw_eid)'''),

    ('Any U WHERE EXISTS(U eid IN (1,2), X owned_by U)',
     '''SELECT U.cw_eid
FROM cw_EUser AS U
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE U.cw_eid IN(1, 2) AND rel_owned_by0.eid_to=U.cw_eid)'''),

    ('Any COUNT(U) WHERE EXISTS (P owned_by U, P is IN (Note, Affaire))',
     '''SELECT COUNT(U.cw_eid)
FROM cw_EUser AS U
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, cw_Affaire AS P WHERE rel_owned_by0.eid_from=P.cw_eid AND rel_owned_by0.eid_to=U.cw_eid UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, cw_Note AS P WHERE rel_owned_by1.eid_from=P.cw_eid AND rel_owned_by1.eid_to=U.cw_eid)'''),

    ('Any MAX(X)',
     '''SELECT MAX(X.eid)
FROM entities AS X'''),

    ('Any MAX(X) WHERE X is Note',
     '''SELECT MAX(X.cw_eid)
FROM cw_Note AS X'''),
    
    ('Any X WHERE X eid > 12',
     '''SELECT X.eid
FROM entities AS X
WHERE X.eid>12'''),
    
    ('Any X WHERE X eid > 12, X is Note',
     """SELECT X.eid
FROM entities AS X
WHERE X.type='Note' AND X.eid>12"""),
    
    ('Any X, T WHERE X eid > 12, X title T',
     """SELECT X.cw_eid, X.cw_title
FROM cw_Bookmark AS X
WHERE X.cw_eid>12
UNION ALL
SELECT X.cw_eid, X.cw_title
FROM cw_Card AS X
WHERE X.cw_eid>12
UNION ALL
SELECT X.cw_eid, X.cw_title
FROM cw_EmailThread AS X
WHERE X.cw_eid>12"""),

    ('Any X',
     '''SELECT X.eid
FROM entities AS X'''),

    ('Any X GROUPBY X WHERE X eid 12',
     '''SELECT 12'''),
    
    ('Any X GROUPBY X ORDERBY Y WHERE X eid 12, X login Y',
     '''SELECT X.cw_eid
FROM cw_EUser AS X
WHERE X.cw_eid=12
GROUP BY X.cw_eid
ORDER BY X.cw_login'''),
    
    ('Any U,COUNT(X) GROUPBY U WHERE U eid 12, X owned_by U HAVING COUNT(X) > 10',
     '''SELECT rel_owned_by0.eid_to, COUNT(rel_owned_by0.eid_from)
FROM owned_by_relation AS rel_owned_by0
WHERE rel_owned_by0.eid_to=12
GROUP BY rel_owned_by0.eid_to
HAVING COUNT(rel_owned_by0.eid_from)>10'''),

    ('DISTINCT Any X ORDERBY stockproc(X) WHERE U login X',
     '''SELECT T1.C0 FROM (SELECT DISTINCT U.cw_login AS C0, STOCKPROC(U.cw_login) AS C1
FROM cw_EUser AS U
ORDER BY 2) AS T1'''),
    
    ('DISTINCT Any X ORDERBY Y WHERE B bookmarked_by X, X login Y',
     '''SELECT T1.C0 FROM (SELECT DISTINCT X.cw_eid AS C0, X.cw_login AS C1
FROM bookmarked_by_relation AS rel_bookmarked_by0, cw_EUser AS X
WHERE rel_bookmarked_by0.eid_to=X.cw_eid
ORDER BY 2) AS T1'''),

    ('DISTINCT Any X ORDERBY SN WHERE X in_state S, S name SN',
     '''SELECT T1.C0 FROM (SELECT DISTINCT X.cw_eid AS C0, S.cw_name AS C1
FROM cw_Affaire AS X, cw_State AS S
WHERE X.cw_in_state=S.cw_eid
UNION
SELECT DISTINCT X.cw_eid AS C0, S.cw_name AS C1
FROM cw_EUser AS X, cw_State AS S
WHERE X.cw_in_state=S.cw_eid
UNION
SELECT DISTINCT X.cw_eid AS C0, S.cw_name AS C1
FROM cw_Note AS X, cw_State AS S
WHERE X.cw_in_state=S.cw_eid
ORDER BY 2) AS T1'''),

    ]

MULTIPLE_SEL = [
    ("DISTINCT Any X,Y where P is Personne, P nom X , P prenom Y;",
     '''SELECT DISTINCT P.cw_nom, P.cw_prenom
FROM cw_Personne AS P'''),
    ("Any X,Y where P is Personne, P nom X , P prenom Y, not P nom NULL;",
     '''SELECT P.cw_nom, P.cw_prenom
FROM cw_Personne AS P
WHERE NOT (P.cw_nom IS NULL)'''),
    ("Personne X,Y where X nom NX, Y nom NX, X eid XE, not Y eid XE",
     '''SELECT X.cw_eid, Y.cw_eid
FROM cw_Personne AS X, cw_Personne AS Y
WHERE Y.cw_nom=X.cw_nom AND NOT (Y.cw_eid=X.cw_eid)''')
    ]

NEGATIONS = [
    ("Personne X WHERE NOT X evaluee Y;",
     '''SELECT X.cw_eid
FROM cw_Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=X.cw_eid)'''),
    
    ("Note N WHERE NOT X evaluee N, X eid 0",
     '''SELECT N.cw_eid
FROM cw_Note AS N
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=0 AND rel_evaluee0.eid_to=N.cw_eid)'''),
    
    ('Any X WHERE NOT X travaille S, X is Personne',
     '''SELECT X.cw_eid
FROM cw_Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=X.cw_eid)'''),
    
    ("Personne P where not P datenaiss TODAY",
     '''SELECT P.cw_eid
FROM cw_Personne AS P
WHERE NOT (DATE(P.cw_datenaiss)=CURRENT_DATE)'''),
    
    ("Personne P where NOT P concerne A",
     '''SELECT P.cw_eid
FROM cw_Personne AS P
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_from=P.cw_eid)'''),
    
    ("Affaire A where not P concerne A",
     '''SELECT A.cw_eid
FROM cw_Affaire AS A
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_to=A.cw_eid)'''),
    ("Personne P where not P concerne A, A sujet ~= 'TEST%'",
     '''SELECT P.cw_eid
FROM cw_Affaire AS A, cw_Personne AS P
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_from=P.cw_eid AND rel_concerne0.eid_to=A.cw_eid) AND A.cw_sujet ILIKE TEST%'''),

    ('Any S WHERE NOT T eid 28258, T tags S',
     '''SELECT rel_tags0.eid_to
FROM tags_relation AS rel_tags0
WHERE NOT (rel_tags0.eid_from=28258)'''),
    
    ('Any S WHERE T is Tag, T name TN, NOT T eid 28258, T tags S, S name SN',
     '''SELECT S.cw_eid
FROM cw_EGroup AS S, cw_Tag AS T, tags_relation AS rel_tags0
WHERE NOT (T.cw_eid=28258) AND rel_tags0.eid_from=T.cw_eid AND rel_tags0.eid_to=S.cw_eid
UNION ALL
SELECT S.cw_eid
FROM cw_State AS S, cw_Tag AS T, tags_relation AS rel_tags0
WHERE NOT (T.cw_eid=28258) AND rel_tags0.eid_from=T.cw_eid AND rel_tags0.eid_to=S.cw_eid
UNION ALL
SELECT S.cw_eid
FROM cw_Tag AS S, cw_Tag AS T, tags_relation AS rel_tags0
WHERE NOT (T.cw_eid=28258) AND rel_tags0.eid_from=T.cw_eid AND rel_tags0.eid_to=S.cw_eid'''),

    
    ('Any X,Y WHERE X created_by Y, X eid 5, NOT Y eid 6',
     '''SELECT 5, rel_created_by0.eid_to
FROM created_by_relation AS rel_created_by0
WHERE rel_created_by0.eid_from=5 AND NOT (rel_created_by0.eid_to=6)'''),

    ('Note X WHERE NOT Y evaluee X',
     '''SELECT X.cw_eid
FROM cw_Note AS X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_to=X.cw_eid)'''),

    ('Any Y WHERE NOT Y evaluee X',
     '''SELECT Y.cw_eid
FROM cw_Division AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.cw_eid)
UNION ALL
SELECT Y.cw_eid
FROM cw_EUser AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.cw_eid)
UNION ALL
SELECT Y.cw_eid
FROM cw_Personne AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.cw_eid)
UNION ALL
SELECT Y.cw_eid
FROM cw_Societe AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.cw_eid)
UNION ALL
SELECT Y.cw_eid
FROM cw_SubDivision AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.cw_eid)'''),

    ('Any X WHERE NOT Y evaluee X, Y is EUser',
     '''SELECT X.cw_eid
FROM cw_Note AS X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0,cw_EUser AS Y WHERE rel_evaluee0.eid_from=Y.cw_eid AND rel_evaluee0.eid_to=X.cw_eid)'''),
    
    ('Any X,T WHERE X title T, NOT X is Bookmark',
     '''SELECT DISTINCT X.cw_eid, X.cw_title
FROM cw_Card AS X
UNION
SELECT DISTINCT X.cw_eid, X.cw_title
FROM cw_EmailThread AS X'''),

    ('Any K,V WHERE P is EProperty, P pkey K, P value V, NOT P for_user U',
     '''SELECT DISTINCT P.cw_pkey, P.cw_value
FROM cw_EProperty AS P
WHERE P.cw_for_user IS NULL'''),

    ('Any S WHERE NOT X in_state S, X is IN(Affaire, EUser)',
     '''SELECT DISTINCT S.cw_eid
FROM cw_Affaire AS X, cw_State AS S
WHERE (X.cw_in_state IS NULL OR X.cw_in_state!=S.cw_eid)
INTERSECT
SELECT DISTINCT S.cw_eid
FROM cw_EUser AS X, cw_State AS S
WHERE (X.cw_in_state IS NULL OR X.cw_in_state!=S.cw_eid)'''),
    ]

OUTER_JOIN = [
    ('Any X,S WHERE X travaille S?',
     '''SELECT X.cw_eid, rel_travaille0.eid_to
FROM cw_Personne AS X LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=X.cw_eid)'''
#SELECT X.cw_eid, S.cw_eid
#FROM cw_Personne AS X LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=X.cw_eid) LEFT OUTER JOIN cw_Societe AS S ON (rel_travaille0.eid_to=S.cw_eid)'''
    ),
    ('Any S,X WHERE X? travaille S, S is Societe',
     '''SELECT S.cw_eid, rel_travaille0.eid_from
FROM cw_Societe AS S LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_to=S.cw_eid)'''
#SELECT S.cw_eid, X.cw_eid
#FROM cw_Societe AS S LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_to=S.cw_eid) LEFT OUTER JOIN cw_Personne AS X ON (rel_travaille0.eid_from=X.cw_eid)'''
    ),

    ('Any N,A WHERE N inline1 A?',
     '''SELECT N.cw_eid, N.cw_inline1
FROM cw_Note AS N'''),

    ('Any SN WHERE X from_state S?, S name SN',
     '''SELECT S.cw_name
FROM cw_TrInfo AS X LEFT OUTER JOIN cw_State AS S ON (X.cw_from_state=S.cw_eid)'''
    ),

    ('Any A,N WHERE N? inline1 A',
     '''SELECT A.cw_eid, N.cw_eid
FROM cw_Affaire AS A LEFT OUTER JOIN cw_Note AS N ON (N.cw_inline1=A.cw_eid)'''
    ),

    ('Any A,B,C,D,E,F,G WHERE A eid 12,A creation_date B,A modification_date C,A comment D,A from_state E?,A to_state F?,A wf_info_for G?',
    '''SELECT A.cw_eid, A.cw_creation_date, A.cw_modification_date, A.cw_comment, A.cw_from_state, A.cw_to_state, A.cw_wf_info_for
FROM cw_TrInfo AS A
WHERE A.cw_eid=12'''),

    ('Any FS,TS,C,D,U ORDERBY D DESC WHERE WF wf_info_for X,WF from_state FS?, WF to_state TS, WF comment C,WF creation_date D, WF owned_by U, X eid 1',
     '''SELECT WF.cw_from_state, WF.cw_to_state, WF.cw_comment, WF.cw_creation_date, rel_owned_by0.eid_to
FROM cw_TrInfo AS WF, owned_by_relation AS rel_owned_by0
WHERE WF.cw_wf_info_for=1 AND WF.cw_to_state IS NOT NULL AND rel_owned_by0.eid_from=WF.cw_eid
ORDER BY 4 DESC'''),

    ('Any X WHERE X is Affaire, S is Societe, EXISTS(X owned_by U OR (X concerne S?, S owned_by U))',
     '''SELECT X.cw_eid
FROM cw_Affaire AS X
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, cw_EUser AS U, cw_Affaire AS A LEFT OUTER JOIN concerne_relation AS rel_concerne1 ON (rel_concerne1.eid_from=A.cw_eid) LEFT OUTER JOIN cw_Societe AS S ON (rel_concerne1.eid_to=S.cw_eid), owned_by_relation AS rel_owned_by2 WHERE ((rel_owned_by0.eid_from=A.cw_eid AND rel_owned_by0.eid_to=U.cw_eid) OR (rel_owned_by2.eid_from=S.cw_eid AND rel_owned_by2.eid_to=U.cw_eid)) AND X.cw_eid=A.cw_eid)'''),

    ('Any C,M WHERE C travaille G?, G evaluee M?, G is Societe',
     '''SELECT C.cw_eid, rel_evaluee1.eid_to
FROM cw_Personne AS C LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=C.cw_eid) LEFT OUTER JOIN cw_Societe AS G ON (rel_travaille0.eid_to=G.cw_eid) LEFT OUTER JOIN evaluee_relation AS rel_evaluee1 ON (rel_evaluee1.eid_from=G.cw_eid)'''
#SELECT C.cw_eid, M.cw_eid
#FROM cw_Personne AS C LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=C.cw_eid) LEFT OUTER JOIN cw_Societe AS G ON (rel_travaille0.eid_to=G.cw_eid) LEFT OUTER JOIN evaluee_relation AS rel_evaluee1 ON (rel_evaluee1.eid_from=G.cw_eid) LEFT OUTER JOIN cw_Note AS M ON (rel_evaluee1.eid_to=M.cw_eid)'''
     ),

    ('Any A,C WHERE A documented_by C?, (C is NULL) OR (EXISTS(C require_permission F, '
     'F name "read", F require_group E, U in_group E)), U eid 1',
     '''SELECT A.cw_eid, rel_documented_by0.eid_to
FROM cw_Affaire AS A LEFT OUTER JOIN documented_by_relation AS rel_documented_by0 ON (rel_documented_by0.eid_from=A.cw_eid)
WHERE ((rel_documented_by0.eid_to IS NULL) OR (EXISTS(SELECT 1 FROM require_permission_relation AS rel_require_permission1, cw_EPermission AS F, require_group_relation AS rel_require_group2, in_group_relation AS rel_in_group3 WHERE rel_documented_by0.eid_to=rel_require_permission1.eid_from AND rel_require_permission1.eid_to=F.cw_eid AND F.cw_name=read AND rel_require_group2.eid_from=F.cw_eid AND rel_in_group3.eid_to=rel_require_group2.eid_to AND rel_in_group3.eid_from=1)))'''),

    ("Any X WHERE X eid 12, P? connait X",
     '''SELECT X.cw_eid
FROM cw_Personne AS X LEFT OUTER JOIN connait_relation AS rel_connait0 ON (rel_connait0.eid_to=12)
WHERE X.cw_eid=12'''
#SELECT 12
#FROM cw_Personne AS X LEFT OUTER JOIN connait_relation AS rel_connait0 ON (rel_connait0.eid_to=12) LEFT OUTER JOIN Personne AS P ON (rel_connait0.eid_from=P.cw_eid)
#WHERE X.cw_eid=12'''
    ),

    ('Any GN, TN ORDERBY GN WHERE T tags G?, T name TN, G name GN',
    '''SELECT _T0.C1, T.cw_name
FROM cw_Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.cw_eid) LEFT OUTER JOIN (SELECT G.cw_eid AS C0, G.cw_name AS C1
FROM cw_EGroup AS G
UNION ALL
SELECT G.cw_eid AS C0, G.cw_name AS C1
FROM cw_State AS G
UNION ALL
SELECT G.cw_eid AS C0, G.cw_name AS C1
FROM cw_Tag AS G) AS _T0 ON (rel_tags0.eid_to=_T0.C0)
ORDER BY 1'''),


    # optional variable with additional restriction
    ('Any T,G WHERE T tags G?, G name "hop", G is EGroup',
     '''SELECT T.cw_eid, G.cw_eid
FROM cw_Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.cw_eid) LEFT OUTER JOIN cw_EGroup AS G ON (rel_tags0.eid_to=G.cw_eid AND G.cw_name=hop)'''),

    # optional variable with additional invariant restriction
    ('Any T,G WHERE T tags G?, G eid 12',
     '''SELECT T.cw_eid, rel_tags0.eid_to
FROM cw_Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.cw_eid AND rel_tags0.eid_to=12)'''),

    # optional variable with additional restriction appearing before the relation
    ('Any T,G WHERE G name "hop", T tags G?, G is EGroup',
     '''SELECT T.cw_eid, G.cw_eid
FROM cw_Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.cw_eid) LEFT OUTER JOIN cw_EGroup AS G ON (rel_tags0.eid_to=G.cw_eid AND G.cw_name=hop)'''),

    # optional variable with additional restriction on inlined relation
    # XXX the expected result should be as the query below. So what, raise BadRQLQuery ?
    ('Any T,G,S WHERE T tags G?, G in_state S, S name "hop", G is EUser',
     '''SELECT T.cw_eid, G.cw_eid, S.cw_eid
FROM cw_State AS S, cw_Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.cw_eid) LEFT OUTER JOIN cw_EUser AS G ON (rel_tags0.eid_to=G.cw_eid)
WHERE G.cw_in_state=S.cw_eid AND S.cw_name=hop
'''),

    # optional variable with additional invariant restriction on an inlined relation
    ('Any T,G,S WHERE T tags G, G in_state S?, S eid 1, G is EUser',
     '''SELECT rel_tags0.eid_from, G.cw_eid, G.cw_in_state
FROM cw_EUser AS G, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=G.cw_eid AND (G.cw_in_state=1 OR G.cw_in_state IS NULL)'''),

    # two optional variables with additional invariant restriction on an inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S eid 1, G is EUser',
     '''SELECT T.cw_eid, G.cw_eid, G.cw_in_state
FROM cw_Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.cw_eid) LEFT OUTER JOIN cw_EUser AS G ON (rel_tags0.eid_to=G.cw_eid AND (G.cw_in_state=1 OR G.cw_in_state IS NULL))'''),

    # two optional variables with additional restriction on an inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S name "hop", G is EUser',
     '''SELECT T.cw_eid, G.cw_eid, S.cw_eid
FROM cw_Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.cw_eid) LEFT OUTER JOIN cw_EUser AS G ON (rel_tags0.eid_to=G.cw_eid) LEFT OUTER JOIN cw_State AS S ON (G.cw_in_state=S.cw_eid AND S.cw_name=hop)'''),
    
    # two optional variables with additional restriction on an ambigous inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S name "hop"',
     '''SELECT T.cw_eid, _T0.C0, _T0.C1
FROM cw_Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.cw_eid) LEFT OUTER JOIN (SELECT G.cw_eid AS C0, S.cw_eid AS C1
FROM cw_Affaire AS G LEFT OUTER JOIN cw_State AS S ON (G.cw_in_state=S.cw_eid AND S.cw_name=hop) 
UNION ALL
SELECT G.cw_eid AS C0, S.cw_eid AS C1
FROM cw_EUser AS G LEFT OUTER JOIN cw_State AS S ON (G.cw_in_state=S.cw_eid AND S.cw_name=hop) 
UNION ALL
SELECT G.cw_eid AS C0, S.cw_eid AS C1
FROM cw_Note AS G LEFT OUTER JOIN cw_State AS S ON (G.cw_in_state=S.cw_eid AND S.cw_name=hop) ) AS _T0 ON (rel_tags0.eid_to=_T0.C0)'''),

    ]

VIRTUAL_VARS = [
    ("Personne P WHERE P travaille S, S tel T, S fax T, S is Societe;",
     '''SELECT rel_travaille0.eid_from
FROM cw_Societe AS S, travaille_relation AS rel_travaille0
WHERE rel_travaille0.eid_to=S.cw_eid AND S.cw_fax=S.cw_tel'''),
    
    ("Personne P where X eid 0, X creation_date D, P datenaiss < D, X is Affaire",
     '''SELECT P.cw_eid
FROM cw_Affaire AS X, cw_Personne AS P
WHERE X.cw_eid=0 AND P.cw_datenaiss<X.cw_creation_date'''),

    ("Any N,T WHERE N is Note, N type T;",
     '''SELECT N.cw_eid, N.cw_type
FROM cw_Note AS N'''),

    ("Personne P where X is Personne, X tel T, X fax F, P fax T+F",
     '''SELECT P.cw_eid
FROM cw_Personne AS P, cw_Personne AS X
WHERE P.cw_fax=(X.cw_tel + X.cw_fax)'''),

    ("Personne P where X tel T, X fax F, P fax IN (T,F)",
     '''SELECT P.cw_eid
FROM cw_Division AS X, cw_Personne AS P
WHERE P.cw_fax IN(X.cw_tel, X.cw_fax)
UNION ALL
SELECT P.cw_eid
FROM cw_Personne AS P, cw_Personne AS X
WHERE P.cw_fax IN(X.cw_tel, X.cw_fax)
UNION ALL
SELECT P.cw_eid
FROM cw_Personne AS P, cw_Societe AS X
WHERE P.cw_fax IN(X.cw_tel, X.cw_fax)
UNION ALL
SELECT P.cw_eid
FROM cw_Personne AS P, cw_SubDivision AS X
WHERE P.cw_fax IN(X.cw_tel, X.cw_fax)'''),

    ("Personne P where X tel T, X fax F, P fax IN (T,F,0832542332)",
     '''SELECT P.cw_eid
FROM cw_Division AS X, cw_Personne AS P
WHERE P.cw_fax IN(X.cw_tel, X.cw_fax, 832542332)
UNION ALL
SELECT P.cw_eid
FROM cw_Personne AS P, cw_Personne AS X
WHERE P.cw_fax IN(X.cw_tel, X.cw_fax, 832542332)
UNION ALL
SELECT P.cw_eid
FROM cw_Personne AS P, cw_Societe AS X
WHERE P.cw_fax IN(X.cw_tel, X.cw_fax, 832542332)
UNION ALL
SELECT P.cw_eid
FROM cw_Personne AS P, cw_SubDivision AS X
WHERE P.cw_fax IN(X.cw_tel, X.cw_fax, 832542332)'''),
    ]

FUNCS = [
    ("Any COUNT(P) WHERE P is Personne",
     '''SELECT COUNT(P.cw_eid)
FROM cw_Personne AS P'''),
##     ("Personne X where X nom upper('TOTO')",
##      '''SELECT X.cw_eid\nFROM cw_Personne AS X\nWHERE UPPER(X.cw_nom) = TOTO'''),
##     ("Personne X where X nom Y, UPPER(X) prenom upper(Y)",
##      '''SELECT X.cw_eid\nFROM cw_Personne AS X\nWHERE UPPER(X.cw_prenom) = UPPER(X.cw_nom)'''),
    ]

SYMETRIC = [
    ('Any P WHERE X eid 0, X connait P',
     '''SELECT DISTINCT P.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS P
WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=P.cw_eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=P.cw_eid)'''
#      '''SELECT rel_connait0.eid_to
# FROM connait_relation AS rel_connait0
# WHERE rel_connait0.eid_from=0
# UNION
# SELECT rel_connait0.eid_from
# FROM connait_relation AS rel_connait0
# WHERE rel_connait0.eid_to=0'''
     ),
    
    ('Any P WHERE X connait P',
    '''SELECT DISTINCT P.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS P
WHERE (rel_connait0.eid_to=P.cw_eid OR rel_connait0.eid_from=P.cw_eid)'''
    ),
    
    ('Any X WHERE X connait P',
    '''SELECT DISTINCT X.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS X
WHERE (rel_connait0.eid_from=X.cw_eid OR rel_connait0.eid_to=X.cw_eid)'''
     ),
    
    ('Any P WHERE X eid 0, NOT X connait P',
     '''SELECT P.cw_eid
FROM cw_Personne AS P
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=P.cw_eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=P.cw_eid))'''),
    
    ('Any P WHERE NOT X connait P',
    '''SELECT P.cw_eid
FROM cw_Personne AS P
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_to=P.cw_eid OR rel_connait0.eid_from=P.cw_eid))'''),
    
    ('Any X WHERE NOT X connait P',
    '''SELECT X.cw_eid
FROM cw_Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_from=X.cw_eid OR rel_connait0.eid_to=X.cw_eid))'''),

    ('Any P WHERE X connait P, P nom "nom"',
     '''SELECT DISTINCT P.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS P
WHERE (rel_connait0.eid_to=P.cw_eid OR rel_connait0.eid_from=P.cw_eid) AND P.cw_nom=nom'''),
    
    ('Any X WHERE X connait P, P nom "nom"',
     '''SELECT DISTINCT X.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS P, cw_Personne AS X
WHERE (rel_connait0.eid_from=X.cw_eid AND rel_connait0.eid_to=P.cw_eid OR rel_connait0.eid_to=X.cw_eid AND rel_connait0.eid_from=P.cw_eid) AND P.cw_nom=nom'''
    ),

    ('Any X ORDERBY X DESC LIMIT 9 WHERE E eid 0, E connait X',
    '''SELECT DISTINCT X.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS X
WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=X.cw_eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=X.cw_eid)
ORDER BY 1 DESC
LIMIT 9'''
     ),

    ('DISTINCT Any P WHERE P connait S OR S connait P, S nom "chouette"',
     '''SELECT DISTINCT P.cw_eid
FROM connait_relation AS rel_connait0, cw_Personne AS P, cw_Personne AS S
WHERE (rel_connait0.eid_from=P.cw_eid AND rel_connait0.eid_to=S.cw_eid OR rel_connait0.eid_to=P.cw_eid AND rel_connait0.eid_from=S.cw_eid) AND S.cw_nom=chouette'''
     )
    ]

INLINE = [
    ('Any P, L WHERE N ecrit_par P, P nom L, N eid 0',
     '''SELECT P.cw_eid, P.cw_nom
FROM cw_Note AS N, cw_Personne AS P
WHERE N.cw_ecrit_par=P.cw_eid AND N.cw_eid=0'''),
    
    ('Any N WHERE NOT N ecrit_par P, P nom "toto"',
     '''SELECT DISTINCT N.cw_eid
FROM cw_Note AS N, cw_Personne AS P
WHERE (N.cw_ecrit_par IS NULL OR N.cw_ecrit_par!=P.cw_eid) AND P.cw_nom=toto'''),
    
    ('Any P WHERE N ecrit_par P, N eid 0',
    '''SELECT N.cw_ecrit_par
FROM cw_Note AS N
WHERE N.cw_ecrit_par IS NOT NULL AND N.cw_eid=0'''),

    ('Any P WHERE N ecrit_par P, P is Personne, N eid 0',
    '''SELECT P.cw_eid
FROM cw_Note AS N, cw_Personne AS P
WHERE N.cw_ecrit_par=P.cw_eid AND N.cw_eid=0'''),

    ('Any P WHERE NOT N ecrit_par P, P is Personne, N eid 512',
     '''SELECT DISTINCT P.cw_eid
FROM cw_Note AS N, cw_Personne AS P
WHERE (N.cw_ecrit_par IS NULL OR N.cw_ecrit_par!=P.cw_eid) AND N.cw_eid=512'''),

    ('Any S,ES,T WHERE S state_of ET, ET name "EUser", ES allowed_transition T, T destination_state S',
     '''SELECT T.cw_destination_state, rel_allowed_transition1.eid_from, T.cw_eid
FROM allowed_transition_relation AS rel_allowed_transition1, cw_EEType AS ET, cw_Transition AS T, state_of_relation AS rel_state_of0
WHERE T.cw_destination_state=rel_state_of0.eid_from AND rel_state_of0.eid_to=ET.cw_eid AND ET.cw_name=EUser AND rel_allowed_transition1.eid_to=T.cw_eid'''),
    ('Any O WHERE S eid 0, S in_state O',
     '''SELECT S.cw_in_state
FROM cw_Affaire AS S
WHERE S.cw_eid=0 AND S.cw_in_state IS NOT NULL
UNION ALL
SELECT S.cw_in_state
FROM cw_EUser AS S
WHERE S.cw_eid=0 AND S.cw_in_state IS NOT NULL
UNION ALL
SELECT S.cw_in_state
FROM cw_Note AS S
WHERE S.cw_eid=0 AND S.cw_in_state IS NOT NULL''')
    
    ]

INTERSECT = [
    ('Any SN WHERE NOT X in_state S, S name SN',
     '''SELECT DISTINCT S.cw_name
FROM cw_Affaire AS X, cw_State AS S
WHERE (X.cw_in_state IS NULL OR X.cw_in_state!=S.cw_eid)
INTERSECT
SELECT DISTINCT S.cw_name
FROM cw_EUser AS X, cw_State AS S
WHERE (X.cw_in_state IS NULL OR X.cw_in_state!=S.cw_eid)
INTERSECT
SELECT DISTINCT S.cw_name
FROM cw_Note AS X, cw_State AS S
WHERE (X.cw_in_state IS NULL OR X.cw_in_state!=S.cw_eid)'''),

    ('Any PN WHERE NOT X travaille S, X nom PN, S is IN(Division, Societe)',
     '''SELECT X.cw_nom
FROM cw_Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0,cw_Division AS S WHERE rel_travaille0.eid_from=X.cw_eid AND rel_travaille0.eid_to=S.cw_eid)
INTERSECT ALL
SELECT X.cw_nom
FROM cw_Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0,cw_Societe AS S WHERE rel_travaille0.eid_from=X.cw_eid AND rel_travaille0.eid_to=S.cw_eid)'''),
    
    ('Any PN WHERE NOT X travaille S, S nom PN, S is IN(Division, Societe)',
     '''SELECT S.cw_nom
FROM cw_Division AS S
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_to=S.cw_eid)
UNION ALL
SELECT S.cw_nom
FROM cw_Societe AS S
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_to=S.cw_eid)'''),
    
    ('Personne X WHERE NOT X travaille S, S nom "chouette"',
     '''SELECT X.cw_eid
FROM cw_Division AS S, cw_Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=X.cw_eid AND rel_travaille0.eid_to=S.cw_eid) AND S.cw_nom=chouette
UNION ALL
SELECT X.cw_eid
FROM cw_Personne AS X, cw_Societe AS S
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=X.cw_eid AND rel_travaille0.eid_to=S.cw_eid) AND S.cw_nom=chouette
UNION ALL
SELECT X.cw_eid
FROM cw_Personne AS X, cw_SubDivision AS S
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=X.cw_eid AND rel_travaille0.eid_to=S.cw_eid) AND S.cw_nom=chouette'''),
    
    ('Any X WHERE X is ET, ET eid 2',
     '''SELECT rel_is0.eid_from
FROM is_relation AS rel_is0
WHERE rel_is0.eid_to=2'''),

    ]
from logilab.common.adbh import ADV_FUNC_HELPER_DIRECTORY
    
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
    
    def _check(self, rql, sql, varmap=None):
        try:
            union = self._prepare(rql)
            r, args = self.o.generate(union, {'text': 'hip hop momo'},
                                      varmap=varmap)
            self.assertLinesEquals((r % args).strip(), self._norm_sql(sql))
        except Exception, ex:
            print rql
            if 'r' in locals():
                print (r%args).strip()
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
#         rqlst, solutions = self._prepare(rql)
#         for i, sol in enumerate(solutions):
#             try:
#                 r, args = self.o.generate([(rqlst, sol)])
#                 self.assertEqual((r.strip(), args), sqls[i])
#             except Exception, ex:
#                 print rql
#                 raise

    def test1(self):
        self._checkall('Any count(RDEF) WHERE RDEF relation_type X, X eid %(x)s',
                       ("""SELECT COUNT(T1.C0) FROM (SELECT RDEF.cw_eid AS C0
FROM cw_EFRDef AS RDEF
WHERE RDEF.cw_relation_type=%(x)s
UNION ALL
SELECT RDEF.cw_eid AS C0
FROM cw_ENFRDef AS RDEF
WHERE RDEF.cw_relation_type=%(x)s) AS T1""", {}),
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

    def test_varmap(self):
        self._check('Any X,L WHERE X is EUser, X in_group G, X login L, G name "users"',
                    '''SELECT T00.x, T00.l
FROM T00, cw_EGroup AS G, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=T00.x AND rel_in_group0.eid_to=G.cw_eid AND G.cw_name=users''',
                    varmap={'X': 'T00.x', 'X.login': 'T00.l'})
        self._check('Any X,L,GN WHERE X is EUser, X in_group G, X login L, G name GN',
                    '''SELECT T00.x, T00.l, G.cw_name
FROM T00, cw_EGroup AS G, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=T00.x AND rel_in_group0.eid_to=G.cw_eid''',
                    varmap={'X': 'T00.x', 'X.login': 'T00.l'})

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
             '''(SELECT X.cw_name
FROM cw_State AS X
ORDER BY 1)
UNION ALL
(SELECT XX.cw_name
FROM cw_Transition AS XX
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
FROM ((SELECT X.cw_name AS C0
FROM cw_State AS X)
UNION ALL
(SELECT XX.cw_name AS C0
FROM cw_Transition AS XX)) AS _T0
ORDER BY 1'''),
            
            ('Any N,NX ORDERBY NX WITH N,NX BEING '
             '((Any N,COUNT(X) GROUPBY N WHERE X name N, X is State HAVING COUNT(X)>1)'
             ' UNION '
             '(Any N,COUNT(X) GROUPBY N WHERE X name N, X is Transition HAVING COUNT(X)>1))',
             '''SELECT _T0.C0, _T0.C1
FROM ((SELECT X.cw_name AS C0, COUNT(X.cw_eid) AS C1
FROM cw_State AS X
GROUP BY X.cw_name
HAVING COUNT(X.cw_eid)>1)
UNION ALL
(SELECT X.cw_name AS C0, COUNT(X.cw_eid) AS C1
FROM cw_Transition AS X
GROUP BY X.cw_name
HAVING COUNT(X.cw_eid)>1)) AS _T0
ORDER BY 2'''),            

            ('Any N,COUNT(X) GROUPBY N HAVING COUNT(X)>1 '
             'WITH X, N BEING ((Any X, N WHERE X name N, X is State) UNION '
             '                 (Any X, N WHERE X name N, X is Transition))',
             '''SELECT _T0.C1, COUNT(_T0.C0)
FROM ((SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_State AS X)
UNION ALL
(SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_Transition AS X)) AS _T0
GROUP BY _T0.C1
HAVING COUNT(_T0.C0)>1'''),

            ('Any ETN,COUNT(X) GROUPBY ETN WHERE X is ET, ET name ETN '
             'WITH X BEING ((Any X WHERE X is Societe) UNION (Any X WHERE X is Affaire, (EXISTS(X owned_by 1)) OR ((EXISTS(D concerne B?, B owned_by 1, X identity D, B is Note)) OR (EXISTS(F concerne E?, E owned_by 1, E is Societe, X identity F)))))',
             '''SELECT ET.cw_name, COUNT(_T0.C0)
FROM ((SELECT X.cw_eid AS C0
FROM cw_Societe AS X)
UNION ALL
(SELECT X.cw_eid AS C0
FROM cw_Affaire AS X
WHERE ((EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE rel_owned_by0.eid_from=X.cw_eid AND rel_owned_by0.eid_to=1)) OR (((EXISTS(SELECT 1 FROM cw_Affaire AS D LEFT OUTER JOIN concerne_relation AS rel_concerne1 ON (rel_concerne1.eid_from=D.cw_eid) LEFT OUTER JOIN cw_Note AS B ON (rel_concerne1.eid_to=B.cw_eid), owned_by_relation AS rel_owned_by2 WHERE rel_owned_by2.eid_from=B.cw_eid AND rel_owned_by2.eid_to=1 AND X.cw_eid=D.cw_eid)) OR (EXISTS(SELECT 1 FROM cw_Affaire AS F LEFT OUTER JOIN concerne_relation AS rel_concerne3 ON (rel_concerne3.eid_from=F.cw_eid) LEFT OUTER JOIN cw_Societe AS E ON (rel_concerne3.eid_to=E.cw_eid), owned_by_relation AS rel_owned_by4 WHERE rel_owned_by4.eid_from=E.cw_eid AND rel_owned_by4.eid_to=1 AND X.cw_eid=F.cw_eid))))))) AS _T0, cw_EEType AS ET, is_relation AS rel_is0
WHERE rel_is0.eid_from=_T0.C0 AND rel_is0.eid_to=ET.cw_eid
GROUP BY ET.cw_name'''),
            )):
            yield t

            
    def test_subquery_error(self):
        rql = ('Any N WHERE X name N WITH X BEING '
               '((Any X WHERE X is State)'
               ' UNION '
               ' (Any X WHERE X is Transition))')
        rqlst = self._prepare(rql)
        self.assertRaises(BadRQLQuery, self.o.generate, rqlst)
            
    def test_symetric(self):
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
             """SELECT X.eid
FROM appears AS appears0, entities AS X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.eid AND X.type='Personne'"""),
            
            ('Personne X WHERE X has_text %(text)s',
             """SELECT X.eid
FROM appears AS appears0, entities AS X
WHERE appears0.words @@ to_tsquery('default', 'hip&hop&momo') AND appears0.uid=X.eid AND X.type='Personne'"""),
            
            ('Any X WHERE X has_text "toto tata", X name "tutu"',
             """SELECT X.cw_eid
FROM appears AS appears0, cw_Basket AS X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_File AS X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Folder AS X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Image AS X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_State AS X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Tag AS X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Transition AS X
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.cw_eid AND X.cw_name=tutu"""),

            ('Personne X where X has_text %(text)s, X travaille S, S has_text %(text)s',
             """SELECT X.eid
FROM appears AS appears0, appears AS appears2, entities AS X, travaille_relation AS rel_travaille1
WHERE appears0.words @@ to_tsquery('default', 'hip&hop&momo') AND appears0.uid=X.eid AND X.type='Personne' AND X.eid=rel_travaille1.eid_from AND appears2.uid=rel_travaille1.eid_to AND appears2.words @@ to_tsquery('default', 'hip&hop&momo')"""),
            )):
            yield t


    def test_from_clause_needed(self):
        queries = [("Any 1 WHERE EXISTS(T is EGroup, T name 'managers')",
                    '''SELECT 1
WHERE EXISTS(SELECT 1 FROM cw_EGroup AS T WHERE T.cw_name=managers)'''),
                   ('Any X,Y WHERE NOT X created_by Y, X eid 5, Y eid 6',
                    '''SELECT 5, 6
WHERE NOT EXISTS(SELECT 1 FROM created_by_relation AS rel_created_by0 WHERE rel_created_by0.eid_from=5 AND rel_created_by0.eid_to=6)'''),
                   ]
        for t in self._parse(queries):
            yield t

    def test_ambigous_exists_no_from_clause(self):
        self._check('Any COUNT(U) WHERE U eid 1, EXISTS (P owned_by U, P is IN (Note, Affaire))',
                    '''SELECT COUNT(1)
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, cw_Affaire AS P WHERE rel_owned_by0.eid_from=P.cw_eid AND rel_owned_by0.eid_to=1 UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, cw_Note AS P WHERE rel_owned_by1.eid_from=P.cw_eid AND rel_owned_by1.eid_to=1)''')


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
             '''SELECT X.cw_name
FROM cw_State AS X
ORDER BY 1
UNION ALL
SELECT XX.cw_name
FROM cw_Transition AS XX
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
FROM (SELECT X.cw_name AS C0
FROM cw_State AS X
UNION ALL
SELECT XX.cw_name AS C0
FROM cw_Transition AS XX) AS _T0
ORDER BY 1'''),
            
            ('Any N,NX ORDERBY NX WITH N,NX BEING '
             '((Any N,COUNT(X) GROUPBY N WHERE X name N, X is State HAVING COUNT(X)>1)'
             ' UNION '
             '(Any N,COUNT(X) GROUPBY N WHERE X name N, X is Transition HAVING COUNT(X)>1))',
             '''SELECT _T0.C0, _T0.C1
FROM (SELECT X.cw_name AS C0, COUNT(X.cw_eid) AS C1
FROM cw_State AS X
GROUP BY X.cw_name
HAVING COUNT(X.cw_eid)>1
UNION ALL
SELECT X.cw_name AS C0, COUNT(X.cw_eid) AS C1
FROM cw_Transition AS X
GROUP BY X.cw_name
HAVING COUNT(X.cw_eid)>1) AS _T0
ORDER BY 2'''),            

            ('Any N,COUNT(X) GROUPBY N HAVING COUNT(X)>1 '
             'WITH X, N BEING ((Any X, N WHERE X name N, X is State) UNION '
             '                 (Any X, N WHERE X name N, X is Transition))',
             '''SELECT _T0.C1, COUNT(_T0.C0)
FROM (SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_State AS X
UNION ALL
SELECT X.cw_eid AS C0, X.cw_name AS C1
FROM cw_Transition AS X) AS _T0
GROUP BY _T0.C1
HAVING COUNT(_T0.C0)>1'''),
            )):
            yield t
        
    def test_has_text(self):
        for t in self._parse((
            ('Any X WHERE X has_text "toto tata"',
             """SELECT appears0.uid
FROM appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata'))"""),
            
            ('Any X WHERE X has_text %(text)s',
             """SELECT appears0.uid
FROM appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('hip', 'hop', 'momo'))"""),
            
            ('Personne X WHERE X has_text "toto tata"',
             """SELECT X.eid
FROM appears AS appears0, entities AS X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.eid AND X.type='Personne'"""),
            
            ('Any X WHERE X has_text "toto tata", X name "tutu"',
             """SELECT X.cw_eid
FROM appears AS appears0, cw_Basket AS X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_File AS X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Folder AS X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Image AS X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_State AS X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Tag AS X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Transition AS X
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.cw_eid AND X.cw_name=tutu"""),
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
        return sql.strip().replace(' ILIKE ', ' LIKE ')

    def test_from_clause_needed(self):
        queries = [("Any 1 WHERE EXISTS(T is EGroup, T name 'managers')",
                    '''SELECT 1
FROM (SELECT 1) AS _T
WHERE EXISTS(SELECT 1 FROM cw_EGroup AS T WHERE T.cw_name=managers)'''),
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
             """SELECT X.eid
FROM appears AS appears0, entities AS X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.type='Personne'"""),
            ('Personne X WHERE X has_text %(text)s',
             """SELECT X.eid
FROM appears AS appears0, entities AS X
WHERE MATCH (appears0.words) AGAINST ('hip hop momo' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.type='Personne'"""),
            ('Any X WHERE X has_text "toto tata", X name "tutu"',
             """SELECT X.cw_eid
FROM appears AS appears0, cw_Basket AS X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_File AS X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Folder AS X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Image AS X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_State AS X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Tag AS X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.cw_eid AND X.cw_name=tutu
UNION ALL
SELECT X.cw_eid
FROM appears AS appears0, cw_Transition AS X
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.cw_eid AND X.cw_name=tutu""")
            ]
        for t in self._parse(queries):
            yield t
                             

    def test_ambigous_exists_no_from_clause(self):
        self._check('Any COUNT(U) WHERE U eid 1, EXISTS (P owned_by U, P is IN (Note, Affaire))',
                    '''SELECT COUNT(1)
FROM (SELECT 1) AS _T
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, cw_Affaire AS P WHERE rel_owned_by0.eid_from=P.cw_eid AND rel_owned_by0.eid_to=1 UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, cw_Note AS P WHERE rel_owned_by1.eid_from=P.cw_eid AND rel_owned_by1.eid_to=1)''') 
           

        

if __name__ == '__main__':
    unittest_main()
