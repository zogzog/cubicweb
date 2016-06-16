import sys

if confirm('fix some corrupted entities noticed on several instances?'):
    rql('DELETE CWConstraint X WHERE NOT E constrained_by X')
    rql('SET X is_instance_of Y WHERE X is Y, NOT X is_instance_of Y')
    commit()

if confirm('fix existing cwuri?'):
    from logilab.common.shellutils import progress
    from cubicweb.server.session import hooks_control
    rset = rql('Any X, XC WHERE X cwuri XC, X cwuri ~= "%/eid/%"')
    title = "%i entities to fix" % len(rset)
    nbops = rset.rowcount
    enabled = interactive_mode
    with progress(title=title, nbops=nbops, size=30, enabled=enabled) as pb:
        for i,  row in enumerate(rset):
            with session.deny_all_hooks_but('integrity'):
                data = {'eid': row[0], 'cwuri': row[1].replace(u'/eid', u'')}
                rql('SET X cwuri %(cwuri)s WHERE X eid %(eid)s', data)
            if not i % 100: # commit every 100 entities to limit memory consumption
                pb.text = "%i committed" % i
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
