# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""a query processor to handle quick search shortcuts for cubicweb
"""

__docformat__ = "restructuredtext en"

import re
from logging import getLogger

from yams.interfaces import IVocabularyConstraint

from rql import RQLSyntaxError, BadRQLQuery, parse
from rql.utils import rqlvar_maker
from rql.nodes import Relation

from cubicweb import Unauthorized
from cubicweb.view import Component
from cubicweb.web.views.ajaxcontroller import ajaxfunc

LOGGER = getLogger('cubicweb.magicsearch')

def _get_approriate_translation(translations_found, eschema):
    """return the first (should be the only one) possible translation according
    to the given entity type
    """
    # get the list of all attributes / relations for this kind of entity
    existing_relations = set(eschema.subject_relations())
    consistent_translations = translations_found & existing_relations
    if len(consistent_translations) == 0:
        return None
    return consistent_translations.pop()


def translate_rql_tree(rqlst, translations, schema):
    """Try to translate each relation in the RQL syntax tree

    :type rqlst: `rql.stmts.Statement`
    :param rqlst: the RQL syntax tree

    :type translations: dict
    :param translations: the reverted l10n dict

    :type schema: `cubicweb.schema.Schema`
    :param schema: the instance's schema
    """
    # var_types is used as a map : var_name / var_type
    vartypes = {}
    # ambiguous_nodes is used as a map : relation_node / (var_name, available_translations)
    ambiguous_nodes = {}
    # For each relation node, check if it's a localized relation name
    # If it's a localized name, then use the original relation name, else
    # keep the existing relation name
    for relation in rqlst.get_nodes(Relation):
        rtype = relation.r_type
        lhs, rhs = relation.get_variable_parts()
        if rtype == 'is':
            try:
                etype = translations[rhs.value]
                rhs.value = etype
            except KeyError:
                # If no translation found, leave the entity type as is
                etype = rhs.value
            # Memorize variable's type
            vartypes[lhs.name] = etype
        else:
            try:
                translation_set = translations[rtype]
            except KeyError:
                pass # If no translation found, leave the relation type as is
            else:
                # Only one possible translation, no ambiguity
                if len(translation_set) == 1:
                    relation.r_type = iter(translations[rtype]).next()
                # More than 1 possible translation => resolve it later
                else:
                    ambiguous_nodes[relation] = (lhs.name, translation_set)
    if ambiguous_nodes:
        resolve_ambiguities(vartypes, ambiguous_nodes, schema)


def resolve_ambiguities(var_types, ambiguous_nodes, schema):
    """Tries to resolve remaining ambiguities for translation
    /!\ An ambiguity is when two different string can be localized with
        the same string
    A simple example:
      - 'name' in a company context will be localized as 'nom' in French
      - but ... 'surname' will also be localized as 'nom'

    :type var_types: dict
    :param var_types: a map : var_name / var_type

    :type ambiguous_nodes: dict
    :param ambiguous_nodes: a map : relation_node / (var_name, available_translations)

    :type schema: `cubicweb.schema.Schema`
    :param schema: the instance's schema
    """
    # Now, try to resolve ambiguous translations
    for relation, (var_name, translations_found) in ambiguous_nodes.items():
        try:
            vartype = var_types[var_name]
        except KeyError:
            continue
        # Get schema for this entity type
        eschema = schema.eschema(vartype)
        rtype = _get_approriate_translation(translations_found, eschema)
        if rtype is None:
            continue
        relation.r_type = rtype



QUOTED_SRE = re.compile(r'(.*?)(["\'])(.+?)\2')

TRANSLATION_MAPS = {}
def trmap(config, schema, lang):
    try:
        return TRANSLATION_MAPS[lang]
    except KeyError:
        assert lang in config.translations, '%s %s' % (lang, config.translations)
        tr, ctxtr = config.translations[lang]
        langmap = {}
        for etype in schema.entities():
            etype = str(etype)
            langmap[tr(etype).capitalize()] = etype
            langmap[etype.capitalize()] = etype
        for rtype in schema.relations():
            rtype = str(rtype)
            langmap.setdefault(tr(rtype).lower(), set()).add(rtype)
            langmap.setdefault(rtype, set()).add(rtype)
        TRANSLATION_MAPS[lang] = langmap
        return langmap


class BaseQueryProcessor(Component):
    __abstract__ = True
    __regid__ = 'magicsearch_processor'
    # set something if you want explicit component search facility for the
    # component
    name = None

    def process_query(self, uquery):
        args = self.preprocess_query(uquery)
        try:
            return self._cw.execute(*args)
        finally:
            # rollback necessary to avoid leaving the connection in a bad state
            self._cw.cnx.rollback()

    def preprocess_query(self, uquery):
        raise NotImplementedError()




class DoNotPreprocess(BaseQueryProcessor):
    """this one returns the raw query and should be placed in first position
    of the chain
    """
    name = 'rql'
    priority = 0
    def preprocess_query(self, uquery):
        return uquery,


class QueryTranslator(BaseQueryProcessor):
    """ parses through rql and translates into schema language entity names
    and attributes
    """
    priority = 2
    def preprocess_query(self, uquery):
        rqlst = parse(uquery, print_errors=False)
        schema = self._cw.vreg.schema
        # rql syntax tree will be modified in place if necessary
        translate_rql_tree(rqlst, trmap(self._cw.vreg.config, schema, self._cw.lang),
                           schema)
        return rqlst.as_string(),


class QSPreProcessor(BaseQueryProcessor):
    """Quick search preprocessor

    preprocessing query in shortcut form to their RQL form
    """
    priority = 4

    def preprocess_query(self, uquery):
        """try to get rql from a unicode query string"""
        args = None
        try:
            # Process as if there was a quoted part
            args = self._quoted_words_query(uquery)
        ## No quoted part
        except BadRQLQuery:
            words = uquery.split()
            if len(words) == 1:
                args = self._one_word_query(*words)
            elif len(words) == 2:
                args = self._two_words_query(*words)
            elif len(words) == 3:
                args = self._three_words_query(*words)
            else:
                raise
        return args

    def _get_entity_type(self, word):
        """check if the given word is matching an entity type, return it if
        it's the case or raise BadRQLQuery if not
        """
        etype = word.capitalize()
        try:
            return trmap(self._cw.vreg.config, self._cw.vreg.schema, self._cw.lang)[etype]
        except KeyError:
            raise BadRQLQuery('%s is not a valid entity name' % etype)

    def _get_attribute_name(self, word, eschema):
        """check if the given word is matching an attribute of the given entity type,
        return it normalized if found or return it untransformed else
        """
        """Returns the attributes's name as stored in the DB"""
        # Need to convert from unicode to string (could be whatever)
        rtype = word.lower()
        # Find the entity name as stored in the DB
        translations = trmap(self._cw.vreg.config, self._cw.vreg.schema, self._cw.lang)
        try:
            translations = translations[rtype]
        except KeyError:
            raise BadRQLQuery('%s is not a valid attribute for %s entity type'
                              % (word, eschema))
        rtype = _get_approriate_translation(translations, eschema)
        if rtype is None:
            raise BadRQLQuery('%s is not a valid attribute for %s entity type'
                              % (word, eschema))
        return rtype

    def _one_word_query(self, word):
        """Specific process for one word query (case (1) of preprocess_rql)
        """
        # if this is an integer, then directly go to eid
        try:
            eid = int(word)
            return 'Any X WHERE X eid %(x)s', {'x': eid}, 'x'
        except ValueError:
            etype = self._get_entity_type(word)
            return '%s %s' % (etype, etype[0]),

    def _complete_rql(self, searchstr, etype, rtype=None, var=None, searchattr=None):
        searchop = ''
        if '%' in searchstr:
            if rtype:
                possible_etypes = self._cw.vreg.schema.rschema(rtype).objects(etype)
            else:
                possible_etypes = [self._cw.vreg.schema.eschema(etype)]
            if searchattr or len(possible_etypes) == 1:
                searchattr = searchattr or possible_etypes[0].main_attribute()
                searchop = 'LIKE '
        searchattr = searchattr or 'has_text'
        if var is None:
            var = etype[0]
        return '%s %s %s%%(text)s' % (var, searchattr, searchop)

    def _two_words_query(self, word1, word2):
        """Specific process for two words query (case (2) of preprocess_rql)
        """
        etype = self._get_entity_type(word1)
        # this is a valid RQL query : ("Person X", or "Person TMP1")
        if len(word2) == 1 and word2.isupper():
            return '%s %s' % (etype, word2),
        # else, suppose it's a shortcut like : Person Smith
        restriction = self._complete_rql(word2, etype)
        if ' has_text ' in restriction:
            rql = '%s %s ORDERBY FTIRANK(%s) DESC WHERE %s' % (
                etype, etype[0], etype[0], restriction)
        else:
            rql = '%s %s WHERE %s' % (
                etype, etype[0], restriction)
        return rql, {'text': word2}

    def _three_words_query(self, word1, word2, word3):
        """Specific process for three words query (case (3) of preprocess_rql)
        """
        etype = self._get_entity_type(word1)
        eschema = self._cw.vreg.schema.eschema(etype)
        rtype = self._get_attribute_name(word2, eschema)
        # expand shortcut if rtype is a non final relation
        if not self._cw.vreg.schema.rschema(rtype).final:
            return self._expand_shortcut(etype, rtype, word3)
        if '%' in word3:
            searchop = 'LIKE '
        else:
            searchop = ''
        rql = '%s %s WHERE %s' % (etype, etype[0],
                                  self._complete_rql(word3, etype, searchattr=rtype))
        return rql, {'text': word3}

    def _expand_shortcut(self, etype, rtype, searchstr):
        """Expands shortcut queries on a non final relation to use has_text or
        the main attribute (according to possible entity type) if '%' is used in the
        search word

        Transforms : 'person worksat IBM' into
        'Personne P WHERE P worksAt C, C has_text "IBM"'
        """
        # check out all possilbe entity types for the relation represented
        # by 'rtype'
        mainvar = etype[0]
        searchvar = mainvar  + '1'
        restriction = self._complete_rql(searchstr, etype, rtype=rtype,
                                         var=searchvar)
        if ' has_text ' in restriction:
            rql =  ('%s %s ORDERBY FTIRANK(%s) DESC '
                    'WHERE %s %s %s, %s' % (etype, mainvar, searchvar,
                                            mainvar, rtype, searchvar, # P worksAt C
                                            restriction))
        else:
            rql =  ('%s %s WHERE %s %s %s, %s' % (etype, mainvar,
                                            mainvar, rtype, searchvar, # P worksAt C
                                            restriction))
        return rql, {'text': searchstr}


    def _quoted_words_query(self, ori_rql):
        """Specific process when there's a "quoted" part
        """
        m = QUOTED_SRE.match(ori_rql)
        # if there's no quoted part, then no special pre-processing to do
        if m is None:
            raise BadRQLQuery("unable to handle request %r" % ori_rql)
        left_words = m.group(1).split()
        quoted_part = m.group(3)
        # Case (1) : Company "My own company"
        if len(left_words) == 1:
            try:
                word1 = left_words[0]
                return self._two_words_query(word1, quoted_part)
            except BadRQLQuery as error:
                raise BadRQLQuery("unable to handle request %r" % ori_rql)
        # Case (2) : Company name "My own company";
        elif len(left_words) == 2:
            word1, word2 = left_words
            return self._three_words_query(word1, word2, quoted_part)
            # return ori_rql
        raise BadRQLQuery("unable to handle request %r" % ori_rql)



