from bokeh.layouts import layout, column, row
from bokeh.models import ColumnDataSource
from bokeh.models.layouts import HBox
from bokeh.models.widgets import Select, Paragraph, Button, Tabs, Panel, RangeSlider, PreText, TableColumn, DataTable, NumberFormatter
from bokeh.plotting import figure
from bokeh.io import curdoc
from ROI_Name_Manager import *
from Analysis_Tools import *
import numpy as np
import itertools
from bokeh.palettes import Category20_9 as palette

db_rois = DatabaseROIs()
colors = itertools.cycle(palette)
plot_initialized = False

# Initialize variables
source = ColumnDataSource(data=dict())
source_stat = ColumnDataSource(data=dict())
current_dvh = DVH(dvh_condition="institutional_roi = 'spinal_cord'")
query_row_count = 0
query_row = {}
query_row_type = []

# Get ROI maps
db_rois = DatabaseROIs()

# Categories map of dropdown values, SQL column, and SQL table
selector_categories = {'Institutional ROI': {'var_name': 'institutional_roi', 'table': 'DVHs'},
                       'Physician ROI': {'var_name': 'physician_roi', 'table': 'DVHs'},
                       'ROI Type': {'var_name': 'roi_type', 'table': 'DVHs'},
                       'Beam Energy': {'var_name': 'beam_energy', 'table': 'Beams'},
                       'Beam Type': {'var_name': 'beam_type', 'table': 'Beams'},
                       'Gantry Rotation Direction': {'var_name': 'gantry_rot_dir', 'table': 'Beams'},
                       'Radiation Type': {'var_name': 'radiation_type', 'table': 'Beams'},
                       'Patient Orientation': {'var_name': 'patient_orientation', 'table': 'Plans'},
                       'Patient Sex': {'var_name': 'patient_sex', 'table': 'Plans'},
                       'Physician': {'var_name': 'physician', 'table': 'Plans'},
                       'Tx Modality': {'var_name': 'tx_modality', 'table': 'Plans'},
                       'Tx Site': {'var_name': 'tx_site', 'table': 'Plans'},
                       'Normalization': {'var_name': 'normalization_method', 'table': 'Rxs'}}
slider_categories = {'Age': {'var_name': 'age', 'table': 'Plans'},
                     'Birth Date': {'var_name': 'birth_date', 'table': 'Plans'},
                     'Planned Fractions': {'var_name': 'fxs', 'table': 'Plans'},
                     'Rx Dose': {'var_name': 'rx_dose', 'table': 'Plans'},
                     'Rx Isodose': {'var_name': 'rx_percent', 'table': 'Rxs'},
                     'Simulation Date': {'var_name': 'sim_study_date', 'table': 'Plans'},
                     'Total Plan MU': {'var_name': 'total_mu', 'table': 'Plans'},
                     'Fraction Dose': {'var_name': 'fx_dose', 'table': 'Rxs'},
                     'Beam Dose': {'var_name': 'beam_dose', 'table': 'Beams'},
                     'Beam MU': {'var_name': 'beam_mu', 'table': 'Beams'},
                     'Collimator Angle': {'var_name': 'collimator_angle', 'table': 'Beams'},
                     'Couch Angle': {'var_name': 'couch_angle', 'table': 'Beams'},
                     'Gantry Start Angle': {'var_name': 'gantry_start', 'table': 'Beams'},
                     'Gantry End Angle': {'var_name': 'gantry_end', 'table': 'Beams'},
                     'SSD': {'var_name': 'ssd', 'table': 'Beams'},
                     'ROI Min Dose': {'var_name': 'min_dose', 'table': 'DVHs'},
                     'ROI Mean Dose': {'var_name': 'mean_dose', 'table': 'DVHs'},
                     'ROI Max Dose': {'var_name': 'max_dose', 'table': 'DVHs'},
                     'ROI Volume': {'var_name': 'volume', 'table': 'DVHs'}}


def update():
    initialize_source_data(current_dvh)


def button_add_selector_row():
    global query_row_count, query_row_type
    query_row[query_row_count] = AddSelectorRow(query_row_count)
    layout_query.children.append(query_row[query_row_count].row)
    query_row_count += 1
    query_row_type.append('selector')


