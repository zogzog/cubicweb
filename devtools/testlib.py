"""this module contains base classes for web tests

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
from math import log

from logilab.common.debugger import Debugger
from logilab.common.testlib import InnerTest
from logilab.common.pytest import nocoverage

from cubicweb.devtools import VIEW_VALIDATORS
from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.devtools._apptest import unprotected_entities, SYSTEM_RELATIONS
from cubicweb.devtools.htmlparser import DTDValidator, SaxOnlyValidator, HTMLValidator
from cubicweb.devtools.fill import insert_entity_queries, make_relations_queries

from cubicweb.sobjects.notification import NotificationView

from cubicweb.vregistry import NoSelectableObject


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
        if rschema.is_final():
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
VALMAP = {None: None, 'dtd': DTDValidator, 'xml': SaxOnlyValidator}

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
    # maps vid : validator name (override content_type_validators)
    vid_validators = dict((vid, VALMAP[valkey])
                          for vid, valkey in VIEW_VALIDATORS.iteritems())

    no_auto_populate = ()
    ignored_relations = ()

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
            existingrels.setdefault(rschema.type, set()).update((x, y) for x, y in rset)
        q = make_relations_queries(self.schema, edict, cu, ignored_relations,
                                   existingrels=existingrels)
        for rql, args in q:
            cu.execute(rql, args)
        self.post_populate(cu)
        self.commit()

    @nocoverage
    def _check_html(self, output, view, template='main-template'):
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


    def view(self, vid, rset=None, req=None, template='main-template',
             **kwargs):
        """This method tests the view `vid` on `rset` using `template`

        If no error occured while rendering the view, the HTML is analyzed
        and parsed.

        :returns: an instance of `cubicweb.devtools.htmlparser.PageInfo`
                  encapsulation the generated HTML
        """
        req = req or rset and rset.req or self.request()
        req.form['vid'] = vid
        kwargs['rset'] = rset
        viewsreg = self.vreg['views']
        view = viewsreg.select(vid, req, **kwargs)
        # set explicit test description
        if rset is not None:
            self.set_description("testing %s, mod=%s (%s)" % (
                vid, view.__module__, rset.printable_rql()))
        else:
            self.set_description("testing %s, mod=%s (no rset)" % (
                vid, view.__module__))
        if template is None: # raw view testing, no template
            viewfunc = view.render
        else:
            kwargs['view'] = view
            templateview = viewsreg.select(template, req, **kwargs)
            viewfunc = lambda **k: viewsreg.main_template(req, template,
                                                          **kwargs)
        kwargs.pop('rset')
        return self._test_view(viewfunc, view, template, kwargs)


    def _test_view(self, viewfunc, view, template='main-template', kwargs={}):
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
                    msg += '\nfor output:\n%s' % output
            raise AssertionError, msg, tcbk


    def to_test_etypes(self):
        return unprotected_entities(self.schema, strict=True)

    def iter_automatic_rsets(self, limit=10):
        """generates basic resultsets for each entity type"""
        etypes = self.to_test_etypes()
        if not etypes:
            return
        for etype in etypes:
            yield self.execute('Any X LIMIT %s WHERE X is %s' % (limit, etype))
        etype1 = etypes.pop()
        try:
            etype2 = etypes.pop()
        except KeyError:
            etype2 = etype1
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
        viewsvreg = self.vreg['views']
        for vid, views in viewsvreg.items():
            if vid[0] == '_':
                continue
            if rset.rowcount > 1 and vid in only_once_vids:
                continue
            views = [view for view in views
                     if view.category != 'startupview'
                     and not issubclass(view, NotificationView)]
            if views:
                try:
                    view = viewsvreg.select_best(views, req, rset=rset)
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
        for action in self.vreg['actions'].possible_objects(req, rset=rset):
            yield action

    def list_boxes_for(self, rset):
        """returns the list of boxes that can be applied on `rset`"""
        req = rset.req
        for box in self.vreg['boxes'].possible_objects(req, rset=rset):
            yield box

    def list_startup_views(self):
        """returns the list of startup views"""
        req = self.request()
        for view in self.vreg['views'].possible_views(req, None):
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
                            rset.req.reset_headers(), 'main-template')
            # We have to do this because some views modify the
            # resultset's syntax tree
            rset = backup_rset
        for action in self.list_actions_for(rset):
            yield InnerTest(self._testname(rset, action.id, 'action'), self._test_action, action)
        for box in self.list_boxes_for(rset):
            yield InnerTest(self._testname(rset, box.id, 'box'), box.render)

    @staticmethod
    def _testname(rset, objid, objtype):
        return '%s_%s_%s' % ('_'.join(rset.column_types(0)), objid, objtype)


class AutomaticWebTest(WebTest):
    """import this if you wan automatic tests to be ran"""
    ## one each
    def test_one_each_config(self):
        self.auto_populate(1)
        for rset in self.iter_automatic_rsets(limit=1):
            for testargs in self._test_everything_for(rset):
                yield testargs

    ## ten each
    def test_ten_each_config(self):
        self.auto_populate(10)
        for rset in self.iter_automatic_rsets(limit=10):
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

def not_selected(vreg, appobject):
    try:
        vreg._selected[appobject.__class__] -= 1
    except (KeyError, AttributeError):
        pass

def vreg_instrumentize(testclass):
    from cubicweb.devtools.apptest import TestEnvironment
    env = testclass._env = TestEnvironment('data', configcls=testclass.configcls,
                                           requestcls=testclass.requestcls)
    for reg in env.vreg.values():
        reg._selected = {}
        try:
            orig_select_best = reg.__class__.__orig_select_best
        except:
            orig_select_best = reg.__class__.select_best
        def instr_select_best(self, *args, **kwargs):
            selected = orig_select_best(self, *args, **kwargs)
            try:
                self._selected[selected.__class__] += 1
            except KeyError:
                self._selected[selected.__class__] = 1
            except AttributeError:
                pass # occurs on reg used to restore database
            return selected
        reg.__class__.select_best = instr_select_best
        reg.__class__.__orig_select_best = orig_select_best

def print_untested_objects(testclass, skipregs=('hooks', 'etypes')):
    for regname, reg in testclass._env.vreg.iteritems():
        if regname in skipregs:
            continue
        for appobjects in reg.itervalues():
            for appobject in appobjects:
                if not reg._selected.get(appobject):
                    print 'not tested', regname, appobject
