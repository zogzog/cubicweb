"""hooks triggered on email entities creation:

* look for state change instruction (XXX security)
* set email content as a comment on an entity when comments are supported and
  linking information are found

:organization: Logilab
:copyright: 2003-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import re

from cubicweb import UnknownEid, typed_eid
from cubicweb.view import Component

        # XXX use user session if gpg signature validated

class TextAnalyzer(Component):
    """analyze and extract information from plain text by calling registered
    text parsers
    """
    id = 'textanalyzer'

    def parse(self, caller, text):
        for parsercls in self.req.vreg['components'].get('textparser', ()):
            parsercls(self.req).parse(caller, text)


class TextParser(Component):
    """base class for text parser, responsible to extract some information
    from plain text. When something is done, it usually call the

      .fire_event(something, {event args})

    method on the caller.
    """
    id = 'textparser'
    __abstract__ = True

    def parse(self, caller, text):
        raise NotImplementedError


class ChangeStateTextParser(TextParser):
    """search some text for change state instruction in the form

         :<transition name>: #?<eid>
    """
    instr_rgx = re.compile(':(\w+):\s*#?(\d+)', re.U)

    def parse(self, caller, text):
        for trname, eid in self.instr_rgx.findall(text):
            try:
                entity = self.req.entity_from_eid(typed_eid(eid))
            except UnknownEid:
                self.error("can't get entity with eid %s", eid)
                continue
            if not hasattr(entity, 'in_state'):
                self.error('bad change state instruction for eid %s', eid)
                continue
            tr = entity.current_workflow and entity.current_workflow.transition_by_name(trname)
            if tr and tr.may_be_fired(entity.eid):
                try:
                    trinfo = entity.fire_transition(tr)
                    caller.fire_event('state-changed', {'trinfo': trinfo,
                                                        'entity': entity})
                except:
                    self.exception('while changing state of %s', entity)
            else:
                self.error("can't pass transition %s on entity %s",
                           trname, entity)
