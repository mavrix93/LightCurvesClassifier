
var traces = {{ coo_data }};
var labels = {{ coo_plot_labels|safe }};

var data = [];
for (i=0; i < traces.length; i++){
    var x_data = traces[i][0];
    var y_data = traces[i][1];
    var z_data = traces[i][2];
    var t = {
    x: x_data, y: y_data, z: z_data,
    name: labels[i],
    mode: 'markers',
    marker: {
        size: 8,
        symbol: 'circle',
        line: {
        color: 'rgb(204, 204, 204)',
        width: 1},
        opacity: 0.8},
    type: 'scatter3d'};
    data.push(t);
    }

var layout = {
   title: "{{ coo_plot_title }}",
   scene: {
      xaxis: {
          title: "{{ coo_plot_axis.0 }}"
          },
      yaxis: {
          title: "{{ coo_plot_axis.1 }}"
          },
      zaxis: {
          title: "{{ coo_plot_axis.2 }}"
          }
        },
   margin: {
    l: 0,
    r: 0,
    b: 0,
    t: 0
  }};
Plotly.newPlot('plot3d', data, layout);