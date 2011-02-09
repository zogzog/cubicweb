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
