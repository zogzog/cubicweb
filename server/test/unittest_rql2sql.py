"""unit tests for module cubicweb.server.sources.rql2sql"""

import sys
from mx.DateTime import today

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
     '''SELECT P.eid
FROM Personne AS P
WHERE P.nom=Zig\'oto'''),

    (r'Personne P WHERE P nom ~= "Zig\"oto%";',
     '''SELECT P.eid
FROM Personne AS P
WHERE P.nom ILIKE Zig"oto%'''),
    ]

BASIC = [
    
    ("Any X WHERE X is Affaire",
     '''SELECT X.eid
FROM Affaire AS X'''),
    
    ("Any X WHERE X eid 0",
     '''SELECT 0'''),
    
    ("Personne P",
     '''SELECT P.eid
FROM Personne AS P'''),

    ("Personne P WHERE P test TRUE",
     '''SELECT P.eid
FROM Personne AS P
WHERE P.test=True'''),

    ("Personne P WHERE P test false",
     '''SELECT P.eid
FROM Personne AS P
WHERE P.test=False'''),

    ("Personne P WHERE P eid -1",
     '''SELECT -1'''),

    ("Personne P LIMIT 20 OFFSET 10",
     '''SELECT P.eid
FROM Personne AS P
LIMIT 20
OFFSET 10'''),

    ("Personne P WHERE S is Societe, P travaille S, S nom 'Logilab';",
     '''SELECT rel_travaille0.eid_from
FROM Societe AS S, travaille_relation AS rel_travaille0
WHERE rel_travaille0.eid_to=S.eid AND S.nom=Logilab'''),

    ("Personne P WHERE P concerne A, A concerne S, S nom 'Logilab', S is Societe;",
     '''SELECT rel_concerne0.eid_from
FROM Societe AS S, concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1
WHERE rel_concerne0.eid_to=rel_concerne1.eid_from AND rel_concerne1.eid_to=S.eid AND S.nom=Logilab'''),

    ("Note N WHERE X evaluee N, X nom 'Logilab';",
     '''SELECT rel_evaluee0.eid_to
FROM Division AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.eid AND X.nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM Personne AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.eid AND X.nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM Societe AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.eid AND X.nom=Logilab
UNION ALL
SELECT rel_evaluee0.eid_to
FROM SubDivision AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.eid AND X.nom=Logilab'''),

    ("Note N WHERE X evaluee N, X nom in ('Logilab', 'Caesium');",
     '''SELECT rel_evaluee0.eid_to
FROM Division AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.eid AND X.nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM Personne AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.eid AND X.nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM Societe AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.eid AND X.nom IN(Logilab, Caesium)
UNION ALL
SELECT rel_evaluee0.eid_to
FROM SubDivision AS X, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=X.eid AND X.nom IN(Logilab, Caesium)'''),

    ("Any X WHERE X creation_date TODAY, X is Affaire",
     '''SELECT X.eid
FROM Affaire AS X
WHERE DATE(X.creation_date)=CURRENT_DATE'''),

    ("Any N WHERE G is EGroup, G name N, E eid 12, E read_permission G",
     '''SELECT G.name
FROM EGroup AS G, read_permission_relation AS rel_read_permission0
WHERE rel_read_permission0.eid_from=12 AND rel_read_permission0.eid_to=G.eid'''),

    ('Any Y WHERE U login "admin", U login Y', # stupid but valid...
     """SELECT U.login
FROM EUser AS U
WHERE U.login=admin"""),

    ('Any T WHERE T tags X, X is State',
     '''SELECT rel_tags0.eid_from
FROM State AS X, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=X.eid'''),

    ('Any X,Y WHERE X eid 0, Y eid 1, X concerne Y',
     '''SELECT 0, 1
FROM concerne_relation AS rel_concerne0
WHERE rel_concerne0.eid_from=0 AND rel_concerne0.eid_to=1'''),

    ("Any X WHERE X prenom 'lulu',"
     "EXISTS(X owned_by U, U in_group G, G name 'lulufanclub' OR G name 'managers');",
     '''SELECT X.eid
FROM Personne AS X
WHERE X.prenom=lulu AND EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, in_group_relation AS rel_in_group1, EGroup AS G WHERE rel_owned_by0.eid_from=X.eid AND rel_in_group1.eid_from=rel_owned_by0.eid_to AND rel_in_group1.eid_to=G.eid AND ((G.name=lulufanclub) OR (G.name=managers)))'''),

    ("Any X WHERE X prenom 'lulu',"
     "NOT EXISTS(X owned_by U, U in_group G, G name 'lulufanclub' OR G name 'managers');",
     '''SELECT X.eid
FROM Personne AS X
WHERE X.prenom=lulu AND NOT EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, in_group_relation AS rel_in_group1, EGroup AS G WHERE rel_owned_by0.eid_from=X.eid AND rel_in_group1.eid_from=rel_owned_by0.eid_to AND rel_in_group1.eid_to=G.eid AND ((G.name=lulufanclub) OR (G.name=managers)))'''),
]

