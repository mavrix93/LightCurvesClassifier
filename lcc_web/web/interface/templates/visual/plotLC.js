var data = [];
var lcs = {{ lcs }};
var labels = {{ labels|safe }};
for (i=0; i < {{ lcs|length }}; i++){
    var x_data = lcs[i][0];
    var y_data = lcs[i][1];
    
    var this_data = {
               x: x_data,
               y: y_data,
               name: labels[i],
               mode: 'markers',
               error_y: {
                  type: 'data',
                  array: lcs[i][2],
                  visible: true,
                  color: '#85144B'
                            }};
    data.push(this_data);
            
}
  
var layout = {
  title: "Light Curve",
  autosize: true,
    font: {
    size: 25
  },
  width: 800,
  height: 600,
  margin: {
    l: 65,
    r: 50,
    b: 65,
    t: 90,
  },
  xaxis: {
    title: "Time [days]"
    },
  yaxis: {
    title: "Magnitude [mag]",
    autorange: 'reversed'}
};

Plotly.newPlot('plotLC', data, layout);