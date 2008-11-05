/*
 *  This file contains Calendar utilities
 *  :organization: Logilab
 *  :copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 */

CubicWeb.require('python.js');
CubicWeb.require('ajax.js');

// IMPORTANT NOTE: the variables DAYNAMES AND MONTHNAMES will be added
//                 by cubicweb automatically

// dynamically computed (and cached)
var _CAL_HEADER = null;

TODAY = new Date();


/*
 * Calendar (graphical) widget
 * public methods are :
 *   __init__ :
 *    @param containerId: the DOM node's ID where the calendar will be displayed
 *    @param inputId: which input needs to be updated when a date is selected
 *    @param year, @param month: year and month to be displayed
 *    @param cssclass: CSS class of the calendar widget (default is commandCal)
 *
 *   show() / hide():
 *    show or hide the calendar widget
 *
 *   toggle():
 *    show (resp. hide) the calendar if it's hidden (resp. displayed)
 * 
 *   displayNextMonth(): (resp. displayPreviousMonth())
 *    update the calendar to display next (resp. previous) month
 */
Calendar = function(containerId, inputId, year, month, cssclass) {
    this.containerId = containerId;
    this.inputId = inputId;
    this.year = year;
    this.month = month-1; // Javascript's counter starts at 0 for january
    this.cssclass = cssclass || "popupCalendar";
    this.visible = false;
    this.domtable = null;

    this.cellprops = { 'onclick'     : function() {dateSelected(this, containerId); },
		       'onmouseover' : function() {this.style.fontWeight = 'bold'; },
		       'onmouseout'  : function() {this.style.fontWeight = 'normal';}
		     }

    this.todayprops = jQuery.extend({}, this.cellprops, {'class' : 'today'});

    this._rowdisplay = function(row) {
	return TR(null, map(partial(TD, this.cellprops), row));
    }

    this._makecell = function(cellinfo) {
	return TD(cellinfo[0], cellinfo[1]);
    }

    /* utility function (the only use for now is inside the calendar) */
    this._uppercaseFirst = function(s) { return s.charAt(0).toUpperCase(); }
    
    /* accepts the cells data and builds the corresponding TR nodes
     * @param rows a list of list of couples (daynum, cssprops)
     */
    this._domForRows = function(rows) {
	var lines = []
	for (i=0; i<rows.length; i++) {
	    lines.push(TR(null, map(this._makecell, rows[i])));
	}
	return lines;
    }

    /* builds the calendar headers */
    this._headdisplay = function(row) {
	if (_CAL_HEADER) {
	    return _CAL_HEADER;
	}
	daynames = map(this._uppercaseFirst, DAYNAMES);
	_CAL_HEADER = TR(null, map(partial(TH, null), daynames));
	return _CAL_HEADER;
    }
    
    this._getrows = function() {
	var rows = [];
	var firstday = new Date(this.year, this.month, 1);
	var stopdate = firstday.nextMonth();
	var curdate = firstday.sub(firstday.getRealDay());
	while (curdate.getTime() < stopdate) {
	    var row = []
	    for (var i=0; i<7; i++) {
		if (curdate.getMonth() == this.month) {
		    props = curdate.equals(TODAY) ? this.todayprops:this.cellprops;
		    row.push([props, curdate.getDate()]);
		} else {
		    row.push([this.cellprops, ""]);
		}
		curdate.iadd(1);
	    }
	    rows.push(row);
	}
	return rows;
    }

    this._makecal = function() {
	var rows = this._getrows();
	var monthname = MONTHNAMES[this.month] + " " + this.year;
	var prevlink = "javascript: togglePreviousMonth('" + this.containerId + "');";
	var nextlink = "javascript: toggleNextMonth('" + this.containerId + "');";
	this.domtable = TABLE({'class': this.cssclass},
			      THEAD(null, TR(null,
					     TH(null, A({'href' : prevlink}, "<<")),
					     TH({'colspan' : 5, 'style' : "text-align: center;"}, monthname),
					     TH(null, A({'href' : nextlink}, ">>")))),
			      TBODY(null,
				    this._headdisplay(),
				    this._domForRows(rows))
			     );
	return this.domtable;
    }

    this._updateDiv = function() {
	if (!this.domtable) {
	    this._makecal();
	}
	jqNode(this.containerId).empty().append(this.domtable);
	// replaceChildNodes($(this.containerId), this.domtable);
    }

    this.displayNextMonth = function() {
	this.domtable = null;
	if (this.month == 11) {
	    this.year++;
	}
	this.month = (this.month+1) % 12;
	this._updateDiv();
    }

    this.displayPreviousMonth = function() {
	this.domtable = null;
	if (this.month == 0) {
	    this.year--;
	}
	this.month = (this.month+11) % 12;
	this._updateDiv();
    }
    
    this.show = function() {
	if (!this.visible) {
	    container = jqNode(this.containerId);
	    if (!this.domtable) {
		this._makecal();
	    }
	    container.empty().append(this.domtable);
	    toggleVisibility(container);
	    this.visible = true;
	}
    }

    this.hide = function(event) {
	var self;
	if (event) {
	    self = event.data.self;
	} else {
	    self = this;
	}
	if (self.visible) {
	    toggleVisibility(self.containerId);
	    self.visible = false;
	}
    }

    this.toggle = function() {
	if (this.visible) {
	    this.hide();
	}
	else {
	    this.show();
	}
    }

    // call hide() when the user explicitly sets the focus on the matching input
    jqNode(inputId).bind('focus', {'self': this}, this.hide); // connect(inputId, 'onfocus', this, 'hide');
};