ADVANCED= [
    ('Any X WHERE X is ET, ET eid 2',
     '''SELECT rel_is0.eid_from
FROM is_relation AS rel_is0
WHERE rel_is0.eid_to=2'''),


    ("Societe S WHERE S nom 'Logilab' OR S nom 'Caesium'",
     '''SELECT S.eid
FROM Societe AS S
WHERE ((S.nom=Logilab) OR (S.nom=Caesium))'''),
    
    ('Any X WHERE X nom "toto", X eid IN (9700, 9710, 1045, 674)',
    '''SELECT X.eid
FROM Division AS X
WHERE X.nom=toto AND X.eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT X.eid
FROM Personne AS X
WHERE X.nom=toto AND X.eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT X.eid
FROM Societe AS X
WHERE X.nom=toto AND X.eid IN(9700, 9710, 1045, 674)
UNION ALL
SELECT X.eid
FROM SubDivision AS X
WHERE X.nom=toto AND X.eid IN(9700, 9710, 1045, 674)'''),

    ('Any Y, COUNT(N) GROUPBY Y WHERE Y evaluee N;',
     '''SELECT rel_evaluee0.eid_from, COUNT(rel_evaluee0.eid_to)
FROM evaluee_relation AS rel_evaluee0
GROUP BY rel_evaluee0.eid_from'''),

    ("Any X WHERE X concerne B or C concerne X",
     '''SELECT X.eid
FROM Affaire AS X, concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1
WHERE ((rel_concerne0.eid_from=X.eid) OR (rel_concerne1.eid_to=X.eid))'''),

    ("Any X WHERE X travaille S or X concerne A",
     '''SELECT X.eid
FROM Personne AS X, concerne_relation AS rel_concerne1, travaille_relation AS rel_travaille0
WHERE ((rel_travaille0.eid_from=X.eid) OR (rel_concerne1.eid_from=X.eid))'''),

    ("Any N WHERE A evaluee N or N ecrit_par P",
     '''SELECT N.eid
FROM Note AS N, evaluee_relation AS rel_evaluee0
WHERE ((rel_evaluee0.eid_to=N.eid) OR (N.ecrit_par IS NOT NULL))'''),

    ("Any N WHERE A evaluee N or EXISTS(N todo_by U)",
     '''SELECT N.eid
FROM Note AS N, evaluee_relation AS rel_evaluee0
WHERE ((rel_evaluee0.eid_to=N.eid) OR (EXISTS(SELECT 1 FROM todo_by_relation AS rel_todo_by1 WHERE rel_todo_by1.eid_from=N.eid)))'''),

    ("Any N WHERE A evaluee N or N todo_by U",
     '''SELECT N.eid
FROM Note AS N, evaluee_relation AS rel_evaluee0, todo_by_relation AS rel_todo_by1
WHERE ((rel_evaluee0.eid_to=N.eid) OR (rel_todo_by1.eid_from=N.eid))'''),
    
    ("Any X WHERE X concerne B or C concerne X, B eid 12, C eid 13",
     '''SELECT X.eid
FROM Affaire AS X, concerne_relation AS rel_concerne0, concerne_relation AS rel_concerne1
WHERE ((rel_concerne0.eid_from=X.eid AND rel_concerne0.eid_to=12) OR (rel_concerne1.eid_from=13 AND rel_concerne1.eid_to=X.eid))'''),

    ('Any X WHERE X created_by U, X concerne B OR C concerne X, B eid 12, C eid 13',
     '''SELECT rel_created_by0.eid_from
FROM concerne_relation AS rel_concerne1, concerne_relation AS rel_concerne2, created_by_relation AS rel_created_by0
WHERE ((rel_concerne1.eid_from=rel_created_by0.eid_from AND rel_concerne1.eid_to=12) OR (rel_concerne2.eid_from=13 AND rel_concerne2.eid_to=rel_created_by0.eid_from))'''),

    ('Any P WHERE P travaille_subdivision S1 OR P travaille_subdivision S2, S1 nom "logilab", S2 nom "caesium"',
     '''SELECT P.eid
FROM Personne AS P, SubDivision AS S1, SubDivision AS S2, travaille_subdivision_relation AS rel_travaille_subdivision0, travaille_subdivision_relation AS rel_travaille_subdivision1
WHERE ((rel_travaille_subdivision0.eid_from=P.eid AND rel_travaille_subdivision0.eid_to=S1.eid) OR (rel_travaille_subdivision1.eid_from=P.eid AND rel_travaille_subdivision1.eid_to=S2.eid)) AND S1.nom=logilab AND S2.nom=caesium'''),

    ('Any X WHERE T tags X',
     '''SELECT rel_tags0.eid_to
FROM tags_relation AS rel_tags0'''),
    
    ('Any X WHERE X in_basket B, B eid 12',
     '''SELECT rel_in_basket0.eid_from
FROM in_basket_relation AS rel_in_basket0
WHERE rel_in_basket0.eid_to=12'''),
    
    ('Any SEN,RN,OEN WHERE X from_entity SE, SE eid 44, X relation_type R, R eid 139, X to_entity OE, OE eid 42, R name RN, SE name SEN, OE name OEN',
     '''SELECT SE.name, R.name, OE.name
FROM EEType AS OE, EEType AS SE, EFRDef AS X, ERType AS R
WHERE X.from_entity=44 AND SE.eid=44 AND X.relation_type=139 AND R.eid=139 AND X.to_entity=42 AND OE.eid=42
UNION ALL
SELECT SE.name, R.name, OE.name
FROM EEType AS OE, EEType AS SE, ENFRDef AS X, ERType AS R
WHERE X.from_entity=44 AND SE.eid=44 AND X.relation_type=139 AND R.eid=139 AND X.to_entity=42 AND OE.eid=42'''),

    # Any O WHERE NOT S corrected_in O, S eid %(x)s, S concerns P, O version_of P, O in_state ST, NOT ST name "published", O modification_date MTIME ORDERBY MTIME DESC LIMIT 9
    ('Any O WHERE NOT S ecrit_par O, S eid 1, S inline1 P, O inline2 P',
     '''SELECT DISTINCT O.eid
FROM Note AS S, Personne AS O
WHERE (S.ecrit_par IS NULL OR S.ecrit_par!=O.eid) AND S.eid=1 AND O.inline2=S.inline1'''),

    ('DISTINCT Any S ORDERBY stockproc(SI) WHERE NOT S ecrit_par O, S para SI',
     '''SELECT T1.C0 FROM (SELECT DISTINCT S.eid AS C0, STOCKPROC(S.para) AS C1
FROM Note AS S
WHERE S.ecrit_par IS NULL
ORDER BY 2) AS T1'''),

    ('Any N WHERE N todo_by U, N is Note, U eid 2, N filed_under T, T eid 3',
     # N would actually be invarient if U eid 2 had given a specific type to U
     '''SELECT N.eid
FROM Note AS N, filed_under_relation AS rel_filed_under1, todo_by_relation AS rel_todo_by0
WHERE rel_todo_by0.eid_from=N.eid AND rel_todo_by0.eid_to=2 AND rel_filed_under1.eid_from=N.eid AND rel_filed_under1.eid_to=3'''),

    ('Any N WHERE N todo_by U, U eid 2, P evaluee N, P eid 3',
     '''SELECT rel_evaluee1.eid_to
FROM evaluee_relation AS rel_evaluee1, todo_by_relation AS rel_todo_by0
WHERE rel_evaluee1.eid_to=rel_todo_by0.eid_from AND rel_todo_by0.eid_to=2 AND rel_evaluee1.eid_from=3'''),

    
    (' Any X,U WHERE C owned_by U, NOT X owned_by U, C eid 1, X eid 2',
     '''SELECT 2, rel_owned_by0.eid_to
FROM owned_by_relation AS rel_owned_by0
WHERE rel_owned_by0.eid_from=1 AND NOT EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by1 WHERE rel_owned_by1.eid_from=2 AND rel_owned_by0.eid_to=rel_owned_by1.eid_to)'''),

    ('Any GN WHERE X in_group G, G name GN, (G name "managers" OR EXISTS(X copain T, T login in ("comme", "cochon")))',
     '''SELECT G.name
FROM EGroup AS G, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_to=G.eid AND ((G.name=managers) OR (EXISTS(SELECT 1 FROM copain_relation AS rel_copain1, EUser AS T WHERE rel_copain1.eid_from=rel_in_group0.eid_from AND rel_copain1.eid_to=T.eid AND T.login IN(comme, cochon))))'''),

    ('Any C WHERE C is Card, EXISTS(X documented_by C)',
      """SELECT C.eid
FROM Card AS C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_to=C.eid)"""),
    
    ('Any C WHERE C is Card, EXISTS(X documented_by C, X eid 12)',
      """SELECT C.eid
FROM Card AS C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_from=12 AND rel_documented_by0.eid_to=C.eid)"""),

    ('Any T WHERE C is Card, C title T, EXISTS(X documented_by C, X eid 12)',
      """SELECT C.title
FROM Card AS C
WHERE EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by0 WHERE rel_documented_by0.eid_from=12 AND rel_documented_by0.eid_to=C.eid)"""),

    ('Any GN,L WHERE X in_group G, X login L, G name GN, EXISTS(X copain T, T login L, T login IN("comme", "cochon"))',
     '''SELECT G.name, X.login
FROM EGroup AS G, EUser AS X, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=X.eid AND rel_in_group0.eid_to=G.eid AND EXISTS(SELECT 1 FROM copain_relation AS rel_copain1, EUser AS T WHERE rel_copain1.eid_from=X.eid AND rel_copain1.eid_to=T.eid AND T.login=X.login AND T.login IN(comme, cochon))'''),

    ('Any X,S, MAX(T) GROUPBY X,S ORDERBY S WHERE X is EUser, T tags X, S eid IN(32), X in_state S',
     '''SELECT X.eid, 32, MAX(rel_tags0.eid_from)
FROM EUser AS X, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=X.eid AND X.in_state=32
GROUP BY X.eid'''),

    ('Any COUNT(S),CS GROUPBY CS ORDERBY 1 DESC LIMIT 10 WHERE S is Affaire, C is Societe, S concerne C, C nom CS, (EXISTS(S owned_by 1)) OR (EXISTS(S documented_by N, N title "published"))',
     '''SELECT COUNT(rel_concerne0.eid_from), C.nom
FROM Societe AS C, concerne_relation AS rel_concerne0
WHERE rel_concerne0.eid_to=C.eid AND ((EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by1 WHERE rel_concerne0.eid_from=rel_owned_by1.eid_from AND rel_owned_by1.eid_to=1)) OR (EXISTS(SELECT 1 FROM documented_by_relation AS rel_documented_by2, Card AS N WHERE rel_concerne0.eid_from=rel_documented_by2.eid_from AND rel_documented_by2.eid_to=N.eid AND N.title=published)))
GROUP BY C.nom
ORDER BY 1 DESC
LIMIT 10'''),

    ('Any X WHERE Y evaluee X, Y is EUser',
     '''SELECT rel_evaluee0.eid_to
FROM EUser AS Y, evaluee_relation AS rel_evaluee0
WHERE rel_evaluee0.eid_from=Y.eid'''),

    ('Any L WHERE X login "admin", X identity Y, Y login L',
     '''SELECT Y.login
FROM EUser AS X, EUser AS Y
WHERE X.login=admin AND X.eid=Y.eid'''),

    ('Any L WHERE X login "admin", NOT X identity Y, Y login L',
     '''SELECT Y.login
FROM EUser AS X, EUser AS Y
WHERE X.login=admin AND NOT X.eid=Y.eid'''),
    
    ('Any L WHERE X login "admin", X identity Y?, Y login L',
     '''SELECT Y.login
FROM EUser AS X LEFT OUTER JOIN EUser AS Y ON (X.eid=Y.eid)
WHERE X.login=admin'''),

    ('Any XN ORDERBY XN WHERE X name XN',
     '''SELECT X.name
FROM Basket AS X
UNION ALL
SELECT X.name
FROM ECache AS X
UNION ALL
SELECT X.name
FROM EConstraintType AS X
UNION ALL
SELECT X.name
FROM EEType AS X
UNION ALL
SELECT X.name
FROM EGroup AS X
UNION ALL
SELECT X.name
FROM EPermission AS X
UNION ALL
SELECT X.name
FROM ERType AS X
UNION ALL
SELECT X.name
FROM File AS X
UNION ALL
SELECT X.name
FROM Folder AS X
UNION ALL
SELECT X.name
FROM Image AS X
UNION ALL
SELECT X.name
FROM State AS X
UNION ALL
SELECT X.name
FROM Tag AS X
UNION ALL
SELECT X.name
FROM Transition AS X
ORDER BY 1'''),

#    ('Any XN WHERE X name XN GROUPBY XN',
#     ''''''),
#    ('Any XN, COUNT(X) WHERE X name XN GROUPBY XN',
#     ''''''),

    # DISTINCT, can use relatin under exists scope as principal
    ('DISTINCT Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), EXISTS(X read_permission Y)',
     '''SELECT DISTINCT X.eid, rel_read_permission0.eid_to
FROM EEType AS X, read_permission_relation AS rel_read_permission0
WHERE X.name=EGroup AND rel_read_permission0.eid_to IN(1, 2, 3) AND EXISTS(SELECT 1 WHERE rel_read_permission0.eid_from=X.eid)
UNION
SELECT DISTINCT X.eid, rel_read_permission0.eid_to
FROM ERType AS X, read_permission_relation AS rel_read_permission0
WHERE X.name=EGroup AND rel_read_permission0.eid_to IN(1, 2, 3) AND EXISTS(SELECT 1 WHERE rel_read_permission0.eid_from=X.eid)'''),

    # no distinct, Y can't be invariant
    ('Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), EXISTS(X read_permission Y)',
     '''SELECT X.eid, Y.eid
FROM EEType AS X, EGroup AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION ALL
SELECT X.eid, Y.eid
FROM EEType AS X, RQLExpression AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION ALL
SELECT X.eid, Y.eid
FROM EGroup AS Y, ERType AS X
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION ALL
SELECT X.eid, Y.eid
FROM ERType AS X, RQLExpression AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)'''),

    # DISTINCT but NEGED exists, can't be invariant
    ('DISTINCT Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), NOT EXISTS(X read_permission Y)',
     '''SELECT DISTINCT X.eid, Y.eid
FROM EEType AS X, EGroup AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION
SELECT DISTINCT X.eid, Y.eid
FROM EEType AS X, RQLExpression AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION
SELECT DISTINCT X.eid, Y.eid
FROM EGroup AS Y, ERType AS X
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION
SELECT DISTINCT X.eid, Y.eid
FROM ERType AS X, RQLExpression AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)'''),

    # should generate the same query as above
    ('DISTINCT Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), NOT X read_permission Y',
     '''SELECT DISTINCT X.eid, Y.eid
FROM EEType AS X, EGroup AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION
SELECT DISTINCT X.eid, Y.eid
FROM EEType AS X, RQLExpression AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION
SELECT DISTINCT X.eid, Y.eid
FROM EGroup AS Y, ERType AS X
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION
SELECT DISTINCT X.eid, Y.eid
FROM ERType AS X, RQLExpression AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)'''),
    
    # neged relation, can't be inveriant
    ('Any X,Y WHERE X name "EGroup", Y eid IN(1, 2, 3), NOT X read_permission Y',
     '''SELECT X.eid, Y.eid
FROM EEType AS X, EGroup AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION ALL
SELECT X.eid, Y.eid
FROM EEType AS X, RQLExpression AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION ALL
SELECT X.eid, Y.eid
FROM EGroup AS Y, ERType AS X
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)
UNION ALL
SELECT X.eid, Y.eid
FROM ERType AS X, RQLExpression AS Y
WHERE X.name=EGroup AND Y.eid IN(1, 2, 3) AND NOT EXISTS(SELECT 1 FROM read_permission_relation AS rel_read_permission0 WHERE rel_read_permission0.eid_from=X.eid AND rel_read_permission0.eid_to=Y.eid)'''),

    ('Any MAX(X)+MIN(X), N GROUPBY N WHERE X name N;',
     '''SELECT (MAX(T1.C0) + MIN(T1.C0)), T1.C1 FROM (SELECT X.eid AS C0, X.name AS C1
FROM Basket AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM ECache AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM EConstraintType AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM EEType AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM EGroup AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM EPermission AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM ERType AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM File AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM Folder AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM Image AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM State AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM Tag AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM Transition AS X) AS T1
GROUP BY T1.C1'''),
    
    ('Any MAX(X)+MIN(LENGTH(D)), N GROUPBY N ORDERBY 1, N, DF WHERE X name N, X data D, X data_format DF;',
     '''SELECT (MAX(T1.C1) + MIN(LENGTH(T1.C0))), T1.C2 FROM (SELECT X.data AS C0, X.eid AS C1, X.name AS C2, X.data_format AS C3
FROM File AS X
UNION ALL
SELECT X.data AS C0, X.eid AS C1, X.name AS C2, X.data_format AS C3
FROM Image AS X) AS T1
GROUP BY T1.C2
ORDER BY 1,2,T1.C3'''),

    ('DISTINCT Any S ORDERBY R WHERE A is Affaire, A sujet S, A ref R',
     '''SELECT T1.C0 FROM (SELECT DISTINCT A.sujet AS C0, A.ref AS C1
FROM Affaire AS A
ORDER BY 2) AS T1'''),
    
    ('DISTINCT Any MAX(X)+MIN(LENGTH(D)), N GROUPBY N ORDERBY 2, DF WHERE X name N, X data D, X data_format DF;',
     '''SELECT T1.C0,T1.C1 FROM (SELECT DISTINCT (MAX(T1.C1) + MIN(LENGTH(T1.C0))) AS C0, T1.C2 AS C1, T1.C3 AS C2 FROM (SELECT DISTINCT X.data AS C0, X.eid AS C1, X.name AS C2, X.data_format AS C3
FROM File AS X
UNION
SELECT DISTINCT X.data AS C0, X.eid AS C1, X.name AS C2, X.data_format AS C3
FROM Image AS X) AS T1
GROUP BY T1.C2,T1.C3
ORDER BY 2,3) AS T1
'''),

    # ambiguity in EXISTS() -> should union the sub-query
    ('Any T WHERE T is Tag, NOT T name in ("t1", "t2"), EXISTS(T tags X, X is IN (EUser, EGroup))',
     '''SELECT T.eid
FROM Tag AS T
WHERE NOT (T.name IN(t1, t2)) AND EXISTS(SELECT 1 FROM tags_relation AS rel_tags0, EGroup AS X WHERE rel_tags0.eid_from=T.eid AND rel_tags0.eid_to=X.eid UNION SELECT 1 FROM tags_relation AS rel_tags1, EUser AS X WHERE rel_tags1.eid_from=T.eid AND rel_tags1.eid_to=X.eid)'''),

    # must not use a relation in EXISTS scope to inline a variable 
    ('Any U WHERE U eid IN (1,2), EXISTS(X owned_by U)',
     '''SELECT U.eid
FROM EUser AS U
WHERE U.eid IN(1, 2) AND EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE rel_owned_by0.eid_to=U.eid)'''),

    ('Any U WHERE EXISTS(U eid IN (1,2), X owned_by U)',
     '''SELECT U.eid
FROM EUser AS U
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE U.eid IN(1, 2) AND rel_owned_by0.eid_to=U.eid)'''),

    ('Any COUNT(U) WHERE EXISTS (P owned_by U, P is IN (Note, Affaire))',
     '''SELECT COUNT(U.eid)
FROM EUser AS U
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, Affaire AS P WHERE rel_owned_by0.eid_from=P.eid AND rel_owned_by0.eid_to=U.eid UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, Note AS P WHERE rel_owned_by1.eid_from=P.eid AND rel_owned_by1.eid_to=U.eid)'''),

    ('Any MAX(X)',
     '''SELECT MAX(X.eid)
FROM entities AS X'''),

    ('Any MAX(X) WHERE X is Note',
     '''SELECT MAX(X.eid)
FROM Note AS X'''),
    
    ('Any X WHERE X eid > 12',
     '''SELECT X.eid
FROM entities AS X
WHERE X.eid>12'''),
    
    ('Any X WHERE X eid > 12, X is Note',
     """SELECT X.eid
FROM entities AS X
WHERE X.type='Note' AND X.eid>12"""),
    
    ('Any X, T WHERE X eid > 12, X title T',
     """SELECT X.eid, X.title
FROM Bookmark AS X
WHERE X.eid>12
UNION ALL
SELECT X.eid, X.title
FROM Card AS X
WHERE X.eid>12
UNION ALL
SELECT X.eid, X.title
FROM EmailThread AS X
WHERE X.eid>12"""),

    ('Any X',
     '''SELECT X.eid
FROM entities AS X'''),

    ('Any X GROUPBY X WHERE X eid 12',
     '''SELECT 12'''),
    
    ('Any X GROUPBY X ORDERBY Y WHERE X eid 12, X login Y',
     '''SELECT X.eid
FROM EUser AS X
WHERE X.eid=12
GROUP BY X.eid
ORDER BY X.login'''),
    
    ('Any U,COUNT(X) GROUPBY U WHERE U eid 12, X owned_by U HAVING COUNT(X) > 10',
     '''SELECT rel_owned_by0.eid_to, COUNT(rel_owned_by0.eid_from)
FROM owned_by_relation AS rel_owned_by0
WHERE rel_owned_by0.eid_to=12
GROUP BY rel_owned_by0.eid_to
HAVING COUNT(rel_owned_by0.eid_from)>10'''),

    ('DISTINCT Any X ORDERBY stockproc(X) WHERE U login X',
     '''SELECT T1.C0 FROM (SELECT DISTINCT U.login AS C0, STOCKPROC(U.login) AS C1
FROM EUser AS U
ORDER BY 2) AS T1'''),
    
    ('DISTINCT Any X ORDERBY Y WHERE B bookmarked_by X, X login Y',
     '''SELECT T1.C0 FROM (SELECT DISTINCT X.eid AS C0, X.login AS C1
FROM EUser AS X, bookmarked_by_relation AS rel_bookmarked_by0
WHERE rel_bookmarked_by0.eid_to=X.eid
ORDER BY 2) AS T1'''),

    ('DISTINCT Any X ORDERBY SN WHERE X in_state S, S name SN',
     '''SELECT T1.C0 FROM (SELECT DISTINCT X.eid AS C0, S.name AS C1
FROM Affaire AS X, State AS S
WHERE X.in_state=S.eid
UNION
SELECT DISTINCT X.eid AS C0, S.name AS C1
FROM EUser AS X, State AS S
WHERE X.in_state=S.eid
UNION
SELECT DISTINCT X.eid AS C0, S.name AS C1
FROM Note AS X, State AS S
WHERE X.in_state=S.eid
ORDER BY 2) AS T1'''),

    ]

