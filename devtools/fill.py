# -*- coding: iso-8859-1 -*-
"""This modules defines func / methods for creating test repositories

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from random import randint, choice
from copy import deepcopy
from datetime import datetime, date, timedelta
from decimal import Decimal

from yams.constraints import (SizeConstraint, StaticVocabularyConstraint,
                              IntervalBoundConstraint)
from rql.utils import decompose_b26 as base_decompose_b26

from cubicweb import Binary
from cubicweb.schema import RQLConstraint

def decompose_b26(index, ascii=False):
    """return a letter (base-26) decomposition of index"""
    if ascii:
        return base_decompose_b26(index)
    return base_decompose_b26(index, u'éabcdefghijklmnopqrstuvwxyz')

def get_choices(eschema, attrname):
    """returns possible choices for 'attrname'
    if attrname doesn't have ChoiceConstraint, return None
    """
    for cst in eschema.constraints(attrname):
        if isinstance(cst, StaticVocabularyConstraint):
            return cst.vocabulary()
    return None
    

def get_max_length(eschema, attrname):
    """returns the maximum length allowed for 'attrname'"""
    for cst in eschema.constraints(attrname):
        if isinstance(cst, SizeConstraint) and cst.max:
            return cst.max
    return 300
    #raise AttributeError('No Size constraint on attribute "%s"' % attrname)

def get_bounds(eschema, attrname):
    for cst in eschema.constraints(attrname):
        if isinstance(cst, IntervalBoundConstraint):
            return cst.minvalue, cst.maxvalue
    return None, None


_GENERATED_VALUES = {}

class _ValueGenerator(object):
    """generates integers / dates / strings / etc. to fill a DB table"""

    def __init__(self, eschema, choice_func=None):
        """<choice_func> is a function that returns a list of possible
        choices for a given entity type and an attribute name. It should
        looks like :
            def values_for(etype, attrname):
                # some stuff ...
                return alist_of_acceptable_values # or None
        """
        self.e_schema = eschema
        self.choice_func = choice_func

    def _generate_value(self, attrname, index, **kwargs):
        if not self.e_schema.has_unique_values(attrname):
            return self.__generate_value(attrname, index, **kwargs)
        value = self.__generate_value(attrname, index, **kwargs)
        while value in _GENERATED_VALUES.get((self.e_schema.type, attrname), ()):
            index += 1
            value = self.__generate_value(attrname, index, **kwargs)
        _GENERATED_VALUES.setdefault((self.e_schema.type, attrname), set()).add(value)
        return value
        
    def __generate_value(self, attrname, index, **kwargs):
        """generates a consistent value for 'attrname'"""
        attrtype = str(self.e_schema.destination(attrname)).lower()
        # Before calling generate_%s functions, try to find values domain
        etype = self.e_schema.type
        if self.choice_func is not None:
            values_domain = self.choice_func(etype, attrname)
            if values_domain is not None:
                return choice(values_domain)
        gen_func = getattr(self, 'generate_%s_%s' % (self.e_schema.type, attrname), None)
        if gen_func is None:
            gen_func = getattr(self, 'generate_Any_%s' % attrname, None)
        if gen_func is not None:
            return gen_func(index, **kwargs)
        # If no specific values domain, then generate a dummy value
        gen_func = getattr(self, 'generate_%s' % (attrtype))
        return gen_func(attrname, index, **kwargs)

    def generate_choice(self, attrname, index):
        """generates a consistent value for 'attrname' if it's a choice"""
        choices = get_choices(self.e_schema, attrname)
        if choices is None:
            return None
        return unicode(choice(choices)) # FIXME
        
    def generate_string(self, attrname, index, format=None):
        """generates a consistent value for 'attrname' if it's a string"""
        # First try to get choices
        choosed = self.generate_choice(attrname, index)
        if choosed is not None:
            return choosed
        # All other case, generate a default string
        attrlength = get_max_length(self.e_schema, attrname)
        num_len = numlen(index)
        if num_len >= attrlength:
            ascii = self.e_schema.rproperty(attrname, 'internationalizable')
            return ('&'+decompose_b26(index, ascii))[:attrlength]
        # always use plain text when no format is specified
        attrprefix = attrname[:max(attrlength-num_len-1, 0)]
        if format == 'text/html':
            value = u'<span>é%s<b>%d</b></span>' % (attrprefix, index)
        elif format == 'text/rest':
            value = u"""
title
-----

* %s
* %d
* é&
""" % (attrprefix, index)
        else:
            value = u'é&%s%d' % (attrprefix, index)
        return value[:attrlength]

    def generate_password(self, attrname, index):
        """generates a consistent value for 'attrname' if it's a password"""
        return u'toto'
        
    def generate_integer(self, attrname, index):
        """generates a consistent value for 'attrname' if it's an integer"""
        choosed = self.generate_choice(attrname, index)
        if choosed is not None:
            return choosed
        minvalue, maxvalue = get_bounds(self.e_schema, attrname)
        if maxvalue is not None and maxvalue <= 0 and minvalue is None:
            minvalue = maxvalue - index # i.e. randint(-index, 0)
        else:
            maxvalue = maxvalue or index
        return randint(minvalue or 0, maxvalue)
    
    generate_int = generate_integer
    
    def generate_float(self, attrname, index):
        """generates a consistent value for 'attrname' if it's a float"""
        return float(randint(-index, index))
    
    def generate_decimal(self, attrname, index):
        """generates a consistent value for 'attrname' if it's a float"""
        return Decimal(str(self.generate_float(attrname, index)))
    
    def generate_date(self, attrname, index):
        """generates a random date (format is 'yyyy-mm-dd')"""
        return date(randint(2000, 2004), randint(1, 12), randint(1, 28))

    def generate_time(self, attrname, index):
        """generates a random time (format is ' HH:MM')"""
        return timedelta(0, 11, index%60) #'11:%02d' % (index % 60)
    
    def generate_datetime(self, attrname, index):
        """generates a random date (format is 'yyyy-mm-dd HH:MM')"""
        return datetime(randint(2000, 2004), randint(1, 12), randint(1, 28), 11, index%60)
        

    def generate_bytes(self, attrname, index, format=None):
        # modpython way
        fakefile = Binary("%s%s" % (attrname, index))
        fakefile.filename = "file_%s" % attrname
        fakefile.value = fakefile.getvalue()
        return fakefile
    
    def generate_boolean(self, attrname, index):
        """generates a consistent value for 'attrname' if it's a boolean"""
        return index % 2 == 0

    def generate_Any_data_format(self, index, **kwargs):
        # data_format attribute of Image/File has no vocabulary constraint, we
        # need this method else stupid values will be set which make mtconverter
        # raise exception
        return u'application/octet-stream'
    
    def generate_Any_content_format(self, index, **kwargs):
        # content_format attribute of EmailPart has no vocabulary constraint, we
        # need this method else stupid values will be set which make mtconverter
        # raise exception
        return u'text/plain'

    def generate_Image_data_format(self, index, **kwargs):
        # data_format attribute of Image/File has no vocabulary constraint, we
        # need this method else stupid values will be set which make mtconverter
        # raise exception
        return u'image/png'


