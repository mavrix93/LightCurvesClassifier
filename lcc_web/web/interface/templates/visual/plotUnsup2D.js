var myPlot = document.getElementById('plot2dUnsup')

var x_data = {{ probab_data.0 }};
var y_data = {{ probab_data.1 }};

var data = [{
           x: x_data,
           y: y_data,
           name: "Probability distribution",
           opacity: 0.6
        }];
        
        
var trace0 = {
  x: {{ coo_data.0 }},
  type: "histogram",
  histnorm: 'probability',
  name: "Histogram",
  opacity: 0.7,
  marker: {
     color: 'green',
  },
};

var trace1 = {
  x: {{ coo_data.0 }},
  y: {{ zeroes }},
  text: {{ coo_plot_labels|safe }},
  type: "scatter",
  mode: 'markers',
  name: "Stars",
  opacity: 0.9,
  marker: {
     color: 'blue',
     size:10,
  },
};

var trace2 = {
  x: [{{ centroids.0.0 }}],
  y: [0],
  type: "line",
  name: "Centroid 1",
  opacity: 0.4,
  mode: 'markers',
  marker: {
     color: 'red',
     size: 20,
  },
};

var trace3 = {
  x: [{{ centroids.0.1 }}],
  y: [0],
  type: "line",
  name: "Centroid 2",
  opacity: 0.4,
  mode: 'markers',
  marker: {
     color: 'red',
     size: 20,
  },
};

data.push(trace1);
data.push(trace0);

data.push(trace2);
data.push(trace3);
        
  
var layout = {
  title: "{{ probab_plot_title }}",
  autosize: false,
  width: 700,
  height: 500,
  margin: {
    l: 65,
    r: 50,
    b: 65,
    t: 90,
  },
  xaxis: {
    title: "{{ probab_plot_axis.0 }}"},
  yaxis: {
    title: "Probability"}
};

Plotly.newPlot('plot2dUnsup', data, layout);

myPlot.on('plotly_click', function(data){
    for (var i = 0; i < data.points.length; i ++){
    
        if (data.points[i].curveNumber == 1){
            plotSelected(data.points[i].pointNumber);
        }
        
        
    }
    
    
    
});