MULTIPLE_SEL = [
    ("DISTINCT Any X,Y where P is Personne, P nom X , P prenom Y;",
     '''SELECT DISTINCT P.nom, P.prenom
FROM Personne AS P'''),
    ("Any X,Y where P is Personne, P nom X , P prenom Y, not P nom NULL;",
     '''SELECT P.nom, P.prenom
FROM Personne AS P
WHERE NOT (P.nom IS NULL)'''),
    ("Personne X,Y where X nom NX, Y nom NX, X eid XE, not Y eid XE",
     '''SELECT X.eid, Y.eid
FROM Personne AS X, Personne AS Y
WHERE Y.nom=X.nom AND NOT (Y.eid=X.eid)''')
    ]

NEGATIONS = [
    ("Personne X WHERE NOT X evaluee Y;",
     '''SELECT X.eid
FROM Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=X.eid)'''),
    
    ("Note N WHERE NOT X evaluee N, X eid 0",
     '''SELECT N.eid
FROM Note AS N
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=0 AND rel_evaluee0.eid_to=N.eid)'''),
    
    ('Any X WHERE NOT X travaille S, X is Personne',
     '''SELECT X.eid
FROM Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM travaille_relation AS rel_travaille0 WHERE rel_travaille0.eid_from=X.eid)'''),
    
    ("Personne P where not P datenaiss TODAY",
     '''SELECT P.eid
FROM Personne AS P
WHERE NOT (DATE(P.datenaiss)=CURRENT_DATE)'''),
    
    ("Personne P where NOT P concerne A",
     '''SELECT P.eid
FROM Personne AS P
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_from=P.eid)'''),
    
    ("Affaire A where not P concerne A",
     '''SELECT A.eid
FROM Affaire AS A
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_to=A.eid)'''),
    ("Personne P where not P concerne A, A sujet ~= 'TEST%'",
     '''SELECT P.eid
FROM Affaire AS A, Personne AS P
WHERE NOT EXISTS(SELECT 1 FROM concerne_relation AS rel_concerne0 WHERE rel_concerne0.eid_from=P.eid AND rel_concerne0.eid_to=A.eid) AND A.sujet ILIKE TEST%'''),

    ('Any S WHERE NOT T eid 28258, T tags S',
     '''SELECT rel_tags0.eid_to
FROM tags_relation AS rel_tags0
WHERE NOT (rel_tags0.eid_from=28258)'''),
    
    ('Any S WHERE T is Tag, T name TN, NOT T eid 28258, T tags S, S name SN',
     '''SELECT S.eid
FROM EGroup AS S, Tag AS T, tags_relation AS rel_tags0
WHERE NOT (T.eid=28258) AND rel_tags0.eid_from=T.eid AND rel_tags0.eid_to=S.eid
UNION ALL
SELECT S.eid
FROM State AS S, Tag AS T, tags_relation AS rel_tags0
WHERE NOT (T.eid=28258) AND rel_tags0.eid_from=T.eid AND rel_tags0.eid_to=S.eid
UNION ALL
SELECT S.eid
FROM Tag AS S, Tag AS T, tags_relation AS rel_tags0
WHERE NOT (T.eid=28258) AND rel_tags0.eid_from=T.eid AND rel_tags0.eid_to=S.eid'''),

    
    ('Any X,Y WHERE X created_by Y, X eid 5, NOT Y eid 6',
     '''SELECT 5, rel_created_by0.eid_to
FROM created_by_relation AS rel_created_by0
WHERE rel_created_by0.eid_from=5 AND NOT (rel_created_by0.eid_to=6)'''),

    ('Note X WHERE NOT Y evaluee X',
     '''SELECT X.eid
FROM Note AS X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_to=X.eid)'''),

    ('Any Y WHERE NOT Y evaluee X',
     '''SELECT Y.eid
FROM Division AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.eid)
UNION ALL
SELECT Y.eid
FROM EUser AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.eid)
UNION ALL
SELECT Y.eid
FROM Personne AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.eid)
UNION ALL
SELECT Y.eid
FROM Societe AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.eid)
UNION ALL
SELECT Y.eid
FROM SubDivision AS Y
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0 WHERE rel_evaluee0.eid_from=Y.eid)'''),

    ('Any X WHERE NOT Y evaluee X, Y is EUser',
     '''SELECT X.eid
FROM Note AS X
WHERE NOT EXISTS(SELECT 1 FROM evaluee_relation AS rel_evaluee0,EUser AS Y WHERE rel_evaluee0.eid_from=Y.eid AND rel_evaluee0.eid_to=X.eid)'''),
    
    ('Any X,T WHERE X title T, NOT X is Bookmark',
     '''SELECT DISTINCT X.eid, X.title
FROM Card AS X
UNION
SELECT DISTINCT X.eid, X.title
FROM EmailThread AS X'''),

    ('Any K,V WHERE P is EProperty, P pkey K, P value V, NOT P for_user U',
     '''SELECT DISTINCT P.pkey, P.value
FROM EProperty AS P
WHERE P.for_user IS NULL'''),

    ('Any S WHERE NOT X in_state S, X is IN(Affaire, EUser)',
     '''SELECT S.eid
FROM Affaire AS X, State AS S
WHERE (X.in_state IS NULL OR X.in_state!=S.eid)
INTERSECT
SELECT S.eid
FROM EUser AS X, State AS S
WHERE (X.in_state IS NULL OR X.in_state!=S.eid)'''),
    ]

