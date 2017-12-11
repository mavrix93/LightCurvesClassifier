function plot3D_scat() {
    var opt = document.getElementsByName("plot_axis")[0].value.split(":");
    var i = opt[0]-1;
    var j = opt[1]-1;
    var k = opt[2]-1;
    var coo_data = {{ space_coords }};
    var x = coo_data[i];
    var y = coo_data[j];
    var axis = {{ all_axis|safe }};
        
    if (isNaN(k)){    
        var z = coo_data[k];
            
        var trace = {
            x:x, y: y, 
            mode: 'markers',
            marker: {
                size: 12,
                line: {
                color: 'rgba(217, 217, 217, 0.14)',
                width: 0.5},
                opacity: 0.8},
            type: 'scatter'
        };
        
        var data = [trace];
        var layout = {  
            xaxis: {
                title: axis[i]
                    },
            yaxis: {
                title: axis[j]
                    },
            margin: {
            l: 0,
            r: 0,
            b: 0,
            t: 0
          }};
    
    }
    
    else {      
        var z = coo_data[k];
        
            
        var trace = {
            x:x, y: y, z: z,
            mode: 'markers',
            marker: {
                size: 12,
                line: {
                color: 'rgba(217, 217, 217, 0.14)',
                width: 0.5},
                opacity: 0.8},
            type: 'scatter3d'
        };
        
        var data = [trace];
        var layout = {    
            autosize: true,    
            scene : {
                xaxis: {
                    title: axis[i]
                        },
                yaxis: {
                    title: axis[j]
                        },
                zaxis: {
                    title: axis[k]
                        }},
            margin: {
            l: 0,
            r: 0,
            b: 0,
            t: 0
          }};
        
    }
    
    
    
    Plotly.newPlot('plot3d_scat', data, layout);
    }