from __future__ import with_statement

# fix some corrupted entities noticed on several instances
rql('DELETE CWConstraint X WHERE NOT E constrained_by X')
rql('SET X is_instance_of Y WHERE X is Y, NOT X is_instance_of Y')
commit()

if confirm('fix existing cwuri?'):
    from logilab.common.shellutils import ProgressBar
    from cubicweb.server.session import hooks_control
    rset = rql('Any X, XC WHERE X cwuri XC, X cwuri ~= "%/eid/%"')
    pb = ProgressBar(nbops=rset.rowcount, size=70)
    with hooks_control(session, session.HOOKS_DENY_ALL, 'integrity'):
        for i,  e in enumerate(rset.entities()):
            e.set_attributes(cwuri=e.cwuri.replace('/eid', ''))
            if i % 100: # commit every 100 entities to limit memory consumption
                commit(ask_confirm=False)
            pb.update()
    commit(ask_confirm=False)

try:
    from cubicweb import devtools
    option_group_changed('anonymous-user', 'main', 'web')
    option_group_changed('anonymous-password', 'main', 'web')
except ImportError:
    # cubicweb-dev unavailable, nothing needed
    pass
