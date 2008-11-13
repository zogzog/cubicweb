/*
 *  :organization: Logilab
 *  :copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 *
 */


/* provide our own custom date parser since the default
 * one only understands iso8601 and gregorian dates
 */
Timeline.NativeDateUnit.getParser = function(format) {
    if (typeof format == "string") {
	if (format.indexOf('%') != -1) {
	    return function(datestring) {
		if (datestring) {
		    return strptime(datestring, format);
		}
		return null;
	    };
	}
        format = format.toLowerCase();
    }
    if (format == "iso8601" || format == "iso 8601") {
	return Timeline.DateTime.parseIso8601DateTime;
    }
    return Timeline.DateTime.parseGregorianDateTime;
};

/*** CUBICWEB EVENT PAINTER *****************************************************/
Timeline.CubicWebEventPainter = function(params) {
//  Timeline.OriginalEventPainter.apply(this, arguments);
   this._params = params;
   this._onSelectListeners = [];

   this._filterMatcher = null;
   this._highlightMatcher = null;
   this._frc = null;

   this._eventIdToElmt = {};
};

Timeline.CubicWebEventPainter.prototype = new Timeline.OriginalEventPainter();

Timeline.CubicWebEventPainter.prototype._paintEventLabel = function(
  evt, text, left, top, width, height, theme) {
    var doc = this._timeline.getDocument();

    var labelDiv = doc.createElement("div");
    labelDiv.className = 'timeline-event-label';

    labelDiv.style.left = left + "px";
    labelDiv.style.width = width + "px";
    labelDiv.style.top = top + "px";

    if (evt._obj.onclick) {
	labelDiv.appendChild(A({'href': evt._obj.onclick}, text));
    } else if (evt._obj.image) {
      labelDiv.appendChild(IMG({src: evt._obj.image, width: '30px', height: '30px'}));
    } else {
      labelDiv.innerHTML = text;
    }

    if(evt._title != null)
        labelDiv.title = evt._title;

    var color = evt.getTextColor();
    if (color == null) {
        color = evt.getColor();
    }
    if (color != null) {
        labelDiv.style.color = color;
    }
    var classname = evt.getClassName();
    if(classname) labelDiv.className +=' ' + classname;

    this._eventLayer.appendChild(labelDiv);

    return {
        left:   left,
        top:    top,
        width:  width,
        height: height,
        elmt:   labelDiv
    };
};


Timeline.CubicWebEventPainter.prototype._showBubble = function(x, y, evt) {
  var div = DIV({id: 'xxx'});
  var width = this._params.theme.event.bubble.width;
  if (!evt._obj.bubbleUrl) {
    evt.fillInfoBubble(div, this._params.theme, this._band.getLabeller());
  }
  SimileAjax.WindowManager.cancelPopups();
  SimileAjax.Graphics.createBubbleForContentAndPoint(div, x, y, width);
  if (evt._obj.bubbleUrl) {
    jQuery('#xxx').loadxhtml(evt._obj.bubbleUrl, null, 'post', 'replace');
  }
};
