"""Pylint plugin to analyse cubicweb cubes

Done:
* turn functions decorated by @objectify_predicate into classes
* add yams base types to yams.buildobjs module
* add data() function to uiprops module's namespace
* avoid 'abstract method not implemented' for `cell_call`, `entity_call`, `render_body`
* avoid invalid-name on schema relation class names

TODO:
* avoid invalid class name for predicates and predicates
* W:188, 0: Method '__lt__' is abstract in class 'Entity' but is not overridden (abstract-method)
* generate entity attributes from the schema?
"""

from astroid import MANAGER, InferenceError, nodes, ClassDef, FunctionDef
from astroid.builder import AstroidBuilder

from pylint.checkers.utils import unimplemented_abstract_methods, class_is_abstract


def turn_function_to_class(node):
    """turn a Function node into a Class node (in-place)"""
    node.__class__ = ClassDef
    node.bases = ()
    # mark class as a new style class
    node._newstyle = True
    # remove return nodes so that we don't get warned about 'return outside
    # function' by pylint
    for rnode in node.nodes_of_class(nodes.Return):
        rnode.parent.body.remove(rnode)
    # add __init__ method to avoid no-init

    # that seems to be enough :)


def cubicweb_transform(module):
    # handle objectify_predicate decorator (and its former name until bw compat
    # is kept). Only look at module level functions, should be enough.
    for assnodes in module.locals.values():
        for node in assnodes:
            if isinstance(node, FunctionDef) and node.decorators:
                for decorator in node.decorators.nodes:
                    try:
                        for infered in decorator.infer():
                            if infered.name in ('objectify_predicate', 'objectify_selector'):
                                turn_function_to_class(node)
                                break
                        else:
                            continue
                        break
                    except InferenceError:
                        continue
    # add yams base types into 'yams.buildobjs', astng doesn't grasp globals()
    # magic in there
    if module.name == 'yams.buildobjs':
        from yams import BASE_TYPES
        for etype in BASE_TYPES:
            module.locals[etype] = [ClassDef(etype, None)]
    # add data() to uiprops module
    elif module.name.split('.')[-1] == 'uiprops':
        fake = AstroidBuilder(MANAGER).string_build('''
def data(string):
  return u''
''')
        module.locals['data'] = fake.locals['data']
    # handle lower case with underscores for relation names in schema.py
    if not module.qname().endswith('.schema'):
        return
    schema_locals = module.locals
    for assnodes in schema_locals.values():
        for node in assnodes:
            if not isinstance(node, ClassDef):
                continue
            # XXX can we infer ancestor classes? it would be better to know for sure that
            # one of the mother classes is yams.buildobjs.RelationDefinition for instance
            for base in node.basenames:
                if base in ('RelationDefinition', 'ComputedRelation', 'RelationType'):
                    new_name = node.name.replace('_', '').capitalize()
                    schema_locals[new_name] = schema_locals[node.name]
                    del schema_locals[node.name]
                    node.name = new_name


def cubicweb_abstractmethods_transform(classdef):
    if class_is_abstract(classdef):
        return

    def is_abstract(method):
        return method.is_abstract(pass_is_abstract=False)

    methods = sorted(
        unimplemented_abstract_methods(classdef, is_abstract).items(),
        key=lambda item: item[0],
    )

    dummy_method = AstroidBuilder(MANAGER).string_build('''
def dummy_method(self):
   """"""
''')

    for name, method in methods:
        owner = method.parent.frame()
        if owner is classdef:
            continue
        if name not in classdef.locals:
            if name in ('cell_call', 'entity_call', 'render_body'):
                classdef.set_local(name, dummy_method)


def register(linter):
    """called when loaded by pylint --load-plugins, nothing to do here"""
    MANAGER.register_transform(nodes.Module, cubicweb_transform)
    MANAGER.register_transform(ClassDef, cubicweb_abstractmethods_transform)
