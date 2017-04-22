from bokeh.layouts import row, column, widgetbox
from bokeh.models import ColumnDataSource
from bokeh.models.widgets import DataTable, TableColumn, TextInput, Select, NumberFormatter, Button
from bokeh.io import curdoc

from DVH_Viewer import *
from Analysis_Tools import *
import numpy as np
from bokeh.palettes import Category20_9 as palette
import itertools
from bokeh.models import HoverTool, Legend, Range1d, Line

source = ColumnDataSource(data=dict())
source_stat = ColumnDataSource(data=dict())
categories_dict = {"MRN": "mrn",
                   "Institutional ROI": "institutional_roi",
                   "Physician ROI": "physician_roi",
                   "ROI Name": "roi_name",
                   "ROI Type": "roi_type",
                   "Volume": "volume",
                   "Min Dose": "min_dose",
                   "Mean Dose": "mean_dose",
                   "Max Dose": "max_dose"}
current_dvh = DVH(dvh_condition="mrn = '0'")
colors = itertools.cycle(palette)
hover = HoverTool(tooltips=[])
tools = 'pan,box_zoom,box_select,crosshair,reset,wheel_zoom,resize'


def update():
    condition = categories_dict[select_category.value] + ' ' + select_operator.value + " '" + query_text.value + "'"
    current_dvh = DVH(dvh_condition=condition)
    mrn = []
    roi_institutional = []
    roi_physician = []
    roi_name = []
    roi_type = []
    rx_dose = []
    volume = []
    min_dose = []
    mean_dose = []
    max_dose = []
    eud = []
    eud_a_value = []
    x_axis = np.linspace(0, current_dvh.bin_count, current_dvh.bin_count) / float(100)
    x_data = []
    y_data = []

    line_colors = []
    for i, color in itertools.izip(range(0, current_dvh.count), colors):
        line_colors.append(color)

    for i in range(0, current_dvh.count):
        mrn.append(current_dvh.mrn[i])
        roi_institutional.append(current_dvh.roi_institutional[i])
        roi_physician.append(current_dvh.roi_physician[i])
        roi_name.append(current_dvh.roi_name[i])
        roi_type.append(current_dvh.roi_type[i])
        rx_dose.append(current_dvh.rx_dose[i])
        volume.append(np.round(current_dvh.volume[i], decimals=1))
        min_dose.append(current_dvh.min_dose[i])
        mean_dose.append(current_dvh.mean_dose[i])
        max_dose.append(current_dvh.max_dose[i])
        eud.append(np.round(current_dvh.eud[i], decimals=2))
        eud_a_value.append(current_dvh.eud_a_value[i])
        x_data.append(x_axis.tolist())
        y_data.append(current_dvh.dvh[:, i].tolist())

    source.data = {'mrn': mrn,
                   'roi_institutional': roi_institutional,
                   'roi_physician': roi_physician,
                   'roi_name': roi_name,
                   'roi_type': roi_type,
                   'rx_dose': rx_dose,
                   'volume': volume,
                   'min_dose': min_dose,
                   'mean_dose': mean_dose,
                   'max_dose': max_dose,
                   'eud': eud,
                   'eud_a_value': eud_a_value,
                   'x': x_data,
                   'y': y_data,
                   'color': line_colors,
                   'legend': roi_name}
    source_stat.data = {'x_patch': np.append(x_axis, x_axis[::-1]).tolist(),
                        'y_patch': np.append(current_dvh.q3_dvh, current_dvh.q1_dvh[::-1]).tolist()}


# Set up SQL Query widgits
categories = ["MRN",
              "Institutional ROI",
              "Physician ROI",
              "ROI Name",
              "ROI Type",
              "Volume",
              "Min Dose",
              "Mean Dose",
              "Max Dose"]
select_category = Select(title="Category", value="MRN", options=categories)

operators = ["=",
             "<",
             ">",
             "like"]
select_operator = Select(title="Operator", value="=", options=operators)

query_text = TextInput(title="Condition", placeholder="enter condition")

button = Button(label="Update", button_type="success")
button.on_click(update)

# set up plot
dvh_plots = figure(plot_width=700, plot_height=400)
dvh_plots.multi_line('x', 'y', source=source, color='color', line_width=2)
#dvh_plots.patch('x_patch', 'y_patch', source=source_stat, alpha=0.1)

# Set up DataTable
columns = [TableColumn(field="mrn", title="MRN", width=175),
           TableColumn(field="roi_name", title="ROI Name"),
           TableColumn(field="roi_type", title="ROI Type", width=80),
           TableColumn(field="rx_dose", title="Rx Dose", width=100, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="volume", title="Volume", width=80, formatter=NumberFormatter(format="0.0")),
           TableColumn(field="min_dose", title="Min Dose", width=80, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="mean_dose", title="Mean Dose", width=80, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="max_dose", title="Max Dose", width=80, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="eud", title="EUD", width=80, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="eud_a_value", title="a", width=80, formatter=NumberFormatter(format="0.00"))]

data_table = DataTable(source=source, columns=columns, width=1000, selectable=True)

# set up layout
query_row = column(select_category, select_operator, query_text)
widgets = column(query_row, button)
layout = column(widgets, dvh_plots, data_table)

curdoc().add_root(layout)
curdoc().title = "Live Free or DICOM"

update()
