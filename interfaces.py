"""Specific views for entities implementing IDownloadable

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

from logilab.common.interface import Interface

class IEmailable(Interface):
    """interface for emailable entities"""
    
    def get_email(self):
        """return email address"""

    @classmethod
    def allowed_massmail_keys(cls):
        """returns a set of allowed email substitution keys

        The default is to return the entity's attribute list but an
        entity class might override this method to allow extra keys.
        For instance, the Person class might want to return a `companyname`
        key.
        """

    def as_email_context(self):
        """returns the dictionary as used by the sendmail controller to
        build email bodies.
        
        NOTE: the dictionary keys should match the list returned by the
        `allowed_massmail_keys` method.
        """


class IWorkflowable(Interface):
    """interface for entities dealing with a specific workflow"""

    @property
    def state(self):
        """return current state"""

    def change_state(self, stateeid, trcomment=None, trcommentformat=None):
        """change the entity's state according to a state defined in given
        parameters
        """
    
    def can_pass_transition(self, trname):
        """return true if the current user can pass the transition with the
        given name
        """
    
    def latest_trinfo(self):
        """return the latest transition information for this entity
        """

class IProgress(Interface):
    """something that has a cost, a state and a progression

    Take a look at cubicweb.common.mixins.ProgressMixIn for some
    default implementations
    """

    @property
    def cost(self):
        """the total cost"""

    @property
    def done(self):
        """what is already done"""

    @property
    def todo(self):
        """what remains to be done"""
    
    def progress_info(self):
        """returns a dictionary describing progress/estimated cost of the
        version.

        mandatory keys are (''estimated', 'done', 'todo')
        optional keys are ('notestimated', 'notestimatedcorrected',
                           'estimatedcorrected')
       'noestimated' and 'notestimatedcorrected' should default to 0
       'estimatedcorrected' should default to 'estimated'
       """

    def finished(self):
        """returns True if status is finished"""

    def in_progress(self):
        """returns True if status is not finished"""

    def progress(self):
        """returns the % progress of the task item"""
        
    
class IMileStone(IProgress):
    """represents an ITask's item"""
    
    parent_type = None # specify main task's type
    
    def get_main_task(self):
        """returns the main ITask entity"""

    def initial_prevision_date(self):
        """returns the initial expected end of the milestone"""
        
    def eta_date(self):
        """returns expected date of completion based on what remains
        to be done
        """

    def completion_date(self):
        """returns date on which the subtask has been completed"""

    def contractors(self):
        """returns the list of persons supposed to work on this task"""


class ITree(Interface):

    def parent(self):
        """returns the parent entity"""

    def children(self):
        """returns the item's children"""

    def __iter__(self):
        """iterates over the item's children"""
        
    def is_leaf(self):
        """returns true if this node as no child"""

    def is_root(self):
        """returns true if this node has no parent"""

    def root(self):
        """return the root object"""


## web specific interfaces ####################################################


class IPrevNext(Interface):
    """interface for entities which can be linked to a previous and/or next
    entity
    """
    
    def next_entity(self):
        """return the 'next' entity"""
    def previous_entity(self):
        """return the 'previous' entity"""


class IBreadCrumbs(Interface):
    """interface for entities which can be "located" on some path"""
    
    def breadcrumbs(self, view, recurs=False):
        """return a list containing some:
        
        * tuple (url, label)
        * entity
        * simple label string

        defining path from a root to the current view

        the main view is given as argument so breadcrumbs may vary according
        to displayed view (may be None). When recursing on a parent entity,
        the `recurs` argument should be set to True.
        """


class IDownloadable(Interface):
    """interface for downloadable entities"""
    
    def download_url(self): # XXX not really part of this interface
        """return an url to download entity's content"""
    def download_content_type(self):
        """return MIME type of the downloadable content"""
    def download_encoding(self):
        """return encoding of the downloadable content"""
    def download_file_name(self):
        """return file name of the downloadable content"""
    def download_data(self):
        """return actual data of the downloadable content"""


class IEmbedable(Interface):
    """interface for embedable entities"""
    
    def embeded_url(self):
        """embed action interface"""
    
class ICalendarable(Interface):
    """interface for itms that do have a begin date 'start' and an end
date 'stop'"""    
    
class ICalendarViews(Interface):
    """calendar views interface"""
    def matching_dates(self, begin, end):
        """
        :param begin: day considered as begin of the range (`DateTime`)
        :param end: day considered as end of the range (`DateTime`)
        
        :return:
          a list of dates (`DateTime`) in the range [`begin`, `end`] on which
          this entity apply
        """
        
class ITimetableViews(Interface):
    """timetable views interface"""
    def timetable_date(self):
        """XXX explain
        
        :return: date (`DateTime`)
        """

class IGeocodable(Interface):
    """interface required by geocoding views such as gmap-view"""

    @property
    def latitude(self):
        """returns the latitude of the entity"""

    @property
    def longitude(self):
        """returns the longitude of the entity"""

    def marker_icon(self):
        """returns the icon that should be used as the marker
        (returns None for default)
        """
        
class IFeed(Interface):
    """interface for entities with rss flux"""
    
    def rss_feed_url(self):
        """return an url which layout sub-entities item
        """
class ISiocItem(Interface):
    """interface for entities (which are item
    in sioc specification) with sioc views"""
    
    def isioc_content(self):
        """return content entity"""

    def isioc_container(self):
        """return container entity"""

    def isioc_type(self):
        """return container type (post, BlogPost, MailMessage)"""

    def isioc_replies(self):
        """return replies items"""       

    def isioc_topics(self):
        """return topics items"""
            
class ISiocContainer(Interface):
    """interface for entities (which are container
    in sioc specification) with sioc views"""

    def isioc_type(self):
        """return container type (forum, Weblog, MailingList)"""

    def isioc_items(self):
        """return contained items"""

   
    