def button_add_slider_row():
    global query_row_count
    query_row[query_row_count] = AddSliderRow(query_row_count)
    layout_query.children.append(query_row[query_row_count].row)
    query_row_count += 1
    query_row_type.append('slider')


def button_del_row():
    global query_row_count
    del(layout_query.children[query_row_count])
    query_row_count -= 1
    query_row_type.pop()


def update_query_text():
    global query_row_count, query_row_type, query_row
    plan_query_str = []
    rx_query_str = []
    beam_query_str = []
    dvh_query_str = []
    for i in range(0, query_row_count):
        if query_row_type[i] == 'selector':
            var_name = selector_categories[query_row[i].select_category.value]['var_name']
            table = selector_categories[query_row[i].select_category.value]['table']
            value = query_row[i].select_value.value
            query_str = var_name + " = '" + value + "'"
        elif query_row_type[i] == 'slider':
            var_name = slider_categories[query_row[i].select_category.value]['var_name']
            table = slider_categories[query_row[i].select_category.value]['table']
            value_low = query_row[i].slider.range[0]
            value_high = query_row[i].slider.range[1]
            query_str = var_name + " between " + str(value_low - 0.01) + " and " + str(value_high + 0.01)

        if table == 'Plans':
            plan_query_str.append(query_str)
        elif table == 'Rxs':
            rx_query_str.append(query_str)
        elif table == 'Beams':
            beam_query_str.append(query_str)
        elif table == 'DVHs':
            dvh_query_str.append(query_str)

    plan_query_str = ' and '.join(plan_query_str)
    plan_query.text = 'Plans: ' + plan_query_str
    rx_query_str = ' and '.join(rx_query_str)
    rx_query.text = 'Rxs: ' + rx_query_str
    beam_query_str = ' and '.join(beam_query_str)
    beam_query.text = 'Beams: ' + beam_query_str
    dvh_query_str = ' and '.join(dvh_query_str)
    dvh_query.text = 'DVHs: ' + dvh_query_str

    uids = get_study_instance_uids(Plans=plan_query_str, Rxs=rx_query_str, Beams=beam_query_str)['union']
    dvh_data = DVH(uid=uids, dvh_condition=dvh_query_str)
    initialize_source_data(dvh_data)


class AddSelectorRow:
    def __init__(self, current_row):
        # Plans Tab Widgets
        # Category Dropdown
        self.category_options = selector_categories.keys()
        self.category_options.sort()
        self.select_category = Select(value=self.category_options[0], options=self.category_options)
        self.select_category.on_change('value', self.update_selector_values)

        # Value Dropdown
        self.sql_table = selector_categories[self.select_category.value]['table']
        self.var_name = selector_categories[self.select_category.value]['var_name']
        self.values = DVH_SQL().get_unique_values(self.sql_table, self.var_name)
        self.select_value = Select(value=self.values[0], options=self.values)

        self.add_selector_button = Button(label="Add Selector", button_type="default", width=100)
        self.add_selector_button.on_click(button_add_selector_row)
        self.add_slider_button = Button(label="Add Slider", button_type="primary", width=100)
        self.add_slider_button.on_click(button_add_slider_row)
        self.delete_last_row = Button(label="Delete", button_type="warning", width=100)
        self.delete_last_row.on_click(button_del_row)

        self.row = HBox(self.select_category,
                        self.select_value,
                        self.add_selector_button,
                        self.add_slider_button,
                        self.delete_last_row)

    def update_selector_values(self, attrname, old, new):
        table_new = selector_categories[self.select_category.value]['table']
        var_name_new = selector_categories[new]['var_name']
        new_options = DVH_SQL().get_unique_values(table_new, var_name_new)
        self.select_value.options = new_options
        self.select_value.value = new_options[0]