OUTER_JOIN = [
    ('Any X,S WHERE X travaille S?',
     '''SELECT X.eid, rel_travaille0.eid_to
FROM Personne AS X LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=X.eid)'''
#SELECT X.eid, S.eid
#FROM Personne AS X LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=X.eid) LEFT OUTER JOIN Societe AS S ON (rel_travaille0.eid_to=S.eid)'''
    ),
    ('Any S,X WHERE X? travaille S, S is Societe',
     '''SELECT S.eid, rel_travaille0.eid_from
FROM Societe AS S LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_to=S.eid)'''
#SELECT S.eid, X.eid
#FROM Societe AS S LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_to=S.eid) LEFT OUTER JOIN Personne AS X ON (rel_travaille0.eid_from=X.eid)'''
    ),

    ('Any N,A WHERE N inline1 A?',
     '''SELECT N.eid, N.inline1
FROM Note AS N'''),

    ('Any SN WHERE X from_state S?, S name SN',
     '''SELECT S.name
FROM TrInfo AS X LEFT OUTER JOIN State AS S ON (X.from_state=S.eid)'''
    ),

    ('Any A,N WHERE N? inline1 A',
     '''SELECT A.eid, N.eid
FROM Affaire AS A LEFT OUTER JOIN Note AS N ON (N.inline1=A.eid)'''
    ),

    ('Any A,B,C,D,E,F,G WHERE A eid 12,A creation_date B,A modification_date C,A comment D,A from_state E?,A to_state F?,A wf_info_for G?',
    '''SELECT A.eid, A.creation_date, A.modification_date, A.comment, A.from_state, A.to_state, A.wf_info_for
FROM TrInfo AS A
WHERE A.eid=12'''),

    ('Any FS,TS,C,D,U ORDERBY D DESC WHERE WF wf_info_for X,WF from_state FS?, WF to_state TS, WF comment C,WF creation_date D, WF owned_by U, X eid 1',
     '''SELECT WF.from_state, WF.to_state, WF.comment, WF.creation_date, rel_owned_by0.eid_to
FROM TrInfo AS WF, owned_by_relation AS rel_owned_by0
WHERE WF.wf_info_for=1 AND WF.to_state IS NOT NULL AND rel_owned_by0.eid_from=WF.eid
ORDER BY 4 DESC'''),

    ('Any X WHERE X is Affaire, S is Societe, EXISTS(X owned_by U OR (X concerne S?, S owned_by U))',
     '''SELECT X.eid
FROM Affaire AS X
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, EUser AS U, Affaire AS A LEFT OUTER JOIN concerne_relation AS rel_concerne1 ON (rel_concerne1.eid_from=A.eid) LEFT OUTER JOIN Societe AS S ON (rel_concerne1.eid_to=S.eid), owned_by_relation AS rel_owned_by2 WHERE ((rel_owned_by0.eid_from=A.eid AND rel_owned_by0.eid_to=U.eid) OR (rel_owned_by2.eid_from=S.eid AND rel_owned_by2.eid_to=U.eid)) AND X.eid=A.eid)'''),

    ('Any C,M WHERE C travaille G?, G evaluee M?, G is Societe',
     '''SELECT C.eid, rel_evaluee1.eid_to
FROM Personne AS C LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=C.eid) LEFT OUTER JOIN Societe AS G ON (rel_travaille0.eid_to=G.eid) LEFT OUTER JOIN evaluee_relation AS rel_evaluee1 ON (rel_evaluee1.eid_from=G.eid)'''
#SELECT C.eid, M.eid
#FROM Personne AS C LEFT OUTER JOIN travaille_relation AS rel_travaille0 ON (rel_travaille0.eid_from=C.eid) LEFT OUTER JOIN Societe AS G ON (rel_travaille0.eid_to=G.eid) LEFT OUTER JOIN evaluee_relation AS rel_evaluee1 ON (rel_evaluee1.eid_from=G.eid) LEFT OUTER JOIN Note AS M ON (rel_evaluee1.eid_to=M.eid)'''
     ),

    ('Any A,C WHERE A documented_by C?, (C is NULL) OR (EXISTS(C require_permission F, '
     'F name "read", F require_group E, U in_group E)), U eid 1',
     '''SELECT A.eid, rel_documented_by0.eid_to
FROM Affaire AS A LEFT OUTER JOIN documented_by_relation AS rel_documented_by0 ON (rel_documented_by0.eid_from=A.eid)
WHERE ((rel_documented_by0.eid_to IS NULL) OR (EXISTS(SELECT 1 FROM require_permission_relation AS rel_require_permission1, EPermission AS F, require_group_relation AS rel_require_group2, in_group_relation AS rel_in_group3 WHERE rel_documented_by0.eid_to=rel_require_permission1.eid_from AND rel_require_permission1.eid_to=F.eid AND F.name=read AND rel_require_group2.eid_from=F.eid AND rel_in_group3.eid_from=1 AND rel_in_group3.eid_to=rel_require_group2.eid_to)))'''),

    ("Any X WHERE X eid 12, P? connait X",
     '''SELECT X.eid
FROM Personne AS X LEFT OUTER JOIN connait_relation AS rel_connait0 ON (rel_connait0.eid_to=12)
WHERE X.eid=12'''
#SELECT 12
#FROM Personne AS X LEFT OUTER JOIN connait_relation AS rel_connait0 ON (rel_connait0.eid_to=12) LEFT OUTER JOIN Personne AS P ON (rel_connait0.eid_from=P.eid)
#WHERE X.eid=12'''
    ),

    ('Any GN, TN ORDERBY GN WHERE T tags G?, T name TN, G name GN',
    '''SELECT _T0.C1, T.name
FROM Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.eid) LEFT OUTER JOIN (SELECT G.eid AS C0, G.name AS C1
FROM EGroup AS G
UNION ALL
SELECT G.eid AS C0, G.name AS C1
FROM State AS G
UNION ALL
SELECT G.eid AS C0, G.name AS C1
FROM Tag AS G) AS _T0 ON (rel_tags0.eid_to=_T0.C0)
ORDER BY 1'''),


    # optional variable with additional restriction
    ('Any T,G WHERE T tags G?, G name "hop", G is EGroup',
     '''SELECT T.eid, G.eid
FROM Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.eid) LEFT OUTER JOIN EGroup AS G ON (rel_tags0.eid_to=G.eid AND G.name=hop)'''),

    # optional variable with additional invariant restriction
    ('Any T,G WHERE T tags G?, G eid 12',
     '''SELECT T.eid, rel_tags0.eid_to
FROM Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.eid AND rel_tags0.eid_to=12)'''),

    # optional variable with additional restriction appearing before the relation
    ('Any T,G WHERE G name "hop", T tags G?, G is EGroup',
     '''SELECT T.eid, G.eid
FROM Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.eid) LEFT OUTER JOIN EGroup AS G ON (rel_tags0.eid_to=G.eid AND G.name=hop)'''),

    # optional variable with additional restriction on inlined relation
    # XXX the expected result should be as the query below. So what, raise BadRQLQuery ?
    ('Any T,G,S WHERE T tags G?, G in_state S, S name "hop", G is EUser',
     '''SELECT T.eid, G.eid, S.eid
FROM State AS S, Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.eid) LEFT OUTER JOIN EUser AS G ON (rel_tags0.eid_to=G.eid)
WHERE G.in_state=S.eid AND S.name=hop
'''),

    # optional variable with additional invariant restriction on an inlined relation
    ('Any T,G,S WHERE T tags G, G in_state S?, S eid 1, G is EUser',
     '''SELECT rel_tags0.eid_from, G.eid, G.in_state
FROM EUser AS G, tags_relation AS rel_tags0
WHERE rel_tags0.eid_to=G.eid AND (G.in_state=1 OR G.in_state IS NULL)'''),

    # two optional variables with additional invariant restriction on an inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S eid 1, G is EUser',
     '''SELECT T.eid, G.eid, G.in_state
FROM Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.eid) LEFT OUTER JOIN EUser AS G ON (rel_tags0.eid_to=G.eid AND (G.in_state=1 OR G.in_state IS NULL))'''),

    # two optional variables with additional restriction on an inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S name "hop", G is EUser',
     '''SELECT T.eid, G.eid, S.eid
FROM Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.eid) LEFT OUTER JOIN EUser AS G ON (rel_tags0.eid_to=G.eid) LEFT OUTER JOIN State AS S ON (G.in_state=S.eid AND S.name=hop)'''),
    
    # two optional variables with additional restriction on an ambigous inlined relation
    ('Any T,G,S WHERE T tags G?, G in_state S?, S name "hop"',
     '''SELECT T.eid, _T0.C0, _T0.C1
FROM Tag AS T LEFT OUTER JOIN tags_relation AS rel_tags0 ON (rel_tags0.eid_from=T.eid) LEFT OUTER JOIN (SELECT G.eid AS C0, S.eid AS C1
FROM Affaire AS G LEFT OUTER JOIN State AS S ON (G.in_state=S.eid AND S.name=hop) 
UNION ALL
SELECT G.eid AS C0, S.eid AS C1
FROM EUser AS G LEFT OUTER JOIN State AS S ON (G.in_state=S.eid AND S.name=hop) 
UNION ALL
SELECT G.eid AS C0, S.eid AS C1
FROM Note AS G LEFT OUTER JOIN State AS S ON (G.in_state=S.eid AND S.name=hop) ) AS _T0 ON (rel_tags0.eid_to=_T0.C0)'''),

    ]

