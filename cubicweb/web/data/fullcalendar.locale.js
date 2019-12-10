/*
 translations for fullCalendar plugin
 */

$.fullCalendar.regional = function(lng, options){
    var defaults = {'fr' : {
     monthNames:
       ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'],
     monthNamesShort: ['janv.','févr.','mars','avr.','mai','juin','juil.','août','sept.','oct.','nov.','déc.'],
     dayNames: ['Dimanche','Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi'],
     dayNamesShort: ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'],
     titleFormat: {
 	month: 'MMMM yyyy', // ex : Janvier 2010
 	week: "d[ MMMM][ yyyy]{ - d MMMM yyyy}", // ex : 10 au 16 Janvier 2010,
 	day: 'dddd d MMMM yyyy' // ex : Jeudi 14 Janvier 2010
     },
     columnFormat: {'month': 'dddd',
                  'agendaWeek': 'dddd dd/M/yyyy',
                  'agendaDay': 'dddd dd/M/yyyy'},
     axisFormat: 'H:mm',
     timeFormat: {
	'': 'H:mm',
	agenda: 'H:mm{ - H:mm}'},
     allDayText: 'journée',
     axisFormat: 'H:mm',
     buttonText: {
        today: "aujourd'hui",
        month: 'mois',
        week: 'semaine',
       day: 'jour'
     }
  }};
  if(lng in defaults){
    return $.extend({}, defaults[lng], options);
   }
   else {return options;};
  };
;
