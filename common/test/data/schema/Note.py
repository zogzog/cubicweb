from cubicweb.schema import format_constraint

class AnotherNote(EntityType):
    descr_format = String(meta=True, internationalizable=True,
                                default='text/rest', constraints=[format_constraint])
    descr = String(fulltextindexed=True,
                   description=_('more detailed description'))
    descr2_format = String(meta=True, internationalizable=True,
                                default='text/rest', constraints=[format_constraint])
    descr2 = String(fulltextindexed=True,
                    description=_('more detailed description'))
    

class SubNote(AnotherNote):
    __specializes_schema__ = True
    descr3 = String()
