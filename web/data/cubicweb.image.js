jQuery.fn.autoResize = function() {
    // remove enforced with / height (by CSS and/or HTML attributes)
    this.css("width", "auto").css("height", "auto");
    this.removeAttr("width").removeAttr("height"); // Remove
    // compute image size / max allowed size to fit screen
    var imgHSize = this.width();
    var maxHSize = $(window).width() - ($(document).width() - imgHSize);
    var imgVSize = this.height();
    // we don't mind if content in [content]footer moved out of the screen
    var maxVSize = $(window).height() - ($(document).height() - imgVSize) + $('#footer').height() + $('#contentfooter').height();
    if (maxHSize > 0 && maxVSize > 0) {
        // if image don't fit screen, set width or height so that
        // browser keep img ratio, ensuring the other dimension will
        // also fit the screen
        if (imgHSize > maxHSize && ((imgVSize / imgHSize) * maxHSize) <= maxVSize) {
            this.css("width", maxHSize);
        } else if (imgVSize > maxVSize && ((imgHSize / imgVSize) * maxVSize) <= maxHSize) {
            this.css("height", maxVSize);
        }
        else {
            // image already fit in screen, don't scale it up
        }
    } else {
        // can't fit image in, don't do anything
    }
};


$(document).ready(function() {
        $("img.contentimage").load(function() {$(this).autoResize()});
});
