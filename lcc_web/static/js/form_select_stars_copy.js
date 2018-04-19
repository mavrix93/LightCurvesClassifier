$().ready(function() {  
     $('#add').click(function() {  
        !$('.select1 option:selected').remove().appendTo('.select2'); 
        unpackElements('select2', 'select1', 'descriptors_l'); 
        unpackElements('select2', 'select1', 'connectors_l')
     });  
     $('#remove').click(function() {  
        document.getElementsByClassName("select2")
        !$('.select2 option:selected').remove().appendTo('.select1');  
        unpackElements('select2', 'select1', 'descriptors_l');
        unpackElements('select2', 'select1', 'connectors_l')
     }); 


     $('#add2').click(function() {  
        !$('.select7 option:selected').remove().appendTo('.select8');
        unpackElements('select8', 'select7', 'deciders_l')
     });  
     $('#remove2').click(function() {  
        !$('.select8 option:selected').remove().appendTo('.select7');  
        unpackElements('select8', 'select7', 'deciders_l')
     });  
     
   
     $('#add3').click(function() {  
        !$('.unselect_con option:selected').remove().appendTo('.select_con');
        unpackElements('select_con', 'unselect_con', 'connectors_l')
     });  
     $('#remove3').click(function() {  
        !$('.select_con option:selected').remove().appendTo('.unselect_con');  
        unpackElements('select_con', 'unselect_con', 'connectors_l')
     });  
 });
