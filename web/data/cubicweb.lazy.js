
function load_now(eltsel, holesel) {
  var lazydiv = jQuery(eltsel);
  var hole = lazydiv.children(holesel);
  if (hole.length == 0) /* the hole is already filled */
    return;
  var vid_eid = lazydiv.attr('cubicweb:lazyloadurl');
  /* XXX see what could be done with jquery.loadxhtml(...)   */
  var later = async_rawremote_exec('lazily', vid_eid);
  later.addCallback(function(req) {
    var div = lazydiv[0];
    div.appendChild(getDomFromResponse(req));
    div.removeChild(hole[0]);
  });
  later.addErrback(function(err) {
    log(err);
  });
}

function trigger_load(divid) {
  jQuery('#lazy-' + divid).trigger('load_' + divid);
}