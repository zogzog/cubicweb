"""a query preprocesser to handle quick search shortcuts for cubicweb


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"

import re
from logging import getLogger

from rql import RQLSyntaxError, BadRQLQuery, parse
from rql.nodes import Relation

from cubicweb import Unauthorized, typed_eid
from cubicweb.view import Component

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

    def process_query(self, uquery, req):
        args = self.preprocess_query(uquery, req)
        try:
            return req.execute(*args)
        finally:
            # rollback necessary to avoid leaving the connection in a bad state
            req.cnx.rollback()

    def preprocess_query(self, uquery, req):
        raise NotImplementedError()




class DoNotPreprocess(BaseQueryProcessor):
    """this one returns the raw query and should be placed in first position
    of the chain
    """
    name = 'rql'
    priority = 0
    def preprocess_query(self, uquery, req):
        return uquery,


class QueryTranslator(BaseQueryProcessor):
    """ parses through rql and translates into schema language entity names
    and attributes
    """
    priority = 2
    def preprocess_query(self, uquery, req):
        rqlst = parse(uquery, print_errors=False)
        schema = self._cw.vreg.schema
        # rql syntax tree will be modified in place if necessary
        translate_rql_tree(rqlst, trmap(self._cw.config, schema, req.lang), schema)
        return rqlst.as_string(),


class QSPreProcessor(BaseQueryProcessor):
    """Quick search preprocessor

    preprocessing query in shortcut form to their RQL form
    """
    priority = 4

    def preprocess_query(self, uquery, req):
        """try to get rql from an unicode query string"""
        args = None
        self._cw = req
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
            return trmap(self._cw.config, self._cw.vreg.schema, self._cw.lang)[etype]
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
        translations = trmap(self._cw.config, self._cw.vreg.schema, self._cw.lang)
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
            eid = typed_eid(word)
            return 'Any X WHERE X eid %(x)s', {'x': eid}, 'x'
        except ValueError:
            etype = self._get_entity_type(word)
            return '%s %s' % (etype, etype[0]),

    def _complete_rql(self, searchstr, etype, rtype=None, var=None, searchattr=None):
        searchop = ''
        if '%' in searchstr:
            if rtype:
                possible_etypes = self._cw.schema.rschema(rtype).objects(etype)
            else:
                possible_etypes = [self._cw.schema.eschema(etype)]
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
        rql = '%s %s WHERE %s' % (etype, etype[0], self._complete_rql(word2, etype))
        return rql, {'text': word2}

    def _three_words_query(self, word1, word2, word3):
        """Specific process for three words query (case (3) of preprocess_rql)
        """
        etype = self._get_entity_type(word1)
        eschema = self._cw.schema.eschema(etype)
        rtype = self._get_attribute_name(word2, eschema)
        # expand shortcut if rtype is a non final relation
        if not self._cw.schema.rschema(rtype).is_final():
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
        rql =  '%s %s WHERE %s %s %s, %s' % (etype, mainvar,  # Person P
                                             mainvar, rtype, searchvar, # P worksAt C
                                             self._complete_rql(searchstr, etype,
                                                                rtype=rtype, var=searchvar))
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
            except BadRQLQuery, error:
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

    def preprocess_query(self, uquery, req):
        """suppose it's a plain text query"""
        return 'Any X WHERE X has_text %(text)s', {'text': uquery}



class MagicSearchComponent(Component):
    __regid__  = 'magicsearch'
    def __init__(self, req, rset=None):
        super(MagicSearchComponent, self).__init__(req, rset=rset)
        processors = []
        self.by_name = {}
        for processorcls in self._cw.vreg['components']['magicsearch_processor']:
            # instantiation needed
            processor = processorcls()
            processors.append(processor)
            if processor.name is not None:
                assert not processor.name in self.by_name
                self.by_name[processor.name.lower()] = processor
        self.processors = sorted(processors, key=lambda x: x.priority)

    def process_query(self, uquery, req):
        assert isinstance(uquery, unicode)
        try:
            procname, query = uquery.split(':', 1)
            proc = self.by_name[procname.strip().lower()]
            uquery = query.strip()
        except:
            # use processor chain
            unauthorized = None
            for proc in self.processors:
                try:
                    return proc.process_query(uquery, req)
                # FIXME : we don't want to catch any exception type here !
                except (RQLSyntaxError, BadRQLQuery):
                    pass
                except Unauthorized, ex:
                    unauthorized = ex
                    continue
                except Exception, ex:
                    LOGGER.debug('%s: %s', ex.__class__.__name__, ex)
                    continue
            if unauthorized:
                raise unauthorized
        else:
            # let exception propagate
            return proc.process_query(uquery, req)
        raise BadRQLQuery(req._('sorry, the server is unable to handle this query'))
