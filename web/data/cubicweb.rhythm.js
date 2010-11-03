$(document).ready(function() {
    $('a.rhythm').click(function (event){
        $('div#pageContent').toggleClass('rhythm_bg');
        $('div#page').toggleClass('rhythm_bg');
        event.preventDefault();
    });
});