// keep track of each calendar created
Calendar.REGISTRY = {};

/*
 * popup / hide calendar associated to `containerId`
 */	    
function toggleCalendar(containerId, inputId, year, month) {
    var cal = Calendar.REGISTRY[containerId];
    if (!cal) {
	cal = new Calendar(containerId, inputId, year, month);
	Calendar.REGISTRY[containerId] = cal;
    }
    /* hide other calendars */
    for (containerId in Calendar.REGISTRY) {
	var othercal = Calendar.REGISTRY[containerId];
	if (othercal !== cal) {
	    othercal.hide();
	}
    }
    cal.toggle();
}


/*
 * ask for next month to calendar displayed in `containerId`
 */
function toggleNextMonth(containerId) {
    var cal = Calendar.REGISTRY[containerId];
    cal.displayNextMonth();
}

/*
 * ask for previous month to calendar displayed in `containerId`
 */
function togglePreviousMonth(containerId) {
    var cal = Calendar.REGISTRY[containerId];
    cal.displayPreviousMonth();
}


/*
 * Callback called when the user clicked on a cell in the popup calendar
 */
function dateSelected(cell, containerId) {
    var cal = Calendar.REGISTRY[containerId];
    var input = getNode(cal.inputId);
    // XXX: the use of innerHTML might cause problems, but it seems to be
    //      the only way understood by both IE and Mozilla. Otherwise,
    //      IE accepts innerText and mozilla accepts textContent
    var selectedDate = new Date(cal.year, cal.month, cell.innerHTML, 12);
    var xxx = remote_exec("format_date", toISOTimestamp(selectedDate));
    input.value = xxx;
    cal.hide();
}

function whichElement(e)
{
var targ;
if (!e)
  {
  var e=window.event;
  }
if (e.target)
  {
  targ=e.target;
  }
else if (e.srcElement)
  {
  targ=e.srcElement;
  }
if (targ.nodeType==3) // defeat Safari bug
  {
  targ = targ.parentNode;
  }
  return targ;
}

function getPosition(element) {
  var left;
  var top;
  var offset;
  // TODO: deal scrollbar positions also!
  left = element.offsetLeft;
  top = element.offsetTop;

  if (element.offsetParent != null)
    {
      offset = getPosition(element.offsetParent);
      left = left + offset[0];
      top = top + offset[1];
      
    }
  return [left, top];
}

function getMouseInBlock(event) {
  var elt = event.target;
  var x = event.clientX;
  var y = event.clientY;
  var w = elt.clientWidth;
  var h = elt.clientHeight;
  var offset = getPosition(elt);

  x = 1.0*(x-offset[0])/w;
  y = 1.0*(y-offset[1])/h;
  return [x, y];
}
function getHourFromMouse(event, hmin, hmax) {
  var pos = getMouseInBlock(event);
  var y = pos[1];
  return Math.floor((hmax-hmin)*y + hmin);
}

function addCalendarItem(event, hmin, hmax, year, month, day, duration, baseurl) {
  var hour = getHourFromMouse(event, hmin, hmax);

  if (0<=hour && hour < 24) {
    baseurl += "&start="+year+"%2F"+month+"%2F"+day+"%20"+hour+":00";
    baseurl += "&stop="+year+"%2F"+month+"%2F"+day+"%20"+(hour+duration)+":00";
    
    stopPropagation(event);
    window.location.assign(baseurl);
    return false;
  }
  return true;
}

function stopPropagation(event) {
  event.cancelBubble = true;
  if (event.stopPropagation) event.stopPropagation();  
}
     
CubicWeb.provide('calendar.js');