VIRTUAL_VARS = [
    ("Personne P WHERE P travaille S, S tel T, S fax T, S is Societe;",
     '''SELECT rel_travaille0.eid_from
FROM Societe AS S, travaille_relation AS rel_travaille0
WHERE rel_travaille0.eid_to=S.eid AND S.fax=S.tel'''),
    
    ("Personne P where X eid 0, X creation_date D, P datenaiss < D, X is Affaire",
     '''SELECT P.eid
FROM Affaire AS X, Personne AS P
WHERE X.eid=0 AND P.datenaiss<X.creation_date'''),

    ("Any N,T WHERE N is Note, N type T;",
     '''SELECT N.eid, N.type
FROM Note AS N'''),

    ("Personne P where X is Personne, X tel T, X fax F, P fax T+F",
     '''SELECT P.eid
FROM Personne AS P, Personne AS X
WHERE P.fax=(X.tel + X.fax)'''),

    ("Personne P where X tel T, X fax F, P fax IN (T,F)",
     '''SELECT P.eid
FROM Division AS X, Personne AS P
WHERE P.fax IN(X.tel, X.fax)
UNION ALL
SELECT P.eid
FROM Personne AS P, Personne AS X
WHERE P.fax IN(X.tel, X.fax)
UNION ALL
SELECT P.eid
FROM Personne AS P, Societe AS X
WHERE P.fax IN(X.tel, X.fax)
UNION ALL
SELECT P.eid
FROM Personne AS P, SubDivision AS X
WHERE P.fax IN(X.tel, X.fax)'''),

    ("Personne P where X tel T, X fax F, P fax IN (T,F,0832542332)",
     '''SELECT P.eid
FROM Division AS X, Personne AS P
WHERE P.fax IN(X.tel, X.fax, 832542332)
UNION ALL
SELECT P.eid
FROM Personne AS P, Personne AS X
WHERE P.fax IN(X.tel, X.fax, 832542332)
UNION ALL
SELECT P.eid
FROM Personne AS P, Societe AS X
WHERE P.fax IN(X.tel, X.fax, 832542332)
UNION ALL
SELECT P.eid
FROM Personne AS P, SubDivision AS X
WHERE P.fax IN(X.tel, X.fax, 832542332)'''),
    ]

