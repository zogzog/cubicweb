// This contains template-specific javascript

function filterLog(domid, thresholdLevel) {
    var logLevels = ["Debug", "Info", "Warning", "Error", "Fatal"]
    var action = "hide";
    for (var idx = 0; idx < logLevels.length; idx++){
        var level = logLevels[idx];
        if (level === thresholdLevel){
            action = "show";
        }
        $('#'+domid+' .log' + level)[action]();
    }
}
