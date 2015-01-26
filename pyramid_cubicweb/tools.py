"""Various tools.

.. warning::

    This module should be considered as internal implementation details. Use
    with caution, as the API may change without notice.
"""

#: A short-term cache for user clones.
#: used by cached_build_user to speed-up repetitive calls to build_user
#: The expiration is handled in a dumb and brutal way: the whole cache is
#: cleared every 5 minutes.
_user_cache = {}


def clone_user(repo, user):
    """Clone a CWUser instance.

    .. warning::

        The returned clone is detached from any cnx.
        Before using it in any way, it should be attached to a cnx that has not
        this user already loaded.
    """
    CWUser = repo.vreg['etypes'].etype_class('CWUser')
    clone = CWUser(
        None,
        rset=user.cw_rset.copy(),
        row=user.cw_row,
        col=user.cw_col,
        groups=set(user._groups) if hasattr(user, '_groups') else None,
        properties=dict(user._properties)
        if hasattr(user, '_properties') else None)
    clone.cw_attr_cache = dict(user.cw_attr_cache)
    return clone


def cnx_attach_entity(cnx, entity):
    """Attach an entity to a cnx."""
    entity._cw = cnx
    if entity.cw_rset:
        entity.cw_rset.req = cnx


def cached_build_user(repo, eid):
    """Cached version of
    :meth:`cubicweb.server.repository.Repository._build_user`
    """
    with repo.internal_cnx() as cnx:
        if eid in _user_cache:
            entity = clone_user(repo, _user_cache[eid])
            # XXX the cnx is needed here so that the CWUser instance has an
            # access to the vreg, which it needs when its 'prefered_language'
            # property is accessed.
            # If this property did not need a cnx to access a vreg, we could
            # avoid the internal_cnx() and save more time.
            cnx_attach_entity(cnx, entity)
            return entity

        user = repo._build_user(cnx, eid)
        user.cw_clear_relation_cache()
        _user_cache[eid] = clone_user(repo, user)
        return user


def clear_cache():
    """Clear the user cache"""
    _user_cache.clear()


def includeme(config):
    """Start the cache maintenance loop task.

    Automatically included by :func:`pyramid_cubicweb.make_cubicweb_application`.
    """
    repo = config.registry['cubicweb.repository']
    interval = int(config.registry.settings.get(
        'cubicweb.usercache.expiration_time', 60*5))
    repo.looping_task(interval, clear_cache)