class autoextend(type):
    def __new__(mcs, name, bases, classdict):
        for attrname, attrvalue in classdict.items():
            if callable(attrvalue):
                if attrname.startswith('generate_') and \
                       attrvalue.func_code.co_argcount < 2:
                    raise TypeError('generate_xxx must accept at least 1 argument')
                setattr(_ValueGenerator, attrname, attrvalue)
        return type.__new__(mcs, name, bases, classdict)

class ValueGenerator(_ValueGenerator):
    __metaclass__ = autoextend


def _default_choice_func(etype, attrname):
    """default choice_func for insert_entity_queries"""
    return None

def insert_entity_queries(etype, schema, vreg, entity_num,
                          choice_func=_default_choice_func):
    """returns a list of 'add entity' queries (couples query, args)
    :type etype: str
    :param etype: the entity's type

    :type schema: cubicweb.schema.Schema
    :param schema: the application schema

    :type entity_num: int
    :param entity_num: the number of entities to insert

    XXX FIXME: choice_func is here for *historical* reasons, it should
               probably replaced by a nicer way to specify choices
    :type choice_func: function
    :param choice_func: a function that takes an entity type, an attrname and
                        returns acceptable values for this attribute
    """
    # XXX HACK, remove or fix asap
    if etype in (('String', 'Int', 'Float', 'Boolean', 'Date', 'CWGroup', 'CWUser')):
        return []
    queries = []
    for index in xrange(entity_num):
        restrictions = []
        args = {}
        for attrname, value in make_entity(etype, schema, vreg, index, choice_func).items():
            restrictions.append('X %s %%(%s)s' % (attrname, attrname))
            args[attrname] = value
        if restrictions:
            queries.append(('INSERT %s X: %s' % (etype, ', '.join(restrictions)),
                            args))
            assert not 'eid' in args, args
        else:
            queries.append(('INSERT %s X' % etype, {}))        
    return queries


