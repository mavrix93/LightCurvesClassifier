var myPlot = document.getElementById('plot3d_surface')

var x_data = {{ probab_data.0 }};
var y_data = {{ probab_data.1 }};
var z_data = {{ probab_data.2 }};

var data = [{
           x: x_data,
           y: y_data,
           z: z_data,
           type: 'contour'
        }];
  
var layout = {
    showlegend: true,
  legend: {
    x: 1500,
    y: 1000
    },
  title: "Probability plot",
  xaxis: {
    title: "{{ probab_plot_axis.0 }}"},
  yaxis: {
    title: "{{ probab_plot_axis.1 }}",
    y: -1900},
  autosize: true
};

var traces = {{ coo_data }};
var labels = {{ coo_plot_labels|safe }};
var colors = {{ colors|safe }};
var point_labels = {{ point_labels|safe }};
for (i=0; i < traces.length; i++){
    var x_data = traces[i][0];
    var y_data = traces[i][1];
    var t = {
    x: x_data, y: y_data,
    mode: 'markers',
    name: labels[i],
    text: point_labels[i],
    marker: {
        size: 8,
        symbol: 'circle',
        color: colors[i],
        line: {
        color: "#000000",
        width: 1.5},
        opacity: 1},
    type: 'scatter2d'};
    data.push(t);
    }

Plotly.newPlot('plot3d_surface', data, layout);

myPlot.on('plotly_click', function(data){
    var len1 = traces[0][0].length;
    var a = 1;
    if (len1 < 2){
        a = 0;
        }
    plotSelected(data.points[0].pointNumber, data.points[0].curveNumber,len1);  
    });
