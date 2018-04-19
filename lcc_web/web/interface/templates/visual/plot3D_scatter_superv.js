function plot3D_scat() {
    var this_plot = document.getElementById('plot3d_scat')
    var opt = document.getElementsByName("plot_axis")[0].value.split(":");
    var i = opt[0]-1;
    var j = opt[1]-1;
    var k = opt[2]-1;
    var coo_data_or = {{ space_coords }};
    var colors = {{ colors|safe }};
    var axis = {{ all_axis|safe }};
    var labels = ["Searched test sample", "Searched train sample", "Contamination test sample", "Contamination train sample"];

    var data = [];
    for (var ind = 0; ind < 4; ind++){
        var xx = coo_data_or[ind][i];
        var yy = coo_data_or[ind][j];
        var zz = coo_data_or[ind][k];

        if (isNaN(k)){

            var trace = {
                x:xx, y: yy,
                mode: 'markers',
                name: labels[ind],
                marker: {
                    size: 12,
                    color: colors[ind],
                    line: {
                    width: 0.5},
                    opacity: 0.8},
                type: 'scatter'
            };

            data.push(trace);
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


            var trace = {
                x:xx, y: yy, z: zz,
                mode: 'markers',
                name: labels[ind],
                text: point_labels[ind],
                marker: {
                    color: colors[ind],
                    size: 12,
                    line: {
                    width: 0.5},
                    opacity: 0.8},
                type: 'scatter3d'
            };

            data.push(trace);

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
    }
    
    
    Plotly.newPlot('plot3d_scat', data, layout);


    this_plot.on('plotly_click', function(data){
    var len1 = coo_data_or[0][0].length;
    var a = 1;
    if (len1 < 2){
        a = 0;
        }
    plotSelected(data.points[0].pointNumber, data.points[0].curveNumber,len1);
    });
    }