FUNCS = [
    ("Any COUNT(P) WHERE P is Personne",
     '''SELECT COUNT(P.eid)
FROM Personne AS P'''),
##     ("Personne X where X nom upper('TOTO')",
##      '''SELECT X.eid\nFROM Personne AS X\nWHERE UPPER(X.nom) = TOTO'''),
##     ("Personne X where X nom Y, UPPER(X) prenom upper(Y)",
##      '''SELECT X.eid\nFROM Personne AS X\nWHERE UPPER(X.prenom) = UPPER(X.nom)'''),
    ]

SYMETRIC = [
    ('Any P WHERE X eid 0, X connait P',
     '''SELECT DISTINCT P.eid
FROM Personne AS P, connait_relation AS rel_connait0
WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=P.eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=P.eid)'''
#      '''SELECT rel_connait0.eid_to
# FROM connait_relation AS rel_connait0
# WHERE rel_connait0.eid_from=0
# UNION
# SELECT rel_connait0.eid_from
# FROM connait_relation AS rel_connait0
# WHERE rel_connait0.eid_to=0'''
     ),
    
    ('Any P WHERE X connait P',
    '''SELECT DISTINCT P.eid
FROM Personne AS P, connait_relation AS rel_connait0
WHERE (rel_connait0.eid_to=P.eid OR rel_connait0.eid_from=P.eid)'''
    ),
    
    ('Any X WHERE X connait P',
    '''SELECT DISTINCT X.eid
FROM Personne AS X, connait_relation AS rel_connait0
WHERE (rel_connait0.eid_from=X.eid OR rel_connait0.eid_to=X.eid)'''
     ),
    
    ('Any P WHERE X eid 0, NOT X connait P',
     '''SELECT P.eid
FROM Personne AS P
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=P.eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=P.eid))'''),
    
    ('Any P WHERE NOT X connait P',
    '''SELECT P.eid
FROM Personne AS P
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_to=P.eid OR rel_connait0.eid_from=P.eid))'''),
    
    ('Any X WHERE NOT X connait P',
    '''SELECT X.eid
FROM Personne AS X
WHERE NOT EXISTS(SELECT 1 FROM connait_relation AS rel_connait0 WHERE (rel_connait0.eid_from=X.eid OR rel_connait0.eid_to=X.eid))'''),

    ('Any P WHERE X connait P, P nom "nom"',
     '''SELECT DISTINCT P.eid
FROM Personne AS P, connait_relation AS rel_connait0
WHERE (rel_connait0.eid_to=P.eid OR rel_connait0.eid_from=P.eid) AND P.nom=nom'''),
    
    ('Any X WHERE X connait P, P nom "nom"',
     '''SELECT DISTINCT X.eid
FROM Personne AS P, Personne AS X, connait_relation AS rel_connait0
WHERE (rel_connait0.eid_from=X.eid AND rel_connait0.eid_to=P.eid OR rel_connait0.eid_to=X.eid AND rel_connait0.eid_from=P.eid) AND P.nom=nom'''
    ),

    ('Any X ORDERBY X DESC LIMIT 9 WHERE E eid 0, E connait X',
    '''SELECT DISTINCT X.eid
FROM Personne AS X, connait_relation AS rel_connait0
WHERE (rel_connait0.eid_from=0 AND rel_connait0.eid_to=X.eid OR rel_connait0.eid_to=0 AND rel_connait0.eid_from=X.eid)
ORDER BY 1 DESC
LIMIT 9'''
     ),

    ('DISTINCT Any P WHERE P connait S OR S connait P, S nom "chouette"',
     '''SELECT DISTINCT P.eid
FROM Personne AS P, Personne AS S, connait_relation AS rel_connait0
WHERE (rel_connait0.eid_from=P.eid AND rel_connait0.eid_to=S.eid OR rel_connait0.eid_to=P.eid AND rel_connait0.eid_from=S.eid) AND S.nom=chouette'''
     )
    ]

INLINE = [
    ('Any P, L WHERE N ecrit_par P, P nom L, N eid 0',
     '''SELECT P.eid, P.nom
FROM Note AS N, Personne AS P
WHERE N.ecrit_par=P.eid AND N.eid=0'''),
    
    ('Any N WHERE NOT N ecrit_par P, P nom "toto"',
     '''SELECT DISTINCT N.eid
FROM Note AS N, Personne AS P
WHERE (N.ecrit_par IS NULL OR N.ecrit_par!=P.eid) AND P.nom=toto'''),
    
    ('Any P WHERE N ecrit_par P, N eid 0',
    '''SELECT N.ecrit_par
FROM Note AS N
WHERE N.ecrit_par IS NOT NULL AND N.eid=0'''),

    ('Any P WHERE N ecrit_par P, P is Personne, N eid 0',
    '''SELECT P.eid
FROM Note AS N, Personne AS P
WHERE N.ecrit_par=P.eid AND N.eid=0'''),

    ('Any P WHERE NOT N ecrit_par P, P is Personne, N eid 512',
     '''SELECT DISTINCT P.eid
FROM Note AS N, Personne AS P
WHERE (N.ecrit_par IS NULL OR N.ecrit_par!=P.eid) AND N.eid=512'''),

    ('Any S,ES,T WHERE S state_of ET, ET name "EUser", ES allowed_transition T, T destination_state S',
     '''SELECT T.destination_state, rel_allowed_transition1.eid_from, T.eid
FROM EEType AS ET, Transition AS T, allowed_transition_relation AS rel_allowed_transition1, state_of_relation AS rel_state_of0
WHERE T.destination_state=rel_state_of0.eid_from AND rel_state_of0.eid_to=ET.eid AND ET.name=EUser AND rel_allowed_transition1.eid_to=T.eid'''),
    ('Any O WHERE S eid 0, S in_state O',
     '''SELECT S.in_state
FROM Affaire AS S
WHERE S.eid=0 AND S.in_state IS NOT NULL
UNION ALL
SELECT S.in_state
FROM EUser AS S
WHERE S.eid=0 AND S.in_state IS NOT NULL
UNION ALL
SELECT S.in_state
FROM Note AS S
WHERE S.eid=0 AND S.in_state IS NOT NULL''')
    
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
                       ("""SELECT COUNT(T1.C0) FROM (SELECT RDEF.eid AS C0
FROM EFRDef AS RDEF
WHERE RDEF.relation_type=%(x)s
UNION ALL
SELECT RDEF.eid AS C0
FROM ENFRDef AS RDEF
WHERE RDEF.relation_type=%(x)s) AS T1""", {}),
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
FROM EGroup AS G, T00, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=T00.x AND rel_in_group0.eid_to=G.eid AND G.name=users''',
                    varmap={'X': 'T00.x', 'X.login': 'T00.l'})
        self._check('Any X,L,GN WHERE X is EUser, X in_group G, X login L, G name GN',
                    '''SELECT T00.x, T00.l, G.name
FROM EGroup AS G, T00, in_group_relation AS rel_in_group0
WHERE rel_in_group0.eid_from=T00.x AND rel_in_group0.eid_to=G.eid''',
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

    def test_union(self):
        for t in self._parse((
            ('(Any N ORDERBY 1 WHERE X name N, X is State)'
             ' UNION '
             '(Any NN ORDERBY 1 WHERE XX name NN, XX is Transition)',
             '''(SELECT X.name
FROM State AS X
ORDER BY 1)
UNION ALL
(SELECT XX.name
FROM Transition AS XX
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
FROM ((SELECT X.name AS C0
FROM State AS X)
UNION ALL
(SELECT XX.name AS C0
FROM Transition AS XX)) AS _T0
ORDER BY 1'''),
            
            ('Any N,NX ORDERBY NX WITH N,NX BEING '
             '((Any N,COUNT(X) GROUPBY N WHERE X name N, X is State HAVING COUNT(X)>1)'
             ' UNION '
             '(Any N,COUNT(X) GROUPBY N WHERE X name N, X is Transition HAVING COUNT(X)>1))',
             '''SELECT _T0.C0, _T0.C1
FROM ((SELECT X.name AS C0, COUNT(X.eid) AS C1
FROM State AS X
GROUP BY X.name
HAVING COUNT(X.eid)>1)
UNION ALL
(SELECT X.name AS C0, COUNT(X.eid) AS C1
FROM Transition AS X
GROUP BY X.name
HAVING COUNT(X.eid)>1)) AS _T0
ORDER BY 2'''),            

            ('Any N,COUNT(X) GROUPBY N HAVING COUNT(X)>1 '
             'WITH X, N BEING ((Any X, N WHERE X name N, X is State) UNION '
             '                 (Any X, N WHERE X name N, X is Transition))',
             '''SELECT _T0.C1, COUNT(_T0.C0)
FROM ((SELECT X.eid AS C0, X.name AS C1
FROM State AS X)
UNION ALL
(SELECT X.eid AS C0, X.name AS C1
FROM Transition AS X)) AS _T0
GROUP BY _T0.C1
HAVING COUNT(_T0.C0)>1'''),

            ('Any ETN,COUNT(X) GROUPBY ETN WHERE X is ET, ET name ETN '
             'WITH X BEING ((Any X WHERE X is Societe) UNION (Any X WHERE X is Affaire, (EXISTS(X owned_by 1)) OR ((EXISTS(D concerne B?, B owned_by 1, X identity D, B is Note)) OR (EXISTS(F concerne E?, E owned_by 1, E is Societe, X identity F)))))',
             '''SELECT ET.name, COUNT(_T0.C0)
FROM ((SELECT X.eid AS C0
FROM Societe AS X)
UNION ALL
(SELECT X.eid AS C0
FROM Affaire AS X
WHERE ((EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0 WHERE rel_owned_by0.eid_from=X.eid AND rel_owned_by0.eid_to=1)) OR (((EXISTS(SELECT 1 FROM Affaire AS D LEFT OUTER JOIN concerne_relation AS rel_concerne1 ON (rel_concerne1.eid_from=D.eid) LEFT OUTER JOIN Note AS B ON (rel_concerne1.eid_to=B.eid), owned_by_relation AS rel_owned_by2 WHERE rel_owned_by2.eid_from=B.eid AND rel_owned_by2.eid_to=1 AND X.eid=D.eid)) OR (EXISTS(SELECT 1 FROM Affaire AS F LEFT OUTER JOIN concerne_relation AS rel_concerne3 ON (rel_concerne3.eid_from=F.eid) LEFT OUTER JOIN Societe AS E ON (rel_concerne3.eid_to=E.eid), owned_by_relation AS rel_owned_by4 WHERE rel_owned_by4.eid_from=E.eid AND rel_owned_by4.eid_to=1 AND X.eid=F.eid))))))) AS _T0, EEType AS ET, is_relation AS rel_is0
WHERE rel_is0.eid_from=_T0.C0 AND rel_is0.eid_to=ET.eid
GROUP BY ET.name'''),
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
             """SELECT X.eid
FROM Basket AS X, appears AS appears0
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM File AS X, appears AS appears0
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Folder AS X, appears AS appears0
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Image AS X, appears AS appears0
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM State AS X, appears AS appears0
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Tag AS X, appears AS appears0
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Transition AS X, appears AS appears0
WHERE appears0.words @@ to_tsquery('default', 'toto&tata') AND appears0.uid=X.eid AND X.name=tutu"""),

            ('Personne X where X has_text %(text)s, X travaille S, S has_text %(text)s',
             """SELECT X.eid
FROM appears AS appears0, appears AS appears2, entities AS X, travaille_relation AS rel_travaille1
WHERE appears0.words @@ to_tsquery('default', 'hip&hop&momo') AND appears0.uid=X.eid AND X.type='Personne' AND X.eid=rel_travaille1.eid_from AND appears2.uid=rel_travaille1.eid_to AND appears2.words @@ to_tsquery('default', 'hip&hop&momo')"""),
            )):
            yield t


    def test_from_clause_needed(self):
        queries = [("Any 1 WHERE EXISTS(T is EGroup, T name 'managers')",
                    '''SELECT 1
WHERE EXISTS(SELECT 1 FROM EGroup AS T WHERE T.name=managers)'''),
                   ('Any X,Y WHERE NOT X created_by Y, X eid 5, Y eid 6',
                    '''SELECT 5, 6
WHERE NOT EXISTS(SELECT 1 FROM created_by_relation AS rel_created_by0 WHERE rel_created_by0.eid_from=5 AND rel_created_by0.eid_to=6)'''),
                   ]
        for t in self._parse(queries):
            yield t

    def test_ambigous_exists_no_from_clause(self):
        self._check('Any COUNT(U) WHERE U eid 1, EXISTS (P owned_by U, P is IN (Note, Affaire))',
                    '''SELECT COUNT(1)
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, Affaire AS P WHERE rel_owned_by0.eid_from=P.eid AND rel_owned_by0.eid_to=1 UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, Note AS P WHERE rel_owned_by1.eid_from=P.eid AND rel_owned_by1.eid_to=1)''')


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
        return sql.strip().replace(' ILIKE ', ' LIKE ')

    def test_union(self):
        for t in self._parse((
            ('(Any N ORDERBY 1 WHERE X name N, X is State)'
             ' UNION '
             '(Any NN ORDERBY 1 WHERE XX name NN, XX is Transition)',
             '''SELECT X.name
