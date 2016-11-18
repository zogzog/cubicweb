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
        col=user.cw_col)
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
    if eid in _user_cache:
        user, lang = _user_cache[eid]
        entity = clone_user(repo, user)
        return entity, lang

    with repo.internal_cnx() as cnx:
        user = repo._build_user(cnx, eid)
        lang = user.prefered_language()
        user.cw_clear_relation_cache()
        _user_cache[eid] = (clone_user(repo, user), lang)
        return user, lang


def clear_cache():
    """Clear the user cache"""
    _user_cache.clear()


def includeme(config):
    """Start the cache maintenance loop task.

    Automatically included by :func:`cubicweb.pyramid.make_cubicweb_application`.
    """
    repo = config.registry['cubicweb.repository']
    interval = int(config.registry.settings.get(
        'cubicweb.usercache.expiration_time', 60 * 5))
    repo.looping_task(interval, clear_cache)
