# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""Standard interfaces. Deprecated in favor of adapters.

.. note::

  The `implements` selector used to match not only entity classes but also their
  interfaces. This will disappear in a future version. You should define an
  adapter for that interface and use `adaptable('MyIFace')` selector on appobjects
  that require that interface.

"""
__docformat__ = "restructuredtext en"

from logilab.common.interface import Interface


# XXX deprecates in favor of IProgressAdapter
class IProgress(Interface):
    """something that has a cost, a state and a progression"""

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

        - mandatory keys are (''estimated', 'done', 'todo')

        - optional keys are ('notestimated', 'notestimatedcorrected',
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

# XXX deprecates in favor of IMileStoneAdapter
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

# XXX deprecates in favor of IEmbedableAdapter
class IEmbedable(Interface):
    """interface for embedable entities"""

    def embeded_url(self):
        """embed action interface"""

# XXX deprecates in favor of ICalendarViewsAdapter
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

# XXX deprecates in favor of ICalendarableAdapter
class ICalendarable(Interface):
    """interface for items that do have a begin date 'start' and an end date 'stop'
    """

    @property
    def start(self):
        """return start date"""

    @property
    def stop(self):
        """return stop state"""

# XXX deprecates in favor of ICalendarableAdapter
class ITimetableViews(Interface):
    """timetable views interface"""
    def timetable_date(self):
        """XXX explain

        :return: date (`DateTime`)
        """

# XXX deprecates in favor of IGeocodableAdapter
class IGeocodable(Interface):
    """interface required by geocoding views such as gmap-view"""

    @property
    def latitude(self):
        """returns the latitude of the entity"""

    @property
    def longitude(self):
        """returns the longitude of the entity"""

    def marker_icon(self):
        """returns the icon that should be used as the marker"""


# XXX deprecates in favor of IEmailableAdapter
class IFeed(Interface):
    """interface for entities with rss flux"""

    def rss_feed_url(self):
        """"""

# XXX deprecates in favor of IDownloadableAdapter
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

# XXX deprecates in favor of IPrevNextAdapter
class IPrevNext(Interface):
    """interface for entities which can be linked to a previous and/or next
    entity
    """

    def next_entity(self):
        """return the 'next' entity"""
    def previous_entity(self):
        """return the 'previous' entity"""

# XXX deprecates in favor of IBreadCrumbsAdapter
class IBreadCrumbs(Interface):

    def breadcrumbs(self, view, recurs=False):
        pass

# XXX deprecates in favor of ITreeAdapter
class ITree(Interface):

    def parent(self):
        """returns the parent entity"""

    def children(self):
        """returns the item's children"""

    def children_rql(self):
        """XXX returns RQL to get children"""

    def iterchildren(self):
        """iterates over the item's children"""

    def is_leaf(self):
        """returns true if this node as no child"""

    def is_root(self):
        """returns true if this node has no parent"""

    def root(self):
        """returns the root object"""

