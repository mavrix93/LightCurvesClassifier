var x_data = {{ roc_data.0 }};
var y_data = {{ roc_data.1 }};

var data = [{
           x: x_data,
           y: y_data,
        }];
  
var layout = {
  title: "ROC",
  autosize: false,  
  width: 600,
  height: 500,
  margin: {
    l: 65,
    r: 50,
    b: 65,
    t: 90,
  },
  xaxis: {
    title: "False positive rate",
    range: [0,1]},
  yaxis: {
    title: "True positive rate",
    range: [0 , 1]}
};

Plotly.newPlot('plotROC', data, layout);