def make_entity(etype, schema, vreg, index=0, choice_func=_default_choice_func,
                form=False):
    """generates a random entity and returns it as a dict

    by default, generate an entity to be inserted in the repository
    elif form, generate an form dictionnary to be given to a web controller
    """
    eschema = schema.eschema(etype)
    valgen = ValueGenerator(eschema, choice_func)
    entity = {}
    # preprocessing to deal with _format fields
    attributes = []
    relatedfields = {}
    for rschema, attrschema in eschema.attribute_definitions():
        attrname = rschema.type
        if attrname == 'eid':
            # don't specify eids !
            continue
        if attrname.endswith('_format') and attrname[:-7] in eschema.subject_relations():
            relatedfields[attrname[:-7]] = attrschema
        else:
            attributes.append((attrname, attrschema))
    for attrname, attrschema in attributes:
        if attrname in relatedfields:
            # first generate a format and record it
            format = valgen._generate_value(attrname + '_format', index)
            entity[attrname + '_format'] = format
            # then a value coherent with this format
            value = valgen._generate_value(attrname, index, format=format)
        else:
            value = valgen._generate_value(attrname, index)
        if form: # need to encode values
            if attrschema.type == 'Bytes':
                # twisted way
                fakefile = value
                filename = value.filename
                value = (filename, u"text/plain", fakefile)
            elif attrschema.type == 'Date':
                value = value.strftime(vreg.property_value('ui.date-format'))
            elif attrschema.type == 'Datetime':
                value = value.strftime(vreg.property_value('ui.datetime-format'))
            elif attrschema.type == 'Time':
                value = value.strftime(vreg.property_value('ui.time-format'))
            elif attrschema.type == 'Float':
                fmt = vreg.property_value('ui.float-format')
                value = fmt % value
            else:
                value = unicode(value)
        entity[attrname] = value
    return entity



def select(constraints, cursor, selectvar='O'):
    """returns list of eids matching <constraints>

    <selectvar> should be either 'O' or 'S' to match schema definitions
    """
    try:
        rset = cursor.execute('Any %s WHERE %s' % (selectvar, constraints))
    except:
        print "could restrict eid_list with given constraints (%r)" % constraints
        return []
    return set(eid for eid, in rset.rows)



def make_relations_queries(schema, edict, cursor, ignored_relations=(),
                           existingrels=None):
    """returns a list of generated RQL queries for relations
    :param schema: The application schema

    :param e_dict: mapping between etypes and eids

    :param ignored_relations: list of relations to ignore (i.e. don't try
                              to generate insert queries for these relations)
    """
    gen = RelationsQueriesGenerator(schema, cursor, existingrels)
    return gen.compute_queries(edict, ignored_relations)