class AddSliderRow:
    def __init__(self, current_row):
        # Plans Tab Widgets
        # Category Dropdown
        self.category_options = slider_categories.keys()
        self.category_options.sort()
        self.select_category = Select(value=self.category_options[0], options=self.category_options)
        self.select_category.on_change('value', self.update_slider_values)

        # Range slider
        self.sql_table = slider_categories[self.select_category.value]['table']
        self.var_name = slider_categories[self.select_category.value]['var_name']
        self.min_value = DVH_SQL().get_min_value(self.sql_table, self.var_name)
        if not self.min_value:
            self.min_value = 0
        self.max_value = DVH_SQL().get_max_value(self.sql_table, self.var_name)
        if not self.max_value:
            self.max_value = 100
        self.slider = RangeSlider(start=round(self.min_value, 1),
                                  end=round(self.max_value, 1),
                                  range=(self.min_value, self.max_value),
                                  step=0.1)

        self.add_selector_button = Button(label="Add Selector", button_type="default", width=100)
        self.add_selector_button.on_click(button_add_selector_row)
        self.add_slider_button = Button(label="Add Slider", button_type="primary", width=100)
        self.add_slider_button.on_click(button_add_slider_row)
        self.delete_last_row = Button(label="Delete", button_type="warning", width=100)
        self.delete_last_row.on_click(button_del_row)

        self.row = HBox(self.select_category,
                        self.slider,
                        self.add_selector_button,
                        self.add_slider_button,
                        self.delete_last_row)

    def update_slider_values(self, attrname, old, new):
        table_new = slider_categories[new]['table']
        var_name_new = slider_categories[new]['var_name']
        min_value_new = DVH_SQL().get_min_value(table_new, var_name_new)
        if not min_value_new:
            min_value_new = 0
        max_value_new = DVH_SQL().get_max_value(table_new, var_name_new)
        if not max_value_new:
            max_value_new = 100
        print min_value_new, max_value_new
        self.slider.start = min_value_new
        self.slider.end = max_value_new
        self.slider.range = (min_value_new, max_value_new)


def initialize_source_data(current_dvh):
    global plot_initialized
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

    dvh_plots_new = []
    dvh_plots_new = figure(plot_width=1000, plot_height=400)
    dvh_plots_new.multi_line('x', 'y', source=source, color='color', line_width=2)
    dvh_plots_new.patch('x_patch', 'y_patch', source=source_stat, alpha=0.15)
    dvh_plots_new.xaxis.axis_label = "Dose (Gy)"
    dvh_plots_new.yaxis.axis_label = "Normalized Volume"
    layout_data.children[1] = dvh_plots_new


# set up layout
dvh_plots = figure(plot_width=1000, plot_height=400)
dvh_plots.multi_line('x', 'y', source=source, color='color', line_width=2)
dvh_plots.patch('x_patch', 'y_patch', source=source_stat, alpha=0.15)
dvh_plots.xaxis.axis_label = "Dose (Gy)"
dvh_plots.yaxis.axis_label = "Normalized Volume"
update_query_button = Button(label="Update", button_type="success", width=100)
update_query_button.on_click(update_query_text)
plan_query = Paragraph(text="This will contain the final SQL Query", width=1000)
rx_query = Paragraph(text="This will contain the final SQL Query", width=1000)
beam_query = Paragraph(text="This will contain the final SQL Query", width=1000)
dvh_query = Paragraph(text="This will contain the final SQL Query", width=1000)

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
widgets = column(plan_query, rx_query, beam_query, dvh_query, update_query_button)
layout_data = layout([[widgets], [dvh_plots], [data_table]])

main_pre_text = PreText(text="Add selectors and sliders to design your query", width=500)
main_add_selector_button = Button(label="Add Selector", button_type="default", width=200)
main_add_selector_button.on_click(button_add_selector_row)
main_add_slider_button = Button(label="Add Slider", button_type="primary", width=200)
main_add_slider_button.on_click(button_add_slider_row)
layout_query = layout([[main_pre_text, main_add_selector_button, main_add_slider_button]])

tab_query = Panel(child=layout_query, title="Query")
tab_data = Panel(child=layout_data, title="Data")
tabs = Tabs(tabs=[tab_query, tab_data])

curdoc().add_root(tabs)
curdoc().title = "Live Free or DICOM"

update()