FROM State AS X
ORDER BY 1
UNION ALL
SELECT XX.name
FROM Transition AS XX
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
FROM (SELECT X.name AS C0
FROM State AS X
UNION ALL
SELECT XX.name AS C0
FROM Transition AS XX) AS _T0
ORDER BY 1'''),
            
            ('Any N,NX ORDERBY NX WITH N,NX BEING '
             '((Any N,COUNT(X) GROUPBY N WHERE X name N, X is State HAVING COUNT(X)>1)'
             ' UNION '
             '(Any N,COUNT(X) GROUPBY N WHERE X name N, X is Transition HAVING COUNT(X)>1))',
             '''SELECT _T0.C0, _T0.C1
FROM (SELECT X.name AS C0, COUNT(X.eid) AS C1
FROM State AS X
GROUP BY X.name
HAVING COUNT(X.eid)>1
UNION ALL
SELECT X.name AS C0, COUNT(X.eid) AS C1
FROM Transition AS X
GROUP BY X.name
HAVING COUNT(X.eid)>1) AS _T0
ORDER BY 2'''),            

            ('Any N,COUNT(X) GROUPBY N HAVING COUNT(X)>1 '
             'WITH X, N BEING ((Any X, N WHERE X name N, X is State) UNION '
             '                 (Any X, N WHERE X name N, X is Transition))',
             '''SELECT _T0.C1, COUNT(_T0.C0)
FROM (SELECT X.eid AS C0, X.name AS C1
FROM State AS X
UNION ALL
SELECT X.eid AS C0, X.name AS C1
FROM Transition AS X) AS _T0
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
             """SELECT X.eid
FROM Basket AS X, appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM File AS X, appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Folder AS X, appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Image AS X, appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM State AS X, appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Tag AS X, appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Transition AS X, appears AS appears0
WHERE appears0.word_id IN (SELECT word_id FROM word WHERE word in ('toto', 'tata')) AND appears0.uid=X.eid AND X.name=tutu"""),
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
WHERE EXISTS(SELECT 1 FROM EGroup AS T WHERE T.name=managers)'''),
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
             """SELECT X.eid
FROM Basket AS X, appears AS appears0
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM File AS X, appears AS appears0
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Folder AS X, appears AS appears0
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Image AS X, appears AS appears0
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM State AS X, appears AS appears0
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Tag AS X, appears AS appears0
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.name=tutu
UNION ALL
SELECT X.eid
FROM Transition AS X, appears AS appears0
WHERE MATCH (appears0.words) AGAINST ('toto tata' IN BOOLEAN MODE) AND appears0.uid=X.eid AND X.name=tutu""")
            ]
        for t in self._parse(queries):
            yield t
                             

    def test_ambigous_exists_no_from_clause(self):
        self._check('Any COUNT(U) WHERE U eid 1, EXISTS (P owned_by U, P is IN (Note, Affaire))',
                    '''SELECT COUNT(1)
FROM (SELECT 1) AS _T
WHERE EXISTS(SELECT 1 FROM owned_by_relation AS rel_owned_by0, Affaire AS P WHERE rel_owned_by0.eid_from=P.eid AND rel_owned_by0.eid_to=1 UNION SELECT 1 FROM owned_by_relation AS rel_owned_by1, Note AS P WHERE rel_owned_by1.eid_from=P.eid AND rel_owned_by1.eid_to=1)''') 
           

        

if __name__ == '__main__':
    unittest_main()
