var myPlot = document.getElementById('plotUnsup')

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
  legend: {
    x: 1500,
    y: 1000
    },
  overlaying: 'y',
  side: "right",
  title: "{{ probab_plot_title }}",
  xaxis: {
    title: "{{ probab_plot_axis.0 }}"},
  yaxis: {
    title: "{{ probab_plot_axis.1 }}",
    y: -1600},
  autosize: true,
  margin: {
    l: 65,
    r: 50,
    b: 65,
    t: 90,
  }
};

var traces = {{ coo_data }};
var labels = {{ coo_plot_labels|safe }};
var t = {
    x: traces[0], y: traces[1],
    mode: 'markers',
    name: "Sample",
    text: labels,
    marker: {
        size: 8,
        symbol: 'circle',
        line: {
        color: 'rgb(204, 204, 204)',
        width: 1},
        opacity: 0.8},
    type: 'scatter2d'};
data.push(t);


var cent = {{ centroids }};
var tc = {
    x: cent[0], y: cent[1],
    mode: 'markers',
    name: "Clusters center",
    text: ["Centroid1", "Centroid2"],
    marker: {
        size: 18,
        symbol: 'circle',
        line: {
        color: 'rgb(204, 204, 204)',
        width: 1},
        opacity: 0.8},
    type: 'scatter2d'};
data.push(tc);
    

Plotly.newPlot('plotUnsup', data, layout);

myPlot.on('plotly_click', function(data){
    plotSelected(data.points[0].pointNumber);
    
});