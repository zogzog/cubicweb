"""Pylint plugin for cubicweb"""

from astroid import MANAGER, InferenceError, nodes, scoped_nodes, ClassDef, FunctionDef
from astroid.builder import AstroidBuilder
from pylint.checkers.utils import unimplemented_abstract_methods, class_is_abstract


def turn_function_to_class(node):
    """turn a Function node into a Class node (in-place)"""
    node.__class__ = ClassDef
    node.bases = ()
    # remove return nodes so that we don't get warned about 'return outside
    # function' by pylint
    for rnode in node.nodes_of_class(nodes.Return):
        rnode.parent.body.remove(rnode)
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
            module.locals[etype] = [scoped_nodes.Class(etype, None)]
    # add data() to uiprops module
    if module.name.split('.')[-1] == 'uiprops':
        fake = AstroidBuilder(MANAGER).string_build('''
def data(string):
  return u''
''')
        module.locals['data'] = fake.locals['data']


def cubicweb_abstractmethods_transform(classdef):
    if class_is_abstract(classdef):
        return

    def is_abstract(method):
        return method.is_abstract(pass_is_abstract=False)

    methods = sorted(
        unimplemented_abstract_methods(classdef, is_abstract).items(),
        key=lambda item: item[0],
    )

    def dummy_method():
        """"""
    for name, method in methods:
        owner = method.parent.frame()
        if owner is classdef:
            continue
        if name not in classdef.locals:
            if name in ('entity_call', 'render_body'):
                classdef.set_local(name, dummy_method)


def register(linter):
    """called when loaded by pylint --load-plugins, nothing to do here"""
    MANAGER.register_transform(nodes.Module, cubicweb_transform)
    MANAGER.register_transform(nodes.ClassDef, cubicweb_abstractmethods_transform)
