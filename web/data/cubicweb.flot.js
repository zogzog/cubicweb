function showTooltip(x, y, contents) {
    $('<div id="tooltip">' + contents + '</div>').css({
        position: 'absolute',
        display: 'none',
        top: y + 5,
        left: x + 5,
        border: '1px solid #fdd',
        padding: '2px',
        'background-color': '#fee',
        opacity: 0.80
    }).appendTo("body").fadeIn(200);
}

var previousPoint = null;
function onPlotHover(event, pos, item) {
    var $fig = $(event.target);
    if (item) {
        if (previousPoint != item.datapoint) {
            previousPoint = item.datapoint;
            $("#tooltip").remove();
            var x = item.datapoint[0].toFixed(2),
                y = item.datapoint[1].toFixed(2);
            if ($fig.data('mode') == 'time') {
                x = new Date(item.datapoint[0]);
                var dateformat = $fig.data('dateformat');
                if (dateformat) {
                    x = x.strftime(dateformat);
                } else {
                    x = x.toLocaleDateString() + ' ' + x.toLocaleTimeString();
                }
            } else if (item.datapoint.length == 4) {
                // NOTE: this has no chance to work with jquery flot >= 0.6 because
                // jquery flot normalizes datapoints and only keeps 2 columns. Either
                // use processRawData hook or use the 'dateformat' option.
                x = new Date(item.datapoint[2]);
                x = x.strftime(item.datapoint[3]);
            }
            showTooltip(item.pageX, item.pageY, item.series.label + ': (' + x + ' ; ' + y + ')');
        }
    } else {
        $("#tooltip").remove();
        previousPoint = null;
    }
}