class FullTextTranslator(BaseQueryProcessor):
    priority = 10
    name = 'text'

    def preprocess_query(self, uquery):
        """suppose it's a plain text query"""
        return 'Any X ORDERBY FTIRANK(X) DESC WHERE X has_text %(text)s', {'text': uquery}



class MagicSearchComponent(Component):
    __regid__  = 'magicsearch'
    def __init__(self, req, rset=None):
        super(MagicSearchComponent, self).__init__(req, rset=rset)
        processors = []
        self.by_name = {}
        for processorcls in self._cw.vreg['components']['magicsearch_processor']:
            # instantiation needed
            processor = processorcls(self._cw)
            processors.append(processor)
            if processor.name is not None:
                assert not processor.name in self.by_name
                self.by_name[processor.name.lower()] = processor
        self.processors = sorted(processors, key=lambda x: x.priority)

    def process_query(self, uquery):
        assert isinstance(uquery, unicode)
        try:
            procname, query = uquery.split(':', 1)
            proc = self.by_name[procname.strip().lower()]
            uquery = query.strip()
        except Exception:
            # use processor chain
            unauthorized = None
            for proc in self.processors:
                try:
                    return proc.process_query(uquery)
                # FIXME : we don't want to catch any exception type here !
                except (RQLSyntaxError, BadRQLQuery):
                    pass
                except Unauthorized as ex:
                    unauthorized = ex
                    continue
                except Exception as ex:
                    LOGGER.debug('%s: %s', ex.__class__.__name__, ex)
                    continue
            if unauthorized:
                raise unauthorized
        else:
            # explicitly specified processor: don't try to catch the exception
            return proc.process_query(uquery)
        raise BadRQLQuery(self._cw._('sorry, the server is unable to handle this query'))