class RelationsQueriesGenerator(object):
    rql_tmpl = 'SET S %s O WHERE S eid %%(subjeid)s, O eid %%(objeid)s'
    def __init__(self, schema, cursor, existing=None):
        self.schema = schema
        self.cursor = cursor
        self.existingrels = existing or {}

    def compute_queries(self, edict, ignored_relations):
        queries = []
        #   1/ skip final relations and explictly ignored relations
        rels = [rschema for rschema in self.schema.relations()
                if not (rschema.is_final() or rschema in ignored_relations)]
        # for each relation
        #   2/ take each possible couple (subj, obj)
        #   3/ analyze cardinality of relation
        #      a/ if relation is mandatory, insert one relation
        #      b/ else insert N relations where N is the mininum
        #         of 20 and the number of existing targetable entities
        for rschema in rels:
            sym = set()
            sedict = deepcopy(edict)
            oedict = deepcopy(edict)
            delayed = []
            # for each couple (subjschema, objschema), insert relations
            for subj, obj in rschema.iter_rdefs():
                sym.add( (subj, obj) )
                if rschema.symetric and (obj, subj) in sym:
                    continue
                subjcard, objcard = rschema.rproperty(subj, obj, 'cardinality')
                # process mandatory relations first
                if subjcard in '1+' or objcard in '1+': 
                    queries += self.make_relation_queries(sedict, oedict,
                                                          rschema, subj, obj)
                else:
                    delayed.append( (subj, obj) )
            for subj, obj in delayed:
                queries += self.make_relation_queries(sedict, oedict, rschema,
                                                      subj, obj)
        return queries
        
    def qargs(self, subjeids, objeids, subjcard, objcard, subjeid, objeid):
        if subjcard in '?1':
            subjeids.remove(subjeid)
        if objcard in '?1':
            objeids.remove(objeid)
        return {'subjeid' : subjeid, 'objeid' : objeid}

    def make_relation_queries(self, sedict, oedict, rschema, subj, obj):
        subjcard, objcard = rschema.rproperty(subj, obj, 'cardinality')
        subjeids = sedict.get(subj, frozenset())
        used = self.existingrels[rschema.type]
        preexisting_subjrels = set(subj for subj, obj in used)
        preexisting_objrels = set(obj for subj, obj in used)
        # if there are constraints, only select appropriate objeids
        q = self.rql_tmpl % rschema.type
        constraints = [c for c in rschema.rproperty(subj, obj, 'constraints')
                       if isinstance(c, RQLConstraint)]
        if constraints:
            restrictions = ', '.join(c.restriction for c in constraints)
            q += ', %s' % restrictions
            # restrict object eids if possible
            objeids = select(restrictions, self.cursor)
        else:
            objeids = oedict.get(obj, frozenset())
        if subjcard in '?1' or objcard in '?1':
            for subjeid, objeid in used:
                if subjcard in '?1' and subjeid in subjeids:
                    subjeids.remove(subjeid)
                    if objeid in objeids:
                        objeids.remove(objeid)
                if objcard in '?1' and objeid in objeids:
                    objeids.remove(objeid)
                    if subjeid in subjeids:
                        subjeids.remove(subjeid)
        if not subjeids:
            check_card_satisfied(objcard, objeids, subj, rschema, obj)
            return 
        if not objeids:
            check_card_satisfied(subjcard, subjeids, subj, rschema, obj)
            return
        if subjcard in '?1+':
            for subjeid in tuple(subjeids):
                # do not insert relation if this entity already has a relation
                if subjeid in preexisting_subjrels:
                    continue
                objeid = choose_eid(objeids, subjeid)
                if objeid is None or (subjeid, objeid) in used:
                    continue
                yield q, self.qargs(subjeids, objeids, subjcard, objcard,
                                    subjeid, objeid)
                used.add( (subjeid, objeid) )
                if not objeids:
                    check_card_satisfied(subjcard, subjeids, subj, rschema, obj)
                    break
        elif objcard in '?1+':
            for objeid in tuple(objeids):
                # do not insert relation if this entity already has a relation
                if objeid in preexisting_objrels:
                    continue
                subjeid = choose_eid(subjeids, objeid)
                if subjeid is None or (subjeid, objeid) in used:
                    continue
                yield q, self.qargs(subjeids, objeids, subjcard, objcard,
                                    subjeid, objeid)
                used.add( (subjeid, objeid) )
                if not subjeids:
                    check_card_satisfied(objcard, objeids, subj, rschema, obj)
                    break
        else:
            # FIXME: 20 should be read from config
            subjeidsiter = [choice(tuple(subjeids)) for i in xrange(min(len(subjeids), 20))]
            objeidsiter = [choice(tuple(objeids)) for i in xrange(min(len(objeids), 20))]
            for subjeid, objeid in zip(subjeidsiter, objeidsiter):
                if subjeid != objeid and not (subjeid, objeid) in used:
                    used.add( (subjeid, objeid) )
                    yield q, self.qargs(subjeids, objeids, subjcard, objcard,
                                        subjeid, objeid)
                    
def check_card_satisfied(card, remaining, subj, rschema, obj):
    if card in '1+' and remaining:
        raise Exception("can't satisfy cardinality %s for relation %s %s %s"
                        % (card, subj, rschema, obj))

def choose_eid(values, avoid):
    values = tuple(values)
    if len(values) == 1 and values[0] == avoid:
        return None
    objeid = choice(values)
    while objeid == avoid: # avoid infinite recursion like in X comment X
        objeid = choice(values)
    return objeid
                    
                

# UTILITIES FUNCS ##############################################################
def make_tel(num_tel):
    """takes an integer, converts is as a string and inserts
    white spaces each 2 chars (french notation)
    """
    num_list = list(str(num_tel))
    for index in (6, 4, 2):
        num_list.insert(index, ' ')

    return ''.join(num_list)


def numlen(number):
    """returns the number's length"""
    return len(str(number))
