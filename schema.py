# pylint: disable-msg=E0611,F0401
from yams.buildobjs import EntityType, Bytes


class CWSession(EntityType):
    """
    Persistent session support

    Used by pyramid_cubiweb to store the session datas.

    It is a partial copy of the yet-to-integrate patch of cubicweb that
    provides cubicweb sessions persistency.

    While the same structure will be used by pyramid_cubicweb persistent
    sessions and Cubicweb persistent sessions, the two concepts are slightly
    different and will NOT co-exist in a single application.
    """

    __permissions__ = {
        'read':   (),
        'add':    (),
        'update': (),
        'delete': ()
    }

    cwsessiondata = Bytes()