## RQL suggestions builder ####################################################
class RQLSuggestionsBuilder(Component):
    """main entry point is `build_suggestions()` which takes
    an incomplete RQL query and returns a list of suggestions to complete
    the query.

    This component is enabled by default and is used to provide autocompletion
    in the RQL search bar. If you don't want this feature in your application,
    just unregister it or make it unselectable.

    .. automethod:: cubicweb.web.views.magicsearch.RQLSuggestionsBuilder.build_suggestions
    .. automethod:: cubicweb.web.views.magicsearch.RQLSuggestionsBuilder.etypes_suggestion_set
    .. automethod:: cubicweb.web.views.magicsearch.RQLSuggestionsBuilder.possible_etypes
    .. automethod:: cubicweb.web.views.magicsearch.RQLSuggestionsBuilder.possible_relations
    .. automethod:: cubicweb.web.views.magicsearch.RQLSuggestionsBuilder.vocabulary
    """
    __regid__ = 'rql.suggestions'

    #: maximum number of results to fetch when suggesting attribute values
    attr_value_limit = 20

    def build_suggestions(self, user_rql):
        """return a list of suggestions to complete `user_rql`

        :param user_rql: an incomplete RQL query
        """
        req = self._cw
        try:
            if 'WHERE' not in user_rql: # don't try to complete if there's no restriction
                return []
            variables, restrictions = [part.strip() for part in user_rql.split('WHERE', 1)]
            if ',' in restrictions:
                restrictions, incomplete_part = restrictions.rsplit(',', 1)
                user_rql = '%s WHERE %s' % (variables, restrictions)
            else:
                restrictions, incomplete_part = '', restrictions
                user_rql = variables
            select = parse(user_rql, print_errors=False).children[0]
            req.vreg.rqlhelper.annotate(select)
            req.vreg.solutions(req, select, {})
            if restrictions:
                return ['%s, %s' % (user_rql, suggestion)
                        for suggestion in self.rql_build_suggestions(select, incomplete_part)]
            else:
                return ['%s WHERE %s' % (user_rql, suggestion)
                        for suggestion in self.rql_build_suggestions(select, incomplete_part)]
        except Exception as exc: # we never want to crash
            self.debug('failed to build suggestions: %s', exc)
            return []

    ## actual completion entry points #########################################
    def rql_build_suggestions(self, select, incomplete_part):
        """
        :param select: the annotated select node (rql syntax tree)
        :param incomplete_part: the part of the rql query that needs
                                to be completed, (e.g. ``X is Pr``, ``X re``)
        """
        chunks = incomplete_part.split(None, 2)
        if not chunks: # nothing to complete
            return []
        if len(chunks) == 1: # `incomplete` looks like "MYVAR"
            return self._complete_rqlvar(select, *chunks)
        elif len(chunks) == 2: # `incomplete` looks like "MYVAR some_rel"
            return self._complete_rqlvar_and_rtype(select, *chunks)
        elif len(chunks) == 3: # `incomplete` looks like "MYVAR some_rel something"
            return self._complete_relation_object(select, *chunks)
        else: # would be anything else, hard to decide what to do here
            return []

    # _complete_* methods are considered private, at least while the API
    # isn't stabilized.
    def _complete_rqlvar(self, select, rql_var):
        """return suggestions for "variable only" incomplete_part

        as in :

        - Any X WHERE X
        - Any X WHERE X is Project, Y
        - etc.
        """
        return ['%s %s %s' % (rql_var, rtype, dest_var)
                for rtype, dest_var in self.possible_relations(select, rql_var)]

    def _complete_rqlvar_and_rtype(self, select, rql_var, user_rtype):
        """return suggestions for "variable + rtype" incomplete_part

        as in :

        - Any X WHERE X is
        - Any X WHERE X is Person, X firstn
        - etc.
        """
        # special case `user_type` == 'is', return every possible type.
        if user_rtype == 'is':
            return self._complete_is_relation(select, rql_var)
        else:
            return ['%s %s %s' % (rql_var, rtype, dest_var)
                    for rtype, dest_var in self.possible_relations(select, rql_var)
                    if rtype.startswith(user_rtype)]

    def _complete_relation_object(self, select, rql_var, user_rtype, user_value):
        """return suggestions for "variable + rtype + some_incomplete_value"

        as in :

        - Any X WHERE X is Per
        - Any X WHERE X is Person, X firstname "
        - Any X WHERE X is Person, X firstname "Pa
        - etc.
        """
        # special case `user_type` == 'is', return every possible type.
        if user_rtype == 'is':
            return self._complete_is_relation(select, rql_var, user_value)
        elif user_value:
            if user_value[0] in ('"', "'"):
                # if finished string, don't suggest anything
                if len(user_value) > 1 and user_value[-1] == user_value[0]:
                    return []
                user_value = user_value[1:]
                return ['%s %s "%s"' % (rql_var, user_rtype, value)
                        for value in self.vocabulary(select, rql_var,
                                                     user_rtype, user_value)]
        return []

    def _complete_is_relation(self, select, rql_var, prefix=''):
        """return every possible types for rql_var

        :param prefix: if specified, will only return entity types starting
                       with the specified value.
        """
        return ['%s is %s' % (rql_var, etype)
                for etype in self.possible_etypes(select, rql_var, prefix)]

    def etypes_suggestion_set(self):
        """returns the list of possible entity types to suggest

        The default is to return any non-final entity type available
        in the schema.

        Can be overridden for instance if an application decides
        to restrict this list to a meaningful set of business etypes.
        """
        schema = self._cw.vreg.schema
        return set(eschema.type for eschema in schema.entities() if not eschema.final)

    def possible_etypes(self, select, rql_var, prefix=''):
        """return all possible etypes for `rql_var`

        The returned list will always be a subset of meth:`etypes_suggestion_set`

        :param select: the annotated select node (rql syntax tree)
        :param rql_var: the variable name for which we want to know possible types
        :param prefix: if specified, will only return etypes starting with it
        """
        available_etypes = self.etypes_suggestion_set()
        possible_etypes = set()
        for sol in select.solutions:
            if rql_var in sol and sol[rql_var] in available_etypes:
                possible_etypes.add(sol[rql_var])
        if not possible_etypes:
            # `Any X WHERE X is Person, Y is`
            # -> won't have a solution, need to give all etypes
            possible_etypes = available_etypes
        return sorted(etype for etype in possible_etypes if etype.startswith(prefix))

    def possible_relations(self, select, rql_var, include_meta=False):
        """returns a list of couple (rtype, dest_var) for each possible
        relations with `rql_var` as subject.

        ``dest_var`` will be picked among availabel variables if types match,
        otherwise a new one will be created.
        """
        schema = self._cw.vreg.schema
        relations = set()
        untyped_dest_var = rqlvar_maker(defined=select.defined_vars).next()
        # for each solution
        # 1. find each possible relation
        # 2. for each relation:
        #    2.1. if the relation is meta, skip it
        #    2.2. for each possible destination type, pick up possible
        #         variables for this type or use a new one
        for sol in select.solutions:
            etype = sol[rql_var]
            sol_by_types = {}
            for varname, var_etype in sol.items():
                # don't push subject var to avoid "X relation X" suggestion
                if varname != rql_var:
                    sol_by_types.setdefault(var_etype, []).append(varname)
            for rschema in schema[etype].subject_relations():
                if include_meta or not rschema.meta:
                    for dest in rschema.objects(etype):
                        for varname in sol_by_types.get(dest.type, (untyped_dest_var,)):
                            suggestion = (rschema.type, varname)
                            if suggestion not in relations:
                                relations.add(suggestion)
        return sorted(relations)

    def vocabulary(self, select, rql_var, user_rtype, rtype_incomplete_value):
        """return acceptable vocabulary for `rql_var` + `user_rtype` in `select`

        Vocabulary is either found from schema (Yams) definition or
        directly from database.
        """
        schema = self._cw.vreg.schema
        vocab = []
        for sol in select.solutions:
            # for each solution :
            # - If a vocabulary constraint exists on `rql_var+user_rtype`, use it
            #   to define possible values
            # - Otherwise, query the database to fetch available values from
            #   database (limiting results to `self.attr_value_limit`)
            try:
                eschema = schema.eschema(sol[rql_var])
                rdef = eschema.rdef(user_rtype)
            except KeyError: # unknown relation
                continue
            cstr = rdef.constraint_by_interface(IVocabularyConstraint)
            if cstr is not None:
                # a vocabulary is found, use it
                vocab += [value for value in cstr.vocabulary()
                          if value.startswith(rtype_incomplete_value)]
            elif rdef.final:
                # no vocab, query database to find possible value
                vocab_rql = 'DISTINCT Any V LIMIT %s WHERE X is %s, X %s V' % (
                    self.attr_value_limit, eschema.type, user_rtype)
                vocab_kwargs = {}
                if rtype_incomplete_value:
                    vocab_rql += ', X %s LIKE %%(value)s' % user_rtype
                    vocab_kwargs['value'] = '%s%%' % rtype_incomplete_value
                vocab += [value for value, in
                          self._cw.execute(vocab_rql, vocab_kwargs)]
        return sorted(set(vocab))



@ajaxfunc(output_type='json')
def rql_suggest(self):
    rql_builder = self._cw.vreg['components'].select_or_none('rql.suggestions', self._cw)
    if rql_builder:
        return rql_builder.build_suggestions(self._cw.form['term'])
    return []
