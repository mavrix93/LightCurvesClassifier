var myPlot = document.getElementById('plot2d')

var x_data = {{ probab_data.0 }};
var y_data = {{ probab_data.1 }};

var data = [{
           x: x_data,
           y: y_data,
           name: "Probability distribution"
        }];
    
var traces = {{ coo_data }};
var zeroes = {{ zeroes }};
var point_labels = {{ point_labels|safe }};
var labels = {{ coo_plot_labels|safe }};
var colors = {{ colors|safe }};
for (i=0; i < traces.length; i++){
    var trace_points = {
      x: traces[i][0],
      y: zeroes[i],
      text: point_labels[i],
      type: "scatter",
      mode: 'markers',
      name: labels[i],
      opacity: 0.9,
      marker: {
         color: colors[i],
         size:10,
      },
    };

    data.push(trace_points);
    }


for (i=0; i < traces.length; i++){


    var trace_hist = {
      x: traces[i][0],
      type: "histogram",
      histnorm: 'probability',
      showlegend: false,
      opacity: 0.7,
      marker: {
         color: colors[i],
      },
    };

    data.push(trace_hist);
    }
        
  
var layout = {
  title: "{{ probab_plot_title }}",
  autosize: true,
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

Plotly.newPlot('plot2d', data, layout);

myPlot.on('plotly_click', function(data){
    var len1 = {{ coo_data.0.0|length }};
    var a = 1;
    if (len1 < 2)
    {
        a = 0;
    }


    plotSelected(data.points[0].pointNumber, data.points[0].curveNumber,len1);
});