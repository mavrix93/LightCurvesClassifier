function plotSelected(id, group=0, len=0){
    var lc_data = [];
    var lcs = {{ lcs }};
    var labels = {{ labels|safe }};
    var point_labels = {{ point_labels|safe }};
    
    if (group < 3) {
        var iid = id + (group-1)*len
    }
    else if (group == 3) {
        var iid = id + point_labels[0].length + point_labels[1].length
    }
    else {
        var iid = id + point_labels[0].length + point_labels[1].length + point_labels[2].length
    }
    var x_data = lcs[iid][0];
    var y_data = lcs[iid][1];
    var err_data = lcs[iid][2];
    
    var this_data = {
               x: x_data,
               y: y_data,
               mode: 'markers',
               error_y: {
                  type: 'data',
                  array: err_data,
                  visible: true,
                  color: '#85144B'
                            }};
    lc_data.push(this_data);
                
    
      
    var layout = {
      title: labels[iid],
      autosize: true,
        font: {
    size: 25
  },
      margin: {
        l: 65,
        r: 50,
        b: 65,
        t: 90,
      },
      xaxis: {
        title: "Time"
        },
      yaxis: {
        title: "Mag",
        autorange: 'reversed'}
    };
    
    Plotly.newPlot('lc_plot', lc_data, layout);
    }