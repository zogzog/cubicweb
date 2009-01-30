"""this module contains base classes for web tests

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
from math import log

from logilab.common.debugger import Debugger
from logilab.common.testlib import InnerTest
from logilab.common.pytest import nocoverage

from rql import parse

from cubicweb.devtools import VIEW_VALIDATORS
from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.devtools._apptest import unprotected_entities, SYSTEM_RELATIONS
from cubicweb.devtools.htmlparser import DTDValidator, SaxOnlyValidator, HTMLValidator
from cubicweb.devtools.fill import insert_entity_queries, make_relations_queries

from cubicweb.sobjects.notification import NotificationView

from cubicweb.vregistry import NoSelectableObject
from cubicweb.web.action import Action
from cubicweb.web.views.basetemplates import TheMainTemplate


## TODO ###############
# creation tests: make sure an entity was actually created
# Existing Test Environment

class CubicWebDebugger(Debugger):

    def do_view(self, arg):
        import webbrowser
        data = self._getval(arg)
        file('/tmp/toto.html', 'w').write(data)
        webbrowser.open('file:///tmp/toto.html')

def how_many_dict(schema, cursor, how_many, skip):
    """compute how many entities by type we need to be able to satisfy relations
    cardinality
    """
    # compute how many entities by type we need to be able to satisfy relation constraint
    relmap = {}
    for rschema in schema.relations():
        if rschema.meta or rschema.is_final(): # skip meta relations
            continue
        for subj, obj in rschema.iter_rdefs():
            card = rschema.rproperty(subj, obj, 'cardinality')
            if card[0] in '1?' and len(rschema.subjects(obj)) == 1:
                relmap.setdefault((rschema, subj), []).append(str(obj))
            if card[1] in '1?' and len(rschema.objects(subj)) == 1:
                relmap.setdefault((rschema, obj), []).append(str(subj))
    unprotected = unprotected_entities(schema)
    for etype in skip:
        unprotected.add(etype)
    howmanydict = {}
    for etype in unprotected_entities(schema, strict=True):
        howmanydict[str(etype)] = cursor.execute('Any COUNT(X) WHERE X is %s' % etype)[0][0]
        if etype in unprotected:
            howmanydict[str(etype)] += how_many
    for (rschema, etype), targets in relmap.iteritems():
        # XXX should 1. check no cycle 2. propagate changes
        relfactor = sum(howmanydict[e] for e in targets)
        howmanydict[str(etype)] = max(relfactor, howmanydict[etype])
    return howmanydict


def line_context_filter(line_no, center, before=3, after=None):
    """return true if line are in context
    if after is None: after = before"""
    if after is None:
        after = before
    return center - before <= line_no <= center + after

## base webtest class #########################################################
class WebTest(EnvBasedTC):
    """base class for web tests"""
    __abstract__ = True

    pdbclass = CubicWebDebugger
    # this is a hook to be able to define a list of rql queries
    # that are application dependent and cannot be guessed automatically
    application_rql = []

    # validators are used to validate (XML, DTD, whatever) view's content
    # validators availables are :
    #  DTDValidator : validates XML + declared DTD
    #  SaxOnlyValidator : guarantees XML is well formed
    #  None : do not try to validate anything
    # validators used must be imported from from.devtools.htmlparser
    content_type_validators = {
        # maps MIME type : validator name
        #
        # do not set html validators here, we need HTMLValidator for html
        # snippets
        #'text/html': DTDValidator,
        #'application/xhtml+xml': DTDValidator,
        'application/xml': SaxOnlyValidator,
        'text/xml': SaxOnlyValidator,
        'text/plain': None,
        'text/comma-separated-values': None,
        'text/x-vcard': None,
        'text/calendar': None,
        'application/json': None,
        'image/png': None,
        }
    vid_validators = {
        # maps vid : validator name (override content_type_validators)
        }
    valmap = {None: None, 'dtd': DTDValidator, 'xml': SaxOnlyValidator}
    no_auto_populate = ()
    ignored_relations = ()
    
    def __init__(self, *args, **kwargs):
        EnvBasedTC.__init__(self, *args, **kwargs)
        for view, valkey in VIEW_VALIDATORS.iteritems():
            self.validators[view] = self.valmap[valkey]
        
    def custom_populate(self, how_many, cursor):
        pass
        
    def post_populate(self, cursor):
        pass
    
    @nocoverage
    def auto_populate(self, how_many):
        """this method populates the database with `how_many` entities
        of each possible type. It also inserts random relations between them
        """
        cu = self.cursor()
        self.custom_populate(how_many, cu)
        vreg = self.vreg
        howmanydict = how_many_dict(self.schema, cu, how_many, self.no_auto_populate)
        for etype in unprotected_entities(self.schema):
            if etype in self.no_auto_populate:
                continue
            nb = howmanydict.get(etype, how_many)
            for rql, args in insert_entity_queries(etype, self.schema, vreg, nb):
                cu.execute(rql, args)
        edict = {}
        for etype in unprotected_entities(self.schema, strict=True):
            rset = cu.execute('%s X' % etype)
            edict[str(etype)] = set(row[0] for row in rset.rows)
        existingrels = {}
        ignored_relations = SYSTEM_RELATIONS + self.ignored_relations
        for rschema in self.schema.relations():
            if rschema.is_final() or rschema in ignored_relations:
                continue
            rset = cu.execute('DISTINCT Any X,Y WHERE X %s Y' % rschema)
            existingrels.setdefault(rschema.type, set()).update((x,y) for x, y in rset)
        q = make_relations_queries(self.schema, edict, cu, ignored_relations,
                                   existingrels=existingrels)
        for rql, args in q:
            cu.execute(rql, args)
        self.post_populate(cu)
        self.commit()

    @nocoverage
    def _check_html(self, output, view, template='main'):
        """raises an exception if the HTML is invalid"""
        try:
            validatorclass = self.vid_validators[view.id]
        except KeyError:
            if template is None:
                default_validator = HTMLValidator
            else:
                default_validator = DTDValidator
            validatorclass = self.content_type_validators.get(view.content_type,
                                                              default_validator)
        if validatorclass is None:
            return None
        validator = validatorclass()
        return validator.parse_string(output.strip())


    def view(self, vid, rset, req=None, template='main', **kwargs):
        """This method tests the view `vid` on `rset` using `template`

        If no error occured while rendering the view, the HTML is analyzed
        and parsed.

        :returns: an instance of `cubicweb.devtools.htmlparser.PageInfo`
                  encapsulation the generated HTML
        """
        req = req or rset.req
        # print "testing ", vid,
        # if rset:
        #     print rset, len(rset), id(rset)
        # else:
        #     print 
        req.form['vid'] = vid
        view = self.vreg.select_view(vid, req, rset, **kwargs)
        # set explicit test description
        if rset is not None:
            self.set_description("testing %s, mod=%s (%s)" % (vid, view.__module__, rset.printable_rql()))
        else:
            self.set_description("testing %s, mod=%s (no rset)" % (vid, view.__module__))
        viewfunc = lambda **k: self.vreg.main_template(req, template, **kwargs)
        if template is None: # raw view testing, no template
            viewfunc = view.dispatch
        elif template == 'main':
            _select_view_and_rset = TheMainTemplate._select_view_and_rset
            # patch TheMainTemplate.process_rql to avoid recomputing resultset
            TheMainTemplate._select_view_and_rset = lambda *a, **k: (view, rset)
        try:
            return self._test_view(viewfunc, view, template, **kwargs)
        finally:
            if template == 'main':
                TheMainTemplate._select_view_and_rset = _select_view_and_rset


    def _test_view(self, viewfunc, view, template='main', **kwargs):
        """this method does the actual call to the view

        If no error occured while rendering the view, the HTML is analyzed
        and parsed.

        :returns: an instance of `cubicweb.devtools.htmlparser.PageInfo`
                  encapsulation the generated HTML
        """
        output = None
        try:
            output = viewfunc(**kwargs)
            return self._check_html(output, view, template)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            # hijack exception: generative tests stop when the exception
            # is not an AssertionError
            klass, exc, tcbk = sys.exc_info()
            try:
                msg = '[%s in %s] %s' % (klass, view.id, exc)
            except:
                msg = '[%s in %s] undisplayable exception' % (klass, view.id)
            if output is not None:
                position = getattr(exc, "position", (0,))[0]
                if position:
                    # define filter
                    output = output.splitlines()
                    width = int(log(len(output), 10)) + 1
                    line_template = " %" + ("%i" % width) + "i: %s"
                    # XXX no need to iterate the whole file except to get
                    # the line number
                    output = '\n'.join(line_template % (idx + 1, line)
                                for idx, line in enumerate(output)
                                if line_context_filter(idx+1, position))
                    msg+= '\nfor output:\n%s' % output
            raise AssertionError, msg, tcbk


    def to_test_etypes(self):
        return unprotected_entities(self.schema, strict=True)
    
    def iter_automatic_rsets(self):
        """generates basic resultsets for each entity type"""
        etypes = self.to_test_etypes()
        for etype in etypes:
            yield self.execute('Any X WHERE X is %s' % etype)

        etype1 = etypes.pop()
        etype2 = etypes.pop()
        # test a mixed query (DISTINCT/GROUP to avoid getting duplicate
        # X which make muledit view failing for instance (html validation fails
        # because of some duplicate "id" attributes)
        yield self.execute('DISTINCT Any X, MAX(Y) GROUPBY X WHERE X is %s, Y is %s' % (etype1, etype2))
        # test some application-specific queries if defined
        for rql in self.application_rql:
            yield self.execute(rql)

                
    def list_views_for(self, rset):
        """returns the list of views that can be applied on `rset`"""
        req = rset.req
        only_once_vids = ('primary', 'secondary', 'text')
        req.data['ex'] = ValueError("whatever")
        for vid, views in self.vreg.registry('views').items():
            if vid[0] == '_':
                continue
            if rset.rowcount > 1 and vid in only_once_vids:
                continue
            views = [view for view in views
                     if view.category != 'startupview'
                     and not issubclass(view, NotificationView)]
            if views:
                try:
                    view = self.vreg.select(views, req, rset)
                    if view.linkable():
                        yield view
                    else:
                        not_selected(self.vreg, view)
                    # else the view is expected to be used as subview and should
                    # not be tested directly
                except NoSelectableObject:
                    continue

    def list_actions_for(self, rset):
        """returns the list of actions that can be applied on `rset`"""
        req = rset.req
        for action in self.vreg.possible_objects('actions', req, rset):
            yield action

    def list_boxes_for(self, rset):
        """returns the list of boxes that can be applied on `rset`"""
        req = rset.req
        for box in self.vreg.possible_objects('boxes', req, rset):
            yield box
            
    def list_startup_views(self):
        """returns the list of startup views"""
        req = self.request()
        for view in self.vreg.possible_views(req, None):
            if view.category == 'startupview':
                yield view.id
            else:
                not_selected(self.vreg, view)
                
    def _test_everything_for(self, rset):
        """this method tries to find everything that can be tested
        for `rset` and yields a callable test (as needed in generative tests)
        """
        propdefs = self.vreg['propertydefs']
        # make all components visible
        for k, v in propdefs.items():
            if k.endswith('visible') and not v['default']:
                propdefs[k]['default'] = True
        for view in self.list_views_for(rset):
            backup_rset = rset._prepare_copy(rset.rows, rset.description)
            yield InnerTest(self._testname(rset, view.id, 'view'),
                            self.view, view.id, rset,
                            rset.req.reset_headers(), 'main')
            # We have to do this because some views modify the
            # resultset's syntax tree
            rset = backup_rset
        for action in self.list_actions_for(rset):
            # XXX this seems a bit dummy
            #yield InnerTest(self._testname(rset, action.id, 'action'),
            #                self.failUnless,
            #                isinstance(action, Action))
            yield InnerTest(self._testname(rset, action.id, 'action'), action.url)
        for box in self.list_boxes_for(rset):
            yield InnerTest(self._testname(rset, box.id, 'box'), box.dispatch)

    @staticmethod
    def _testname(rset, objid, objtype):
        return '%s_%s_%s' % ('_'.join(rset.column_types(0)), objid, objtype)
            

class AutomaticWebTest(WebTest):
    """import this if you wan automatic tests to be ran"""
    ## one each
    def test_one_each_config(self):
        self.auto_populate(1)
        for rset in self.iter_automatic_rsets():
            for testargs in self._test_everything_for(rset):
                yield testargs

    ## ten each
    def test_ten_each_config(self):
        self.auto_populate(10)
        for rset in self.iter_automatic_rsets():
            for testargs in self._test_everything_for(rset):
                yield testargs
                
    ## startup views
    def test_startup_views(self):
        for vid in self.list_startup_views():
            req = self.request()
            yield self.view, vid, None, req


class RealDBTest(WebTest):

    def iter_individual_rsets(self, etypes=None, limit=None):
        etypes = etypes or unprotected_entities(self.schema, strict=True)
        for etype in etypes:
            rset = self.execute('Any X WHERE X is %s' % etype)
            for row in xrange(len(rset)):
                if limit and row > limit:
                    break
                rset2 = rset.limit(limit=1, offset=row)
                yield rset2

def not_selected(vreg, vobject):
    try:
        vreg._selected[vobject.__class__] -= 1
    except (KeyError, AttributeError):
        pass
        
def vreg_instrumentize(testclass):
    from cubicweb.devtools.apptest import TestEnvironment
    env = testclass._env = TestEnvironment('data', configcls=testclass.configcls,
                                           requestcls=testclass.requestcls)
    vreg = env.vreg
    vreg._selected = {}
    orig_select = vreg.__class__.select
    def instr_select(self, *args, **kwargs):
        selected = orig_select(self, *args, **kwargs)
        try:
            self._selected[selected.__class__] += 1
        except KeyError:
            self._selected[selected.__class__] = 1
        except AttributeError:
            pass # occurs on vreg used to restore database
        return selected
    vreg.__class__.select = instr_select

def print_untested_objects(testclass, skipregs=('hooks', 'etypes')):
    vreg = testclass._env.vreg
    for registry, vobjectsdict in vreg.items():
        if registry in skipregs:
            continue
        for vobjects in vobjectsdict.values():
            for vobject in vobjects:
                if not vreg._selected.get(vobject):
                    print 'not tested', registry, vobject
