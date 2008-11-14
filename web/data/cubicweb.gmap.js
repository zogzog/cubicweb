/*
 *  :organization: Logilab
 *  :copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 *
 *
 */

Widgets.GMapWidget = defclass('GMapWidget', null, {
  __init__: function(wdgnode) {
    // Assume we have imported google maps JS
    if (GBrowserIsCompatible()) {
      var uselabelstr = wdgnode.getAttribute('cubicweb:uselabel');
      var uselabel = true;
      if (uselabelstr){
	if (uselabelstr == 'True'){
	  uselabel = true;
	}
	else{
	  uselabel = false;
	}
      }
      var map = new GMap2(wdgnode);
      map.addControl(new GSmallMapControl());
      var jsonurl = wdgnode.getAttribute('cubicweb:loadurl');
      var self = this; // bind this to a local variable
      jQuery.getJSON(jsonurl, function(geodata) {
	if (geodata.center) {
	  var zoomLevel = 8; // FIXME arbitrary !
	  map.setCenter(new GLatLng(geodata.center.latitude, geodata.center.longitude),
		        zoomLevel);
	}
	for (var i=0; i<geodata.markers.length; i++) {
	  var marker = geodata.markers[i];
	  self.createMarker(map, marker, i+1, uselabel);
	}
      });
      jQuery(wdgnode).after(this.legendBox);
    } else { // incompatible browser
      jQuery.unload(GUnload);
    }
  },

  createMarker: function(map, marker, i, uselabel) {
    var point = new GLatLng(marker.latitude, marker.longitude);
    var icon = new GIcon();
    icon.image = marker.icon[0];
    icon.iconSize = new GSize(marker.icon[1][0], marker.icon[1][1]) ;
    icon.iconAnchor = new GPoint(marker.icon[2][0], marker.icon[2][1]);
    if(marker.icon[3]){
      icon.shadow4 =  marker.icon[3];
    }
    if (typeof LabeledMarker == "undefined") {
	var gmarker = new GMarker(point, {icon: icon,
	title: marker.title});
    } else {
        var gmarker = new LabeledMarker(point, {
          icon: icon,
          title: marker.title,
          labelText: uselabel?'<strong>' + i + '</strong>':'',
          labelOffset: new GSize(2, -32)
        });
    }
    map.addOverlay(gmarker);
    GEvent.addListener(gmarker, 'click', function() {
      jQuery.post(marker.bubbleUrl, function(data) {
	map.openInfoWindowHtml(point, data);
      });
    });
  }

});
