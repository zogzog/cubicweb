
function load_now(eltsel, holesel, reloadable) {
    var lazydiv = jQuery(eltsel);
    var hole = lazydiv.children(holesel);
    if ((hole.length == 0) && !reloadable) {
	/* the hole is already filled */
	return;
    }
    lazydiv.loadxhtml(lazydiv.attr('cubicweb:loadurl'));
}

function trigger_load(divid) {
    jQuery('#lazy-' + divid).trigger('load_' + divid);
}
