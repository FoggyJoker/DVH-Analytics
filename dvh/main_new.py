#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
main program for Bokeh server
Created on Sun Apr 21 2017
@author: Dan Cutright, PhD
"""


from __future__ import print_function
from future.utils import listitems
from analysis_tools import DVH, get_study_instance_uids, calc_eud
from utilities import Temp_DICOM_FileSet, get_planes_from_string, get_union
import auth
from sql_connector import DVH_SQL
from sql_to_python import QuerySQL
import numpy as np
import itertools
from datetime import datetime
from os.path import dirname, join
from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, Legend, CustomJS, HoverTool, Slider, Spacer
from bokeh.plotting import figure
from bokeh.io import curdoc
from bokeh.palettes import Colorblind8 as palette
from bokeh.models.widgets import Select, Button, Div, TableColumn, DataTable, Panel, Tabs, NumberFormatter,\
    RadioButtonGroup, TextInput, RadioGroup, CheckboxButtonGroup, Dropdown, CheckboxGroup, PasswordInput
from dicompylercore import dicomparser, dvhcalc
from bokeh import events
from scipy.stats import ttest_ind, ranksums, normaltest, pearsonr, linregress
from math import pi
import statsmodels.api as sm
import matplotlib.colors as plot_colors
import time
from options import *

# This depends on a user defined function in dvh/auth.py.  By default, this returns True
# It is up to the user/installer to write their own function (e.g., using python-ldap)
# Proper execution of this requires placing Bokeh behind a reverse proxy with SSL setup (HTTPS)
# Please see Bokeh documentation for more information
ACCESS_GRANTED = not AUTH_USER_REQ

SELECT_CATEGORY1_DEFAULT = 'ROI Institutional Category'
SELECT_CATEGORY_DEFAULT = 'Rx Dose'

# Used to keep Query UI clean
ALLOW_SOURCE_UPDATE = True

# This depends on a user defined function in dvh/auth.py.  By default, this returns True
# It is up to the user/installer to write their own function (e.g., using python-ldap)
# Proper execution of this requires placing Bokeh behind a reverse proxy with SSL setup (HTTPS)
# Please see Bokeh documentation for more information
ACCESS_GRANTED = not AUTH_USER_REQ


# Declare variables
colors = itertools.cycle(palette)
current_dvh, current_dvh_group_1, current_dvh_group_2 = [], [], []
anon_id_map = {}
uids_1, uids_2 = [], []

temp_dvh_info = Temp_DICOM_FileSet()
dvh_review_mrns = temp_dvh_info.mrn
if dvh_review_mrns[0] != '':
    dvh_review_rois = temp_dvh_info.get_roi_names(dvh_review_mrns[0]).values()
    dvh_review_mrns.append('')
else:
    dvh_review_rois = ['']


roi_viewer_data, roi2_viewer_data, roi3_viewer_data, roi4_viewer_data, roi5_viewer_data = {}, {}, {}, {}, {}
tv_data = {}


# Bokeh column data sources
source = ColumnDataSource(data=dict(color=[], x=[], y=[], mrn=[]))
source_selectors = ColumnDataSource(data=dict(row=[1], category1=[''], category2=[''],
                                              group=[''], group_label=[''], not_status=['']))
source_ranges = ColumnDataSource(data=dict(row=[], category=[], min=[], max=[], min_display=[], max_display=[],
                                           group=[], group_label=[], not_status=[]))
source_endpoint_defs = ColumnDataSource(data=dict(row=[], output_type=[], input_type=[], input_value=[],
                                                  label=[], units_in=[], units_out=[]))
source_endpoint_calcs = ColumnDataSource(data=dict())
source_beams = ColumnDataSource(data=dict())
source_plans = ColumnDataSource(data=dict())
source_rxs = ColumnDataSource(data=dict())
source_patch_1 = ColumnDataSource(data=dict(x_patch=[], y_patch=[]))
source_patch_2 = ColumnDataSource(data=dict(x_patch=[], y_patch=[]))
source_stats_1 = ColumnDataSource(data=dict(x=[], min=[], q1=[], mean=[], median=[], q3=[], max=[]))
source_stats_2 = ColumnDataSource(data=dict(x=[], min=[], q1=[], mean=[], median=[], q3=[], max=[]))
source_roi_viewer = ColumnDataSource(data=dict(x=[], y=[]))
source_roi2_viewer = ColumnDataSource(data=dict(x=[], y=[]))
source_roi3_viewer = ColumnDataSource(data=dict(x=[], y=[]))
source_roi4_viewer = ColumnDataSource(data=dict(x=[], y=[]))
source_roi5_viewer = ColumnDataSource(data=dict(x=[], y=[]))
source_tv = ColumnDataSource(data=dict(x=[], y=[]))


# Categories map of dropdown values, SQL column, and SQL table (and data source for range_categories)
selector_categories = {'ROI Institutional Category': {'var_name': 'institutional_roi', 'table': 'DVHs'},
                       'ROI Physician Category': {'var_name': 'physician_roi', 'table': 'DVHs'},
                       'ROI Type': {'var_name': 'roi_type', 'table': 'DVHs'},
                       'Beam Type': {'var_name': 'beam_type', 'table': 'Beams'},
                       'Dose Grid Resolution': {'var_name': 'dose_grid_res', 'table': 'Plans'},
                       'Gantry Rotation Direction': {'var_name': 'gantry_rot_dir', 'table': 'Beams'},
                       'Radiation Type': {'var_name': 'radiation_type', 'table': 'Beams'},
                       'Patient Orientation': {'var_name': 'patient_orientation', 'table': 'Plans'},
                       'Patient Sex': {'var_name': 'patient_sex', 'table': 'Plans'},
                       'Physician': {'var_name': 'physician', 'table': 'Plans'},
                       'Tx Modality': {'var_name': 'tx_modality', 'table': 'Plans'},
                       'Tx Site': {'var_name': 'tx_site', 'table': 'Plans'},
                       'Normalization': {'var_name': 'normalization_method', 'table': 'Rxs'},
                       'Treatment Machine': {'var_name': 'treatment_machine', 'table': 'Beams'},
                       'Heterogeneity Correction': {'var_name': 'heterogeneity_correction', 'table': 'Plans'},
                       'Scan Mode': {'var_name': 'scan_mode', 'table': 'Beams'},
                       'MRN': {'var_name': 'mrn', 'table': 'Plans'},
                       'UID': {'var_name': 'study_instance_uid', 'table': 'Plans'},
                       'Baseline': {'var_name': 'baseline', 'table': 'Plans'}}
range_categories = {'Age': {'var_name': 'age', 'table': 'Plans', 'units': '', 'source': source_plans},
                    'Beam Energy Min': {'var_name': 'beam_energy_min', 'table': 'Beams', 'units': '', 'source': source_beams},
                    'Beam Energy Max': {'var_name': 'beam_energy_max', 'table': 'Beams', 'units': '', 'source': source_beams},
                    'Birth Date': {'var_name': 'birth_date', 'table': 'Plans', 'units': '', 'source': source_plans},
                    'Planned Fractions': {'var_name': 'fxs', 'table': 'Plans', 'units': '', 'source': source_plans},
                    'Rx Dose': {'var_name': 'rx_dose', 'table': 'Plans', 'units': 'Gy', 'source': source_plans},
                    'Rx Isodose': {'var_name': 'rx_percent', 'table': 'Rxs', 'units': '%', 'source': source_rxs},
                    'Simulation Date': {'var_name': 'sim_study_date', 'table': 'Plans', 'units': '', 'source': source_plans},
                    'Total Plan MU': {'var_name': 'total_mu', 'table': 'Plans', 'units': 'MU', 'source': source_plans},
                    'Fraction Dose': {'var_name': 'fx_dose', 'table': 'Rxs', 'units': 'Gy', 'source': source_rxs},
                    'Beam Dose': {'var_name': 'beam_dose', 'table': 'Beams', 'units': 'Gy', 'source': source_beams},
                    'Beam MU': {'var_name': 'beam_mu', 'table': 'Beams', 'units': '', 'source': source_beams},
                    'Control Point Count': {'var_name': 'control_point_count', 'table': 'Beams', 'units': '', 'source': source_beams},
                    'Collimator Start Angle': {'var_name': 'collimator_start', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Collimator End Angle': {'var_name': 'collimator_end', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Collimator Min Angle': {'var_name': 'collimator_min', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Collimator Max Angle': {'var_name': 'collimator_max', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Collimator Range': {'var_name': 'collimator_range', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Couch Start Angle': {'var_name': 'couch_start', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Couch End Angle': {'var_name': 'couch_end', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Couch Min Angle': {'var_name': 'couch_min', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Couch Max Angle': {'var_name': 'couch_max', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Couch Range': {'var_name': 'couch_range', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Gantry Start Angle': {'var_name': 'gantry_start', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Gantry End Angle': {'var_name': 'gantry_end', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Gantry Min Angle': {'var_name': 'gantry_min', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Gantry Max Angle': {'var_name': 'gantry_max', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'Gantry Range': {'var_name': 'gantry_range', 'table': 'Beams', 'units': 'deg', 'source': source_beams},
                    'SSD': {'var_name': 'ssd', 'table': 'Beams', 'units': 'cm', 'source': source_beams},
                    'ROI Min Dose': {'var_name': 'min_dose', 'table': 'DVHs', 'units': 'Gy', 'source': source},
                    'ROI Mean Dose': {'var_name': 'mean_dose', 'table': 'DVHs', 'units': 'Gy', 'source': source},
                    'ROI Max Dose': {'var_name': 'max_dose', 'table': 'DVHs', 'units': 'Gy', 'source': source},
                    'ROI Volume': {'var_name': 'volume', 'table': 'DVHs', 'units': 'cc', 'source': source},
                    'PTV Distance (Min)': {'var_name': 'dist_to_ptv_min', 'table': 'DVHs', 'units': 'cm', 'source': source},
                    'PTV Distance (Mean)': {'var_name': 'dist_to_ptv_mean', 'table': 'DVHs', 'units': 'cm', 'source': source},
                    'PTV Distance (Median)': {'var_name': 'dist_to_ptv_median', 'table': 'DVHs', 'units': 'cm', 'source': source},
                    'PTV Distance (Max)': {'var_name': 'dist_to_ptv_max', 'table': 'DVHs', 'units': 'cm', 'source': source},
                    'PTV Overlap': {'var_name': 'ptv_overlap', 'table': 'DVHs', 'units': 'cc', 'source': source},
                    'Scan Spots': {'var_name': 'scan_spot_count', 'table': 'Beams', 'units': '', 'source': source_beams},
                    'Beam MU per deg': {'var_name': 'beam_mu_per_deg', 'table': 'Beams', 'units': '', 'source': source_beams},
                    'Beam MU per control point': {'var_name': 'beam_mu_per_cp', 'table': 'Beams', 'units': '', 'source': source_beams}}


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Functions for Querying by categorical data
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def update_select_category2_values():
    new = select_category1.value
    table_new = selector_categories[new]['table']
    var_name_new = selector_categories[new]['var_name']
    new_options = DVH_SQL().get_unique_values(table_new, var_name_new)
    select_category2.options = new_options
    select_category2.value = new_options[0]


def ensure_selector_group_is_assigned(attr, old, new):
    if not group_selector.active:
        group_selector.active = [-old[0] + 1]
    update_selector_source()


def update_selector_source():
    if selector_row.value:
        r = int(selector_row.value) - 1
        group = sum([i+1 for i in group_selector.active])
        group_labels = ['1', '2', '1 & 2']
        group_label = group_labels[group-1]
        not_status = ['', 'Not'][len(selector_not_operator_checkbox.active)]

        patch = {'category1': [(r, select_category1.value)], 'category2': [(r, select_category2.value)],
                 'group': [(r, group)], 'group_label': [(r, group_label)], 'not_status': [(r, not_status)]}
        source_selectors.patch(patch)


def add_selector_row():
    if source_selectors.data['row']:
        temp = source_selectors.data

        for key in list(temp):
            temp[key].append('')
        temp['row'][-1] = len(temp['row'])

        source_selectors.data = temp
        new_options = [str(x+1) for x in range(0, len(temp['row']))]
        selector_row.options = new_options
        selector_row.value = new_options[-1]
        select_category1.value = SELECT_CATEGORY1_DEFAULT
        select_category2.value = select_category2.options[0]
        selector_not_operator_checkbox.active = []
    else:
        selector_row.options = ['1']
        selector_row.value = '1'
        source_selectors.data = dict(row=[1], category1=[''], category2=[''],
                                     group=[''], group_label=[''], not_status=[''])
    update_selector_source()

    clear_source_selection(source_selectors)


def select_category1_ticker(attr, old, new):
    update_select_category2_values()
    update_selector_source()


def select_category2_ticker(attr, old, new):
    update_selector_source()


def selector_not_operator_ticker(attr, old, new):
    update_selector_source()


def selector_row_ticker(attr, old, new):
    if source_selectors.data['category1'] and source_selectors.data['category1'][-1]:
        r = int(selector_row.value) - 1
        category1 = source_selectors.data['category1'][r]
        category2 = source_selectors.data['category2'][r]
        group = source_selectors.data['group'][r]
        not_status = source_selectors.data['not_status'][r]

        select_category1.value = category1
        select_category2.value = category2
        group_selector.active = [[0], [1], [0, 1]][group-1]
        if not_status:
            selector_not_operator_checkbox.active = [0]
        else:
            selector_not_operator_checkbox.active = []


def update_selector_row_on_selection(attr, old, new):
    if new['1d']['indices']:
        selector_row.value = selector_row.options[min(new['1d']['indices'])]


def delete_selector_row():
    if selector_row.value:
        new_selectors_source = source_selectors.data
        index_to_delete = int(selector_row.value) - 1
        new_source_length = len(source_selectors.data['category1']) - 1

        if new_source_length == 0:
            source_selectors.data = dict(row=[], category1=[], category2=[], group=[], group_label=[], not_status=[])
            selector_row.options = ['']
            selector_row.value = ''
            group_selector.active = [0]
            selector_not_operator_checkbox.active = []
            select_category1.value = SELECT_CATEGORY1_DEFAULT
            select_category2.value = select_category2.options[0]
        else:
            for key in list(new_selectors_source):
                new_selectors_source[key].pop(index_to_delete)

            for i in range(index_to_delete, new_source_length):
                new_selectors_source['row'][i] -= 1

            selector_row.options = [str(x+1) for x in range(0, new_source_length)]
            if selector_row.value not in selector_row.options:
                selector_row.value = selector_row.options[-1]
            source_selectors.data = new_selectors_source

        clear_source_selection(source_selectors)


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Functions for Querying by numerical data
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
def add_range_row():
    if source_ranges.data['row']:
        temp = source_ranges.data

        for key in list(temp):
            temp[key].append('')
        temp['row'][-1] = len(temp['row'])
        source_ranges.data = temp
        new_options = [str(x+1) for x in range(0, len(temp['row']))]
        range_row.options = new_options
        range_row.value = new_options[-1]
        select_category.value = SELECT_CATEGORY_DEFAULT
        group_range.active = [0]
        range_not_operator_checkbox.active = []
    else:
        range_row.options = ['1']
        range_row.value = '1'
        source_ranges.data = dict(row=['1'], category=[''], min=[''], max=[''], min_display=[''], max_display=[''],
                                  group=[''], group_label=[''], not_status=[''])

    update_range_titles(reset_values=True)
    update_range_source()

    clear_source_selection(source_ranges)


def update_range_source():
    if range_row.value:
        table = range_categories[select_category.value]['table']
        var_name = range_categories[select_category.value]['var_name']

        r = int(range_row.value) - 1
        group = sum([i+1 for i in group_range.active])
        group_labels = ['1', '2', '1 & 2']
        group_label = group_labels[group-1]
        not_status = ['', 'Not'][len(range_not_operator_checkbox.active)]

        try:
            min_float = float(text_min.value)
        except ValueError:
            try:
                min_float = float(DVH_SQL().get_min_value(table, var_name))
            except TypeError:
                min_float = ''

        try:
            max_float = float(text_max.value)
        except ValueError:
            try:
                max_float = float(DVH_SQL().get_max_value(table, var_name))
            except TypeError:
                max_float = ''

        if min_float or min_float == 0.:
            min_display = "%s %s" % (str(min_float), range_categories[select_category.value]['units'])
        else:
            min_display = 'None'

        if max_float or max_float == 0.:
            max_display = "%s %s" % (str(max_float), range_categories[select_category.value]['units'])
        else:
            max_display = 'None'

        patch = {'category': [(r, select_category.value)], 'min': [(r, min_float)], 'max': [(r, max_float)],
                 'min_display': [(r, min_display)], 'max_display': [(r, max_display)],
                 'group': [(r, group)], 'group_label': [(r, group_label)], 'not_status': [(r, not_status)]}
        source_ranges.patch(patch)

        group_range.active = [[0], [1], [0, 1]][group - 1]
        text_min.value = str(min_float)
        text_max.value = str(max_float)


def update_range_titles(**kwargs):
    table = range_categories[select_category.value]['table']
    var_name = range_categories[select_category.value]['var_name']
    min_value = DVH_SQL().get_min_value(table, var_name)
    text_min.title = 'Min: ' + str(min_value) + ' ' + range_categories[select_category.value]['units']
    max_value = DVH_SQL().get_max_value(table, var_name)
    text_max.title = 'Max: ' + str(max_value) + ' ' + range_categories[select_category.value]['units']

    if kwargs and 'reset_values' in kwargs and kwargs['reset_values']:
        text_min.value = str(min_value)
        text_max.value = str(max_value)


def range_row_ticker(attr, old, new):
    global ALLOW_SOURCE_UPDATE
    if source_ranges.data['category'] and source_ranges.data['category'][-1]:
        r = int(new) - 1
        category = source_ranges.data['category'][r]
        min_new = source_ranges.data['min'][r]
        max_new = source_ranges.data['max'][r]
        group = source_ranges.data['group'][r]
        not_status = source_ranges.data['not_status'][r]

        ALLOW_SOURCE_UPDATE = False
        select_category.value = category
        text_min.value = str(min_new)
        text_max.value = str(max_new)
        update_range_titles()
        group_range.active = [[0], [1], [0, 1]][group - 1]
        ALLOW_SOURCE_UPDATE = True
        if not_status:
            range_not_operator_checkbox.active = [0]
        else:
            range_not_operator_checkbox.active = []


def select_category_ticker(attr, old, new):
    if ALLOW_SOURCE_UPDATE:
        update_range_titles(reset_values=True)
        update_range_source()


def min_text_ticker(attr, old, new):
    if ALLOW_SOURCE_UPDATE:
        update_range_source()


def max_text_ticker(attr, old, new):
    if ALLOW_SOURCE_UPDATE:
        update_range_source()


def range_not_operator_ticker(attr, old, new):
    if ALLOW_SOURCE_UPDATE:
        update_range_source()


def delete_range_row():
    if range_row.value:
        new_range_source = source_ranges.data
        index_to_delete = int(range_row.value) - 1
        new_source_length = len(source_ranges.data['category']) - 1

        if new_source_length == 0:
            source_ranges.data = dict(row=[], category=[], min=[], max=[], min_display=[], max_display=[],
                                      group=[], group_label=[], not_status=[])
            range_row.options = ['']
            range_row.value = ''
            group_range.active = [0]
            range_not_operator_checkbox.active = []
            select_category.value = SELECT_CATEGORY_DEFAULT
            text_min.value = ''
            text_max.value = ''
        else:
            for key in list(new_range_source):
                new_range_source[key].pop(index_to_delete)

            for i in range(index_to_delete, new_source_length):
                new_range_source['row'][i] -= 1

            range_row.options = [str(x+1) for x in range(0, new_source_length)]
            if range_row.value not in range_row.options:
                range_row.value = range_row.options[-1]
            source_ranges.data = new_range_source

        clear_source_selection(source_ranges)


def ensure_range_group_is_assigned(attrname, old, new):
    if not group_range.active:
        group_range.active = [-old[0] + 1]
    update_range_source()


def update_range_row_on_selection(attr, old, new):
    if new['1d']['indices']:
        range_row.value = range_row.options[min(new['1d']['indices'])]


def clear_source_selection(src):
    src.selected = {'0d': {'glyph': None, 'indices': []},
                    '1d': {'indices': []},
                    '2d': {'indices': {}}}


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Functions for adding DVH endpoints
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def add_endpoint():
    if source_endpoint_defs.data['row']:
        temp = source_endpoint_defs.data

        for key in list(temp):
            temp[key].append('')
        temp['row'][-1] = len(temp['row'])
        source_endpoint_defs.data = temp
        new_options = [str(x+1) for x in range(0, len(temp['row']))]
        ep_row.options = new_options
        ep_row.value = new_options[-1]
    else:
        ep_row.options = ['1']
        ep_row.value = '1'
        source_endpoint_defs.data = dict(row=['1'], output_type=[''], input_type=[''], input_value=[''],
                                         label=[''], units_in=[''], units_out=[''])
        if not ep_text_input.value:
            ep_text_input.value = '1'

    update_ep_source()

    clear_source_selection(source_endpoint_defs)


def update_ep_source():
    if ep_row.value:

        r = int(ep_row.value) - 1

        if 'Dose' in select_ep_type.value:
            input_type, output_type = 'Dose', 'Volume'
            if '%' in select_ep_type.value:
                units_out = '%'
            else:
                units_out = 'Gy'
            units_in = ['cc', '%'][ep_units_in.active]
            label = "D_%s%s" % (ep_text_input.value, units_in)
        else:
            input_type, output_type = 'Volume', 'Dose'
            if '%' in select_ep_type.value:
                units_out = '%'
            else:
                units_out = 'cc'
            units_in = ['Gy', '%'][ep_units_in.active]
            label = "V_%s%s" % (ep_text_input.value, units_in)

        try:
            input_value = float(ep_text_input.value)
        except:
            input_value = 1

        patch = {'output_type': [(r, output_type)], 'input_type': [(r, input_type)],
                 'input_value': [(r, input_value)], 'label': [(r, label)],
                 'units_in': [(r, units_in)], 'units_out': [(r, units_out)]}
        source_endpoint_defs.patch(patch)


def ep_units_in_ticker(attr, old, new):
    if ALLOW_SOURCE_UPDATE:
        update_ep_text_input_title()
        update_ep_source()
        if current_dvh:
            update_source_endpoint_calcs()


def update_ep_text_input_title():
    if 'Dose' in select_ep_type.value:
        ep_text_input.title = "Input Volume (%s):" % ['cc', '%'][ep_units_in.active]
    else:
        ep_text_input.title = "Input Dose (%s):" % ['cc', 'Gy'][ep_units_in.active]


def select_ep_type_ticker(attr, old, new):
    if ALLOW_SOURCE_UPDATE:
        if 'Dose' in new:
            ep_units_in.labels = ['cc', '%']
        else:
            ep_units_in.labels = ['Gy', '%']

        update_ep_text_input_title()
        update_ep_source()
        if current_dvh:
            update_source_endpoint_calcs()


def ep_text_input_ticker(attr, old, new):
    if ALLOW_SOURCE_UPDATE:
        update_ep_source()
        if current_dvh:
            update_source_endpoint_calcs()


def delete_ep_row():
    if ep_row.value:
        new_ep_source = source_endpoint_defs.data
        index_to_delete = int(ep_row.value) - 1
        new_source_length = len(source_endpoint_defs.data['output_type']) - 1

        if new_source_length == 0:
            source_endpoint_defs.data = dict(row=[], output_type=[], input_type=[], input_value=[],
                                             label=[], units_in=[], units_out=[])
            ep_row.options = ['']
            ep_row.value = ''
        else:
            for key in list(new_ep_source):
                new_ep_source[key].pop(index_to_delete)

            for i in range(index_to_delete, new_source_length):
                new_ep_source['row'][i] -= 1

            ep_row.options = [str(x+1) for x in range(0, new_source_length)]
            if ep_row.value not in ep_row.options:
                ep_row.value = ep_row.options[-1]
            source_endpoint_defs.data = new_ep_source

        clear_source_selection(source_endpoint_defs)


def update_ep_row_on_selection(attr, old, new):
    global ALLOW_SOURCE_UPDATE
    ALLOW_SOURCE_UPDATE = False

    if new['1d']['indices']:
        data = source_endpoint_defs.data
        r = min(new['1d']['indices'])

        # update row
        ep_row.value = ep_row.options[r]

        # update input value
        ep_text_input.value = str(data['input_value'][r])

        # update input units radio button
        if '%' in data['units_in'][r]:
            ep_units_in.active = 1
        else:
            ep_units_in.active = 0

        # update output
        if 'Volume' in data['output_type'][r]:
            if '%' in data['units_in'][r]:
                select_ep_type.value = ep_options[1]
            else:
                select_ep_type.value = ep_options[0]
        else:
            if '%' in data['units_in'][r]:
                select_ep_type.value = ep_options[3]
            else:
                select_ep_type.value = ep_options[2]

    ALLOW_SOURCE_UPDATE = True


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Query functions
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!

# This function retuns the list of information needed to execute QuerySQL from
# SQL_to_Python.py (i.e., uids and dvh_condition)
# This function can be used for one group at a time, or both groups. Using both groups is useful so that duplicate
# DVHs do not show up in the plot (i.e., if a DVH satisfies both group criteria)
def get_query(**kwargs):

    if kwargs and 'group' in kwargs:
        if kwargs['group'] == 1:
            active_groups = [1]
        elif kwargs['group'] == 2:
            active_groups = [2]
    else:
        active_groups = [1, 2]

    # Used to accumulate lists of query strings for each table
    # Will assume each item in list is complete query for that SQL column
    queries = {'Plans': [], 'Rxs': [], 'Beams': [], 'DVHs': []}

    # Used to group queries by variable, will combine all queries of same variable with an OR operator
    # e.g., queries_by_sql_column['Plans'][key] = list of strings, where key is sql column
    queries_by_sql_column = {'Plans': {}, 'Rxs': {}, 'Beams': {}, 'DVHs': {}}

    for active_group in active_groups:

        # Accumulate categorical query strings
        data = source_selectors.data
        for r in data['row']:
            r = int(r)
            if active_group == data['group'][r-1]:
                var_name = selector_categories[data['category1'][r-1]]['var_name']
                table = selector_categories[data['category1'][r-1]]['table']
                value = data['category2'][r-1]
                if data['not_status'][r-1]:
                    operator = "!="
                else:
                    operator = "="

                query_str = "%s %s '%s'" % (var_name, operator, value)

                # Append query_str in query_by_sql_column
                if var_name not in queries_by_sql_column[table].keys():
                    queries_by_sql_column[table][var_name] = []
                queries_by_sql_column[table][var_name].append(query_str)

        # Accumulate numerical query strings
        data = source_ranges.data
        for r in data['row']:
            r = int(r)
            if active_group in data['group']:
                var_name = range_categories[data['category'][r-1]]['var_name']
                table = range_categories[data['category'][r-1]]['table']

                value_low = float(data['min'][r-1])
                value_high = float(data['max'][r-1])

                # Modify value_low and value_high so SQL interprets values as dates, if applicable
                if var_name in {'sim_study_date', 'birth_date'}:
                    value_low = "'%s'::date" % value_low
                    value_high = "'%s'::date" % value_high

                if data['not_status'][r - 1]:
                    query_str = var_name + " NOT BETWEEN " + str(value_low) + " AND " + str(value_high)
                else:
                    query_str = var_name + " BETWEEN " + str(value_low) + " AND " + str(value_high)

                # Append query_str in query_by_sql_column
                if var_name not in queries_by_sql_column[table]:
                    queries_by_sql_column[table][var_name] = []
                queries_by_sql_column[table][var_name].append(query_str)

        for table in queries:
            temp_str = []
            for v in queries_by_sql_column[table].keys():

                # collect all contraints for a given sql column into one list
                q_by_sql_col = [q for q in queries_by_sql_column[table][v]]

                # combine all contraints for a given sql column with 'or' operators
                temp_str.append("(%s)" % ' OR '.join(q_by_sql_col))

            queries[table] = ' AND '.join(temp_str)
            print(str(datetime.now()), '%s = %s' % (table, queries[table]), sep=' ')

    # Get a list of UIDs that fit the plan, rx, and beam query criteria.  DVH query criteria will not alter the
    # list of UIDs, therefore dvh_query is not needed to get the UID list
    print(str(datetime.now()), 'getting uids', sep=' ')
    uids = get_study_instance_uids(Plans=queries['Plans'], Rxs=queries['Rxs'], Beams=queries['Beams'])['union']

    # uids: a unique list of all uids that satisfy the criteria
    # queries['DVHs']: the dvh query string for SQL
    return uids, queries['DVHs']


# main update function
def update_data():
    global current_dvh, current_dvh_group_1, current_dvh_group_2
    old_update_button_label = query_button.label
    old_update_button_type = query_button.button_type
    query_button.label = 'Updating...'
    query_button.button_type = 'warning'
    uids, dvh_query_str = get_query()
    print(str(datetime.now()), 'getting dvh data', sep=' ')
    current_dvh = DVH(uid=uids, dvh_condition=dvh_query_str)
    print(str(datetime.now()), 'initializing source data ', current_dvh.query, sep=' ')
    current_dvh_group_1, current_dvh_group_2 = update_dvh_data(current_dvh)
    update_source_endpoint_calcs()
    # calculate_review_dvh()
    # update_all_range_endpoints()
    # update_endpoint_data(current_dvh, current_dvh_group_1, current_dvh_group_2)
    # initialize_rad_bio_source()
    query_button.label = old_update_button_label
    query_button.button_type = old_update_button_type
    # control_chart_y.value = ''
    update_roi_viewer_mrn()
    # print(str(datetime.now()), 'updating correlation data')
    # update_correlation()
    # print(str(datetime.now()), 'correlation data updated')


# input is a DVH class from Analysis_Tools.py
# This function creates a new ColumnSourceData and calls
# the functions to update beam, rx, and plans ColumnSourceData variables
def update_dvh_data(dvh):
    global uids_1, uids_2, anon_id_map

    dvh_group_1, dvh_group_2 = [], []
    group_1_count, group_2_count = group_count()
    if group_1_count > 0 and group_2_count > 0:
        extra_rows = 12
    elif group_1_count > 0 or group_2_count > 0:
        extra_rows = 6
    else:
        extra_rows = 0

    print(str(datetime.now()), 'updating dvh data', sep=' ')
    line_colors = [color for j, color in itertools.izip(range(0, dvh.count + extra_rows), colors)]

    x_axis = np.round(np.add(np.linspace(0, dvh.bin_count, dvh.bin_count) / 100., 0.005), 3)

    print(str(datetime.now()), 'beginning stat calcs', sep=' ')

    if radio_group_dose.active == 1:
        stat_dose_scale = 'relative'
        x_axis_stat = dvh.get_stat_dvh(type=False, dose=stat_dose_scale)
    else:
        stat_dose_scale = 'absolute'
        x_axis_stat = x_axis
    if radio_group_volume.active == 0:
        stat_volume_scale = 'absolute'
    else:
        stat_volume_scale = 'relative'

    print(str(datetime.now()), 'calculating patches', sep=' ')

    # stat_dvhs = dvh.get_standard_stat_dvh(dose=stat_dose_scale, volume=stat_volume_scale)

    if group_1_count == 0:
        uids_1 = []
        source_patch_1.data = {'x_patch': [],
                               'y_patch': []}
        source_stats_1.data = {'x': [],
                               'min': [],
                               'q1': [],
                               'mean': [],
                               'median': [],
                               'q3': [],
                               'max': []}
    else:
        uids_1, dvh_query_str = get_query(group=1)
        dvh_group_1 = DVH(uid=uids_1, dvh_condition=dvh_query_str)
        uids_1 = dvh_group_1.study_instance_uid
        stat_dvhs_1 = dvh_group_1.get_standard_stat_dvh(dose=stat_dose_scale, volume=stat_volume_scale)

        if radio_group_dose.active == 1:
            x_axis_1 = dvh_group_1.get_stat_dvh(type=False, dose=stat_dose_scale)
        else:
            x_axis_1 = np.add(np.linspace(0, dvh_group_1.bin_count, dvh_group_1.bin_count) / 100., 0.005)

        source_patch_1.data = {'x_patch': np.append(x_axis_1, x_axis_1[::-1]).tolist(),
                               'y_patch': np.append(stat_dvhs_1['q3'], stat_dvhs_1['q1'][::-1]).tolist()}
        source_stats_1.data = {'x': x_axis_1.tolist(),
                               'min': stat_dvhs_1['min'].tolist(),
                               'q1': stat_dvhs_1['q1'].tolist(),
                               'mean': stat_dvhs_1['mean'].tolist(),
                               'median': stat_dvhs_1['median'].tolist(),
                               'q3': stat_dvhs_1['q3'].tolist(),
                               'max': stat_dvhs_1['max'].tolist()}
    if group_2_count == 0:
        uids_2 = []
        source_patch_2.data = {'x_patch': [],
                               'y_patch': []}
        source_stats_2.data = {'x': [],
                               'min': [],
                               'q1': [],
                               'mean': [],
                               'median': [],
                               'q3': [],
                               'max': []}
    else:
        uids_2, dvh_query_str = get_query(group=2)
        dvh_group_2 = DVH(uid=uids_2, dvh_condition=dvh_query_str)
        uids_2 = dvh_group_2.study_instance_uid
        stat_dvhs_2 = dvh_group_2.get_standard_stat_dvh(dose=stat_dose_scale, volume=stat_volume_scale)

        if radio_group_dose.active == 1:
            x_axis_2 = dvh_group_2.get_stat_dvh(type=False, dose=stat_dose_scale)
        else:
            x_axis_2 = np.add(np.linspace(0, dvh_group_2.bin_count, dvh_group_2.bin_count) / 100., 0.005)

        source_patch_2.data = {'x_patch': np.append(x_axis_2, x_axis_2[::-1]).tolist(),
                               'y_patch': np.append(stat_dvhs_2['q3'], stat_dvhs_2['q1'][::-1]).tolist()}
        source_stats_2.data = {'x': x_axis_2.tolist(),
                               'min': stat_dvhs_2['min'].tolist(),
                               'q1': stat_dvhs_2['q1'].tolist(),
                               'mean': stat_dvhs_2['mean'].tolist(),
                               'median': stat_dvhs_2['median'].tolist(),
                               'q3': stat_dvhs_2['q3'].tolist(),
                               'max': stat_dvhs_2['max'].tolist()}

    print(str(datetime.now()), 'patches calculated', sep=' ')

    if radio_group_dose.active == 0:
        x_scale = ['Gy'] * (dvh.count + extra_rows + 1)
        dvh_plots.xaxis.axis_label = "Dose (Gy)"
    else:
        x_scale = ['%RxDose'] * (dvh.count + extra_rows + 1)
        dvh_plots.xaxis.axis_label = "Relative Dose (to Rx)"
    if radio_group_volume.active == 0:
        y_scale = ['cm^3'] * (dvh.count + extra_rows + 1)
        dvh_plots.yaxis.axis_label = "Absolute Volume (cc)"
    else:
        y_scale = ['%Vol'] * (dvh.count + extra_rows + 1)
        dvh_plots.yaxis.axis_label = "Relative Volume"

    new_endpoint_columns = [''] * (dvh.count + extra_rows + 1)

    x_data, y_data = [], []
    for n in range(0, dvh.count):
        if radio_group_dose.active == 0:
            x_data.append(x_axis.tolist())
        else:
            x_data.append(np.divide(x_axis, dvh.rx_dose[n]).tolist())
        if radio_group_volume.active == 0:
            y_data.append(np.multiply(dvh.dvh[:, n], dvh.volume[n]).tolist())
        else:
            y_data.append(dvh.dvh[:, n].tolist())

    y_names = ['Max', 'Q3', 'Median', 'Mean', 'Q1', 'Min']

    # Determine Population group (blue (1) or red (2))
    dvh_groups = []
    for r in range(0, len(dvh.study_instance_uid)):

        current_uid = dvh.study_instance_uid[r]
        current_roi = dvh.roi_name[r]

        if dvh_group_1:
            for r1 in range(0, len(dvh_group_1.study_instance_uid)):
                if dvh_group_1.study_instance_uid[r1] == current_uid and dvh_group_1.roi_name[r1] == current_roi:
                    dvh_groups.append('Blue')

        if dvh_group_2:
            for r2 in range(0, len(dvh_group_2.study_instance_uid)):
                if dvh_group_2.study_instance_uid[r2] == current_uid and dvh_group_2.roi_name[r2] == current_roi:
                    if len(dvh_groups) == r + 1:
                        dvh_groups[r] = 'Blue & Red'
                    else:
                        dvh_groups.append('Red')

        if len(dvh_groups) < r + 1:
            dvh_groups.append('error')

    dvh_groups.insert(0, 'Review')

    for n in range(0, 6):
        if group_1_count > 0:
            dvh.mrn.append(y_names[n])
            dvh.roi_name.append('N/A')
            x_data.append(x_axis_stat.tolist())
            current = stat_dvhs_1[y_names[n].lower()].tolist()
            y_data.append(current)
            dvh_groups.append('Blue')
        if group_2_count > 0:
            dvh.mrn.append(y_names[n])
            dvh.roi_name.append('N/A')
            x_data.append(x_axis_stat.tolist())
            current = stat_dvhs_2[y_names[n].lower()].tolist()
            y_data.append(current)
            dvh_groups.append('Red')

    # Adjust dvh object to include stats data
    if extra_rows > 0:
        dvh.study_instance_uid.extend(['N/A'] * extra_rows)
        dvh.institutional_roi.extend(['N/A'] * extra_rows)
        dvh.physician_roi.extend(['N/A'] * extra_rows)
        dvh.roi_type.extend(['Stat'] * extra_rows)
    if group_1_count > 0:
        dvh.rx_dose.extend(calc_stats(dvh_group_1.rx_dose))
        dvh.volume.extend(calc_stats(dvh_group_1.volume))
        dvh.surface_area.extend(calc_stats(dvh_group_1.surface_area))
        dvh.min_dose.extend(calc_stats(dvh_group_1.min_dose))
        dvh.mean_dose.extend(calc_stats(dvh_group_1.mean_dose))
        dvh.max_dose.extend(calc_stats(dvh_group_1.max_dose))
        dvh.dist_to_ptv_min.extend(calc_stats(dvh_group_1.dist_to_ptv_min))
        dvh.dist_to_ptv_median.extend(calc_stats(dvh_group_1.dist_to_ptv_median))
        dvh.dist_to_ptv_mean.extend(calc_stats(dvh_group_1.dist_to_ptv_mean))
        dvh.dist_to_ptv_max.extend(calc_stats(dvh_group_1.dist_to_ptv_max))
        dvh.ptv_overlap.extend(calc_stats(dvh_group_1.ptv_overlap))
    if group_2_count > 0:
        dvh.rx_dose.extend(calc_stats(dvh_group_2.rx_dose))
        dvh.volume.extend(calc_stats(dvh_group_2.volume))
        dvh.surface_area.extend(calc_stats(dvh_group_2.surface_area))
        dvh.min_dose.extend(calc_stats(dvh_group_2.min_dose))
        dvh.mean_dose.extend(calc_stats(dvh_group_2.mean_dose))
        dvh.max_dose.extend(calc_stats(dvh_group_2.max_dose))
        dvh.dist_to_ptv_min.extend(calc_stats(dvh_group_2.dist_to_ptv_min))
        dvh.dist_to_ptv_median.extend(calc_stats(dvh_group_2.dist_to_ptv_median))
        dvh.dist_to_ptv_mean.extend(calc_stats(dvh_group_2.dist_to_ptv_mean))
        dvh.dist_to_ptv_max.extend(calc_stats(dvh_group_2.dist_to_ptv_max))
        dvh.ptv_overlap.extend(calc_stats(dvh_group_2.ptv_overlap))

    # Adjust dvh object for review dvh
    dvh.dvh = np.insert(dvh.dvh, 0, 0, 1)
    dvh.count += 1
    dvh.mrn.insert(0, select_reviewed_mrn.value)
    dvh.study_instance_uid.insert(0, '')
    dvh.institutional_roi.insert(0, '')
    dvh.physician_roi.insert(0, '')
    dvh.roi_name.insert(0, select_reviewed_dvh.value)
    dvh.roi_type.insert(0, 'Review')
    dvh.rx_dose.insert(0, 0)
    dvh.volume.insert(0, 0)
    dvh.surface_area.insert(0, '')
    dvh.min_dose.insert(0, '')
    dvh.mean_dose.insert(0, '')
    dvh.max_dose.insert(0, '')
    dvh.dist_to_ptv_min.insert(0, 'N/A')
    dvh.dist_to_ptv_mean.insert(0, 'N/A')
    dvh.dist_to_ptv_median.insert(0, 'N/A')
    dvh.dist_to_ptv_max.insert(0, 'N/A')
    dvh.ptv_overlap.insert(0, 'N/A')
    line_colors.insert(0, 'green')
    x_data.insert(0, [0])
    y_data.insert(0, [0])

    # anonymize ids
    anon_id_map = {mrn: i for i, mrn in enumerate(list(set(dvh.mrn)))}
    anon_id = [anon_id_map[dvh.mrn[i]] for i in range(0, len(dvh.mrn))]

    print(str(datetime.now()), 'writing source.data', sep=' ')
    source.data = {'mrn': dvh.mrn,
                   'anon_id': anon_id,
                   'group': dvh_groups,
                   'uid': dvh.study_instance_uid,
                   'roi_institutional': dvh.institutional_roi,
                   'roi_physician': dvh.physician_roi,
                   'roi_name': dvh.roi_name,
                   'roi_type': dvh.roi_type,
                   'rx_dose': dvh.rx_dose,
                   'volume': dvh.volume,
                   'surface_area': dvh.surface_area,
                   'min_dose': dvh.min_dose,
                   'mean_dose': dvh.mean_dose,
                   'max_dose': dvh.max_dose,
                   'dist_to_ptv_min': dvh.dist_to_ptv_min,
                   'dist_to_ptv_mean': dvh.dist_to_ptv_mean,
                   'dist_to_ptv_median': dvh.dist_to_ptv_median,
                   'dist_to_ptv_max': dvh.dist_to_ptv_max,
                   'ptv_overlap': dvh.ptv_overlap,
                   'x': x_data,
                   'y': y_data,
                   'color': line_colors,
                   'ep1': new_endpoint_columns,
                   'ep2': new_endpoint_columns,
                   'ep3': new_endpoint_columns,
                   'ep4': new_endpoint_columns,
                   'ep5': new_endpoint_columns,
                   'ep6': new_endpoint_columns,
                   'ep7': new_endpoint_columns,
                   'ep8': new_endpoint_columns,
                   'x_scale': x_scale,
                   'y_scale': y_scale}

    print(str(datetime.now()), 'begin updating beam, plan, rx data sources', sep=' ')
    update_beam_data(dvh.study_instance_uid)
    update_plan_data(dvh.study_instance_uid)
    update_rx_data(dvh.study_instance_uid)
    print(str(datetime.now()), 'all sources set', sep=' ')

    return dvh_group_1, dvh_group_2


# updates beam ColumnSourceData for a given list of uids
def update_beam_data(uids):

    cond_str = "study_instance_uid in ('" + "', '".join(uids) + "')"
    beam_data = QuerySQL('Beams', cond_str)

    groups = get_group_list(beam_data.study_instance_uid)

    anon_id = [anon_id_map[beam_data.mrn[i]] for i in range(0, len(beam_data.mrn))]

    source_beams.data = {'mrn': beam_data.mrn,
                         'anon_id': anon_id,
                         'group': groups,
                         'uid': beam_data.study_instance_uid,
                         'beam_dose': beam_data.beam_dose,
                         'beam_energy_min': beam_data.beam_energy_min,
                         'beam_energy_max': beam_data.beam_energy_max,
                         'beam_mu': beam_data.beam_mu,
                         'beam_mu_per_deg': beam_data.beam_mu_per_deg,
                         'beam_mu_per_cp': beam_data.beam_mu_per_cp,
                         'beam_name': beam_data.beam_name,
                         'beam_number': beam_data.beam_number,
                         'beam_type': beam_data.beam_type,
                         'scan_mode': beam_data.scan_mode,
                         'scan_spot_count': beam_data.scan_spot_count,
                         'control_point_count': beam_data.control_point_count,
                         'fx_count': beam_data.fx_count,
                         'fx_grp_beam_count': beam_data.fx_grp_beam_count,
                         'fx_grp_number': beam_data.fx_grp_number,
                         'gantry_start': beam_data.gantry_start,
                         'gantry_end': beam_data.gantry_end,
                         'gantry_rot_dir': beam_data.gantry_rot_dir,
                         'gantry_range': beam_data.gantry_range,
                         'gantry_min': beam_data.gantry_min,
                         'gantry_max': beam_data.gantry_max,
                         'collimator_start': beam_data.collimator_start,
                         'collimator_end': beam_data.collimator_end,
                         'collimator_rot_dir': beam_data.collimator_rot_dir,
                         'collimator_range': beam_data.collimator_range,
                         'collimator_min': beam_data.collimator_min,
                         'collimator_max': beam_data.collimator_max,
                         'couch_start': beam_data.couch_start,
                         'couch_end': beam_data.couch_end,
                         'couch_rot_dir': beam_data.couch_rot_dir,
                         'couch_range': beam_data.couch_range,
                         'couch_min': beam_data.couch_min,
                         'couch_max': beam_data.couch_max,
                         'radiation_type': beam_data.radiation_type,
                         'ssd': beam_data.ssd,
                         'treatment_machine': beam_data.treatment_machine}


# updates plan ColumnSourceData for a given list of uids
def update_plan_data(uids):

    cond_str = "study_instance_uid in ('" + "', '".join(uids) + "')"
    plan_data = QuerySQL('Plans', cond_str)

    # Determine Groups
    groups = get_group_list(plan_data.study_instance_uid)

    anon_id = [anon_id_map[plan_data.mrn[i]] for i in range(0, len(plan_data.mrn))]

    source_plans.data = {'mrn': plan_data.mrn,
                         'anon_id': anon_id,
                         'uid': plan_data.study_instance_uid,
                         'group': groups,
                         'age': plan_data.age,
                         'birth_date': plan_data.birth_date,
                         'dose_grid_res': plan_data.dose_grid_res,
                         'fxs': plan_data.fxs,
                         'patient_orientation': plan_data.patient_orientation,
                         'patient_sex': plan_data.patient_sex,
                         'physician': plan_data.physician,
                         'rx_dose': plan_data.rx_dose,
                         'sim_study_date': plan_data.sim_study_date,
                         'total_mu': plan_data.total_mu,
                         'tx_modality': plan_data.tx_modality,
                         'tx_site': plan_data.tx_site,
                         'heterogeneity_correction': plan_data.heterogeneity_correction,
                         'baseline': plan_data.baseline}


# updates rx ColumnSourceData for a given list of uids
def update_rx_data(uids):

    cond_str = "study_instance_uid in ('" + "', '".join(uids) + "')"
    rx_data = QuerySQL('Rxs', cond_str)

    groups = get_group_list(rx_data.study_instance_uid)

    anon_id = [anon_id_map[rx_data.mrn[i]] for i in range(0, len(rx_data.mrn))]

    source_rxs.data = {'mrn': rx_data.mrn,
                       'anon_id': anon_id,
                       'uid': rx_data.study_instance_uid,
                       'group': groups,
                       'plan_name': rx_data.plan_name,
                       'fx_dose': rx_data.fx_dose,
                       'rx_percent': rx_data.rx_percent,
                       'fxs': rx_data.fxs,
                       'rx_dose': rx_data.rx_dose,
                       'fx_grp_count': rx_data.fx_grp_count,
                       'fx_grp_name': rx_data.fx_grp_name,
                       'fx_grp_number': rx_data.fx_grp_number,
                       'normalization_method': rx_data.normalization_method,
                       'normalization_object': rx_data.normalization_object}


def get_group_list(uids):

    groups = []
    for r in range(0, len(uids)):
        if uids[r] in uids_1:
            if uids[r] in uids_2:
                groups.append('Blue & Red')
            else:
                groups.append('Blue')
        else:
            groups.append('Red')

    return groups


def calc_stats(data):
    try:
        data_np = np.array(data)
        rtn_data = [np.max(data_np),
                    np.percentile(data_np, 75),
                    np.median(data_np),
                    np.mean(data_np),
                    np.percentile(data_np, 25),
                    np.min(data_np)]
    except:
        rtn_data = [0, 0, 0, 0, 0, 0]
    return rtn_data


def group_count():
    group_1_count, group_2_count = 0, 0

    data = source_selectors.data
    for r in data['row']:
        r = int(r)
        if 1 in data['group']:
            group_1_count += 1
        if 2 in data['group']:
            group_2_count += 1

    data = source_ranges.data
    for r in data['row']:
        r = int(r)
        if 1 in data['group'][r-1]:
            group_1_count += 1
        if 2 in data['group'][r-1]:
            group_2_count += 1

    return group_1_count, group_2_count


def update_source_endpoint_calcs():

    num_stats_to_calculate = 6

    group_1_count, group_2_count = group_count()

    ep, ep_1, ep_2 = {'mrn': ['']}, {}, {}

    table_columns = []

    ep['mrn'] = current_dvh.mrn
    ep['group'] = source.data['group']
    ep['roi_name'] = source.data['roi_name']
    if group_1_count:
        ep_1['mrn'] = current_dvh_group_1.mrn
    if group_2_count:
        ep_2['mrn'] = current_dvh_group_2.mrn
    table_columns.append(TableColumn(field='mrn', title='MRN'))
    table_columns.append(TableColumn(field='group', title='Group'))
    table_columns.append(TableColumn(field='roi_name', title='ROI Name'))

    data = source_endpoint_defs.data
    for r in range(0, len(data['row'])):

        ep_name = str(data['label'][r])
        table_columns.append(TableColumn(field=ep_name, title=ep_name, formatter=NumberFormatter(format="0.00")))
        x = data['input_value'][r]

        if '%' in data['units_in'][r]:
            endpoint_input = 'relative'
            x /= 100.
        else:
            endpoint_input = 'absolute'

        if '%' in data['units_out'][r]:
            endpoint_output = 'relative'
        else:
            endpoint_output = 'absolute'

        if 'Dose' in data['output_type'][r]:
            ep[ep_name] = current_dvh.get_dose_to_volume(x, input=endpoint_input, output=endpoint_output)
            if group_1_count:
                ep_1[ep_name] = current_dvh_group_1.get_dose_to_volume(x, input=endpoint_input, output=endpoint_output)
                ep_1[ep_name].extend([''] * num_stats_to_calculate)
            if group_2_count:
                ep_2[ep_name] = current_dvh_group_2.get_dose_to_volume(x, input=endpoint_input, output=endpoint_output)
                ep_2[ep_name].extend([''] * num_stats_to_calculate)
        else:
            ep[ep_name] = current_dvh.get_volume_of_dose(x, input=endpoint_input, output=endpoint_output)
            if group_1_count:
                ep_1[ep_name] = current_dvh_group_1.get_volume_of_dose(x, input=endpoint_input, output=endpoint_output)
                ep_1[ep_name].extend([''] * num_stats_to_calculate)
            if group_2_count:
                ep_2[ep_name] = current_dvh_group_2.get_volume_of_dose(x, input=endpoint_input, output=endpoint_output)
                ep_2[ep_name].extend([''] * num_stats_to_calculate)

        if group_1_count and group_2_count:
            ep[ep_name].extend([''] * num_stats_to_calculate * 2)
        else:
            ep[ep_name].extend([''] * num_stats_to_calculate)

    # Need to calculate stats here per group

    # If number of columns are different, need to remove table from layout, and create a new table
    if len(ep) == len(source_endpoint_calcs.data):
        source_endpoint_calcs.data = ep
    else:
        source_endpoint_calcs.data = ep
        data_table_new = DataTable(source=source_endpoint_calcs, columns=table_columns, width=1200)
        layout_dvhs.children.pop()
        layout_dvhs.children.append(data_table_new)


def update_roi_viewer_mrn():
    options = [mrn for mrn in source_plans.data['mrn']]
    if options:
        options.sort()
        roi_viewer_mrn_select.options = options
        roi_viewer_mrn_select.value = options[0]
    else:
        roi_viewer_mrn_select.options = ['']
        roi_viewer_mrn_select.value = ''


def roi_viewer_mrn_ticker(attr, old, new):

    if new == '':
        roi_viewer_study_date_select.options = ['']
        roi_viewer_study_date_select.value = ''
        roi_viewer_uid_select.options = ['']
        roi_viewer_uid_select.value = ''
        roi_viewer_roi_select.options = ['']
        roi_viewer_roi_select.value = ''
        roi_viewer_roi2_select.options = ['']
        roi_viewer_roi2_select.value = ''
        roi_viewer_roi3_select.options = ['']
        roi_viewer_roi3_select.value = ''
        roi_viewer_roi4_select.options = ['']
        roi_viewer_roi4_select.value = ''
        roi_viewer_roi5_select.options = ['']
        roi_viewer_roi5_select.value = ''

    else:
        # Clear out additional ROIs since current values may not exist in new patient set
        roi_viewer_roi2_select.value = ''
        roi_viewer_roi3_select.value = ''
        roi_viewer_roi4_select.value = ''
        roi_viewer_roi5_select.value = ''

        options = []
        for i in range(0, len(source_plans.data['mrn'])):
            if source_plans.data['mrn'][i] == new:
                options.append(source_plans.data['sim_study_date'][i])
        options.sort()
        old_sim_date = roi_viewer_study_date_select.value
        roi_viewer_study_date_select.options = options
        roi_viewer_study_date_select.value = options[0]
        if old_sim_date == options[0]:
            update_roi_viewer_uid()


def roi_viewer_study_date_ticker(attr, old, new):
    update_roi_viewer_uid()


def update_roi_viewer_uid():
    if roi_viewer_mrn_select.value != '':
        options = []
        for i in range(0, len(source_plans.data['mrn'])):
            if source_plans.data['mrn'][i] == roi_viewer_mrn_select.value and \
                            source_plans.data['sim_study_date'][i] == roi_viewer_study_date_select.value:
                options.append(source_plans.data['uid'][i])
        roi_viewer_uid_select.options = options
        roi_viewer_uid_select.value = options[0]


def roi_viewer_uid_ticker(attr, old, new):
    update_roi_viewer_rois()


def roi_viewer_roi_ticker(attr, old, new):
    global roi_viewer_data
    roi_viewer_data = update_roi_viewer_data(roi_viewer_roi_select.value)
    update_roi_viewer_slice()


def roi_viewer_roi2_ticker(attr, old, new):
    global roi2_viewer_data
    roi2_viewer_data = update_roi_viewer_data(roi_viewer_roi2_select.value)
    update_roi2_viewer()


def roi_viewer_roi3_ticker(attr, old, new):
    global roi3_viewer_data
    roi3_viewer_data = update_roi_viewer_data(roi_viewer_roi3_select.value)
    update_roi3_viewer()


def roi_viewer_roi4_ticker(attr, old, new):
    global roi4_viewer_data
    roi4_viewer_data = update_roi_viewer_data(roi_viewer_roi4_select.value)
    update_roi4_viewer()


def roi_viewer_roi5_ticker(attr, old, new):
    global roi5_viewer_data
    roi5_viewer_data = update_roi_viewer_data(roi_viewer_roi5_select.value)
    update_roi5_viewer()


def roi_viewer_roi1_color_ticker(attr, old, new):
    roi_viewer_patch1.glyph.fill_color = new
    roi_viewer_patch1.glyph.line_color = new


def roi_viewer_roi2_color_ticker(attr, old, new):
    roi_viewer_patch2.glyph.fill_color = new
    roi_viewer_patch2.glyph.line_color = new


def roi_viewer_roi3_color_ticker(attr, old, new):
    roi_viewer_patch3.glyph.fill_color = new
    roi_viewer_patch3.glyph.line_color = new


def roi_viewer_roi4_color_ticker(attr, old, new):
    roi_viewer_patch4.glyph.fill_color = new
    roi_viewer_patch4.glyph.line_color = new


def roi_viewer_roi5_color_ticker(attr, old, new):
    roi_viewer_patch5.glyph.fill_color = new
    roi_viewer_patch5.glyph.line_color = new


def roi_viewer_slice_ticker(attr, old, new):
    update_roi_viewer()
    update_roi2_viewer()
    update_roi3_viewer()
    update_roi4_viewer()
    update_roi5_viewer()
    source_tv.data = {'x': [], 'y': [], 'z': []}


def update_roi_viewer_slice():
    options = list(roi_viewer_data)
    options.sort()
    roi_viewer_slice_select.options = options
    roi_viewer_slice_select.value = options[len(options) / 2]  # default to the middle slice


def roi_viewer_go_to_previous_slice():
    index = roi_viewer_slice_select.options.index(roi_viewer_slice_select.value)
    roi_viewer_slice_select.value = roi_viewer_slice_select.options[index - 1]


def roi_viewer_go_to_next_slice():
    index = roi_viewer_slice_select.options.index(roi_viewer_slice_select.value)
    if index + 1 == len(roi_viewer_slice_select.options):
        index = -1
    roi_viewer_slice_select.value = roi_viewer_slice_select.options[index + 1]


def update_roi_viewer_rois():

    options = DVH_SQL().get_unique_values('DVHs', 'roi_name', "study_instance_uid = '%s'" % roi_viewer_uid_select.value)
    options.sort()

    roi_viewer_roi_select.options = options
    # default to an external like ROI if found
    if 'external' in options:
        roi_viewer_roi_select.value = 'external'
    elif 'ext' in options:
        roi_viewer_roi_select.value = 'ext'
    elif 'body' in options:
        roi_viewer_roi_select.value = 'body'
    elif 'skin' in options:
        roi_viewer_roi_select.value = 'skin'
    else:
        roi_viewer_roi_select.value = options[0]

    roi_viewer_roi2_select.options = [''] + options
    roi_viewer_roi2_select.value = ''

    roi_viewer_roi3_select.options = [''] + options
    roi_viewer_roi3_select.value = ''

    roi_viewer_roi4_select.options = [''] + options
    roi_viewer_roi4_select.value = ''

    roi_viewer_roi5_select.options = [''] + options
    roi_viewer_roi5_select.value = ''


def update_roi_viewer_data(roi_name):

    # if roi_name is an empty string (default selection), return an empty data set
    if not roi_name:
        return {'0': {'x': [], 'y': [], 'z': []}}

    roi_data = {}
    uid = roi_viewer_uid_select.value
    roi_coord_string = DVH_SQL().query('dvhs',
                                       'roi_coord_string',
                                       "study_instance_uid = '%s' and roi_name = '%s'" % (uid, roi_name))
    roi_planes = get_planes_from_string(roi_coord_string[0][0])
    for z_plane in list(roi_planes):
        x, y, z = [], [], []
        for polygon in roi_planes[z_plane]:
            initial_polygon_index = len(x)
            for point in polygon:
                x.append(point[0])
                y.append(point[1])
                z.append(point[2])
            x.append(x[initial_polygon_index])
            y.append(y[initial_polygon_index])
            z.append(z[initial_polygon_index])
            x.append(float('nan'))
            y.append(float('nan'))
            z.append(float('nan'))
        roi_data[z_plane] = {'x': x, 'y': y, 'z': z}

    return roi_data


def update_tv_data():
    global tv_data
    tv_data = {}

    uid = roi_viewer_uid_select.value
    ptv_coordinates_strings = DVH_SQL().query('dvhs',
                                              'roi_coord_string',
                                              "study_instance_uid = '%s' and roi_type like 'PTV%%'"
                                              % uid)

    if ptv_coordinates_strings:

        ptvs = [get_planes_from_string(ptv[0]) for ptv in ptv_coordinates_strings]
        tv_planes = get_union(ptvs)

    for z_plane in list(tv_planes):
        x, y, z = [], [], []
        for polygon in tv_planes[z_plane]:
            initial_polygon_index = len(x)
            for point in polygon:
                x.append(point[0])
                y.append(point[1])
                z.append(point[2])
            x.append(x[initial_polygon_index])
            y.append(y[initial_polygon_index])
            z.append(z[initial_polygon_index])
            x.append(float('nan'))
            y.append(float('nan'))
            z.append(float('nan'))
            tv_data[z_plane] = {'x': x,
                                'y': y,
                                'z': z}


def update_roi_viewer():
    z = roi_viewer_slice_select.value
    source_roi_viewer.data = roi_viewer_data[z]


def update_roi2_viewer():
    z = roi_viewer_slice_select.value
    if z in list(roi2_viewer_data):
        source_roi2_viewer.data = roi2_viewer_data[z]
    else:
        source_roi2_viewer.data = {'x': [], 'y': [], 'z': []}


def update_roi3_viewer():
    z = roi_viewer_slice_select.value
    if z in list(roi3_viewer_data):
        source_roi3_viewer.data = roi3_viewer_data[z]
    else:
        source_roi3_viewer.data = {'x': [], 'y': [], 'z': []}


def update_roi4_viewer():
    z = roi_viewer_slice_select.value
    if z in list(roi4_viewer_data):
        source_roi4_viewer.data = roi4_viewer_data[z]
    else:
        source_roi4_viewer.data = {'x': [], 'y': [], 'z': []}


def update_roi5_viewer():
    z = roi_viewer_slice_select.value
    if z in list(roi5_viewer_data):
        source_roi5_viewer.data = roi5_viewer_data[z]
    else:
        source_roi5_viewer.data = {'x': [], 'y': [], 'z': []}


def roi_viewer_flip_y_axis():
    if roi_viewer.y_range.flipped:
        roi_viewer.y_range.flipped = False
    else:
        roi_viewer.y_range.flipped = True


def roi_viewer_flip_x_axis():
    if roi_viewer.x_range.flipped:
        roi_viewer.x_range.flipped = False
    else:
        roi_viewer.x_range.flipped = True


def roi_viewer_plot_tv():
    update_tv_data()
    z = roi_viewer_slice_select.value
    if z in list(tv_data) and not source_tv.data['x']:
        source_tv.data = tv_data[z]
    else:
        source_tv.data = {'x': [], 'y': [], 'z': []}


def roi_viewer_wheel_event(event):
    if roi_viewer_scrolling.active:
        if event.delta > 0:
            roi_viewer_go_to_next_slice()
        elif event.delta < 0:
            roi_viewer_go_to_previous_slice()


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Selection Filter UI objects
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!
category_options = list(selector_categories)
category_options.sort()

div_selector = Div(text="<b>Query by Categorical Data</b>", width=1000)
div_selector_end = Div(text="<hr>", width=1050)

# Add Current row to source
add_selector_row_button = Button(label="Add Selection Filter", button_type="primary", width=200)
add_selector_row_button.on_click(add_selector_row)

# Row
selector_row = Select(value='1', options=['1'], width=50, title="Row")
selector_row.on_change('value', selector_row_ticker)

# Category 1
select_category1 = Select(value="ROI Institutional Category", options=category_options, width=300, title="Category 1")
select_category1.on_change('value', select_category1_ticker)

# Category 2
cat_2_sql_table = selector_categories[select_category1.value]['table']
cat_2_var_name = selector_categories[select_category1.value]['var_name']
category2_values = DVH_SQL().get_unique_values(cat_2_sql_table, cat_2_var_name)
select_category2 = Select(value=category2_values[0], options=category2_values, width=300, title="Category 2")
select_category2.on_change('value', select_category2_ticker)

# Misc
delete_selector_row_button = Button(label="Delete", button_type="warning", width=100)
delete_selector_row_button.on_click(delete_selector_row)
group_selector = CheckboxButtonGroup(labels=["Group 1", "Group 2"], active=[0], width=180)
group_selector.on_change('active', ensure_selector_group_is_assigned)
selector_not_operator_checkbox = CheckboxGroup(labels=['Not'], active=[])
selector_not_operator_checkbox.on_change('active', selector_not_operator_ticker)

# Selector Category table
columns = [TableColumn(field="row", title="Row", width=60),
           TableColumn(field="category1", title="Selection Category 1", width=280),
           TableColumn(field="category2", title="Selection Category 2", width=280),
           TableColumn(field="group_label", title="Group", width=170),
           TableColumn(field="not_status", title="Apply Not Operator", width=150)]
selection_filter_data_table = DataTable(source=source_selectors,
                                        columns=columns, width=1000, height=150, row_headers=False)
source_selectors.on_change('selected', update_selector_row_on_selection)
update_selector_source()

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Range Filter UI objects
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!
category_options = list(range_categories)
category_options.sort()

div_range = Div(text="<b>Query by Numerical Data</b>", width=1000)
div_range_end = Div(text="<hr>", width=1050)

# Add Current row to source
add_range_row_button = Button(label="Add Range Filter", button_type="primary", width=200)
add_range_row_button.on_click(add_range_row)

# Row
range_row = Select(value='', options=[''], width=50, title="Row")
range_row.on_change('value', range_row_ticker)

# Category
select_category = Select(value=SELECT_CATEGORY_DEFAULT, options=category_options, width=240, title="Category")
select_category.on_change('value', select_category_ticker)

# Min and max
text_min = TextInput(value='', title='Min: ', width=180)
text_min.on_change('value', min_text_ticker)
text_max = TextInput(value='', title='Max: ', width=180)
text_max.on_change('value', max_text_ticker)

# Misc
delete_range_row_button = Button(label="Delete", button_type="warning", width=100)
delete_range_row_button.on_click(delete_range_row)
group_range = CheckboxButtonGroup(labels=["Group 1", "Group 2"], active=[0], width=180)
group_range.on_change('active', ensure_range_group_is_assigned)
range_not_operator_checkbox = CheckboxGroup(labels=['Not'], active=[])
range_not_operator_checkbox.on_change('active', range_not_operator_ticker)

# Selector Category table
columns = [TableColumn(field="row", title="Row", width=60),
           TableColumn(field="category", title="Range Category", width=230),
           TableColumn(field="min_display", title="Min", width=170),
           TableColumn(field="max_display", title="Max", width=170),
           TableColumn(field="group_label", title="Group", width=180),
           TableColumn(field="not_status", title="Apply Not Operator", width=150)]
range_filter_data_table = DataTable(source=source_ranges,
                                    columns=columns, width=1000, height=150, row_headers=False)
source_ranges.on_change('selected', update_range_row_on_selection)

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# DVH Endpoint Filter UI objects
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
div_endpoint = Div(text="<b>Define Endpoints</b>", width=1000)

# Add Current row to source
add_endpoint_row_button = Button(label="Add Endpoint", button_type="primary", width=200)
add_endpoint_row_button.on_click(add_endpoint)

ep_row = Select(value='', options=[''], width=50, title="Row")
ep_options = ["Dose (Gy)", "Dose (%)", "Volume (cc)", "Volume (%)"]
select_ep_type = Select(value=ep_options[0], options=ep_options, width=180, title="Output")
select_ep_type.on_change('value', select_ep_type_ticker)
ep_text_input = TextInput(value='', title="Input Volume (cc):", width=180)
ep_text_input.on_change('value', ep_text_input_ticker)
ep_units_in = RadioButtonGroup(labels=["cc", "%"], active=0, width=100)
ep_units_in.on_change('active', ep_units_in_ticker)
delete_ep_row_button= Button(label="Delete", button_type="warning", width=100)
delete_ep_row_button.on_click(delete_ep_row)

# endpoint  table
columns = [TableColumn(field="row", title="Row", width=60),
           TableColumn(field="label", title="Endpoint", width=180),
           TableColumn(field="units_out", title="Units", width=60)]
ep_data_table = DataTable(source=source_endpoint_defs, columns=columns, width=300, height=150, row_headers=False)

source_endpoint_defs.on_change('selected', update_ep_row_on_selection)

query_button = Button(label="Query", button_type="success", width=200)
query_button.on_click(update_data)


def custom_title_blue_ticker(attr, old, new):
    custom_title_query_blue.value = new
    custom_title_dvhs_blue.value = new
    custom_title_rad_bio_blue.value = new
    custom_title_roi_viewer_blue.value = new
    custom_title_planning_blue.value = new
    custom_title_time_series_blue.value = new
    custom_title_correlation_blue.value = new
    custom_title_regression_blue.value = new


def custom_title_red_ticker(attr, old, new):
    custom_title_query_red.value = new
    custom_title_dvhs_red.value = new
    custom_title_rad_bio_red.value = new
    custom_title_roi_viewer_red.value = new
    custom_title_planning_red.value = new
    custom_title_time_series_red.value = new
    custom_title_correlation_red.value = new
    custom_title_regression_red.value = new


# Ticker function for abs/rel dose radio buttons
# any change will call update_data, if any source data has been retrieved from SQL
def radio_group_dose_ticker(attr, old, new):
    if source.data['x'] != '':
        update_data()
        # calculate_review_dvh()


# Ticker function for abs/rel volume radio buttons
# any change will call update_data, if any source data has been retrieved from SQL
def radio_group_volume_ticker(attr, old, new):
    if source.data['x'] != '':
        update_data()
        # calculate_review_dvh()


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Set up Layout
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
min_border = 75
tools = "pan,wheel_zoom,box_zoom,reset,crosshair,save"
dvh_plots = figure(plot_width=1050, plot_height=500, tools=tools, logo=None, active_drag="box_zoom")
dvh_plots.min_border_left = min_border
dvh_plots.min_border_bottom = min_border
dvh_plots.add_tools(HoverTool(show_arrow=False, line_policy='next',
                              tooltips=[('Label', '@mrn @roi_name'),
                                        ('Dose', '$x'),
                                        ('Volume', '$y')]))
dvh_plots.xaxis.axis_label_text_font_size = PLOT_AXIS_LABEL_FONT_SIZE
dvh_plots.yaxis.axis_label_text_font_size = PLOT_AXIS_LABEL_FONT_SIZE
dvh_plots.xaxis.major_label_text_font_size = PLOT_AXIS_MAJOR_LABEL_FONT_SIZE
dvh_plots.yaxis.major_label_text_font_size = PLOT_AXIS_MAJOR_LABEL_FONT_SIZE
dvh_plots.yaxis.axis_label_text_baseline = "bottom"
dvh_plots.lod_factor = LOD_FACTOR  # level of detail during interactive plot events

# Add statistical plots to figure
stats_median_1 = dvh_plots.line('x', 'median', source=source_stats_1,
                                line_width=STATS_1_MEDIAN_LINE_WIDTH, color=GROUP_1_COLOR,
                                line_dash=STATS_1_MEDIAN_LINE_DASH, alpha=STATS_1_MEDIAN_ALPHA)
stats_mean_1 = dvh_plots.line('x', 'mean', source=source_stats_1,
                              line_width=STATS_1_MEAN_LINE_WIDTH, color=GROUP_1_COLOR,
                              line_dash=STATS_1_MEAN_LINE_DASH, alpha=STATS_1_MEAN_ALPHA)
stats_median_2 = dvh_plots.line('x', 'median', source=source_stats_2,
                                line_width=STATS_2_MEDIAN_LINE_WIDTH, color=GROUP_2_COLOR,
                                line_dash=STATS_2_MEDIAN_LINE_DASH, alpha=STATS_2_MEDIAN_ALPHA)
stats_mean_2 = dvh_plots.line('x', 'mean', source=source_stats_2,
                              line_width=STATS_2_MEAN_LINE_WIDTH, color=GROUP_2_COLOR,
                              line_dash=STATS_2_MEAN_LINE_DASH, alpha=STATS_2_MEAN_ALPHA)

# Add all DVHs, but hide them until selected
dvh_plots.multi_line('x', 'y', source=source,
                     selection_color='color', line_width=DVH_LINE_WIDTH, alpha=0,
                     nonselection_alpha=0, selection_alpha=1)

# Shaded region between Q1 and Q3
iqr_1 = dvh_plots.patch('x_patch', 'y_patch', source=source_patch_1, alpha=IQR_1_ALPHA, color=GROUP_1_COLOR)
iqr_2 = dvh_plots.patch('x_patch', 'y_patch', source=source_patch_2, alpha=IQR_2_ALPHA, color=GROUP_2_COLOR)

# Set x and y axis labels
dvh_plots.xaxis.axis_label = "Dose (Gy)"
dvh_plots.yaxis.axis_label = "Normalized Volume"

# Set the legend (for stat dvhs only)
legend_stats = Legend(items=[("Median", [stats_median_1]),
                             ("Mean", [stats_mean_1]),
                             ("IQR", [iqr_1]),
                             ("Median", [stats_median_2]),
                             ("Mean", [stats_mean_2]),
                             ("IQR", [iqr_2])],
                      location=(25, 0))

# Add the layout outside the plot, clicking legend item hides the line
dvh_plots.add_layout(legend_stats, 'right')
dvh_plots.legend.click_policy = "hide"

# Set up DataTable for dvhs
data_table_title = Div(text="<b>DVHs</b>", width=1200)
columns = [TableColumn(field="mrn", title="MRN / Stat", width=175),
           TableColumn(field="group", title="Group", width=175),
           TableColumn(field="roi_name", title="ROI Name"),
           TableColumn(field="roi_type", title="ROI Type", width=80),
           TableColumn(field="rx_dose", title="Rx Dose", width=100, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="volume", title="Volume", width=80, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="min_dose", title="Min Dose", width=80, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="mean_dose", title="Mean Dose", width=80, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="max_dose", title="Max Dose", width=80, formatter=NumberFormatter(format="0.00")),
           TableColumn(field="dist_to_ptv_min", title="Dist to PTV", width=80, formatter=NumberFormatter(format="0.0")),
           TableColumn(field="ptv_overlap", title="PTV Overlap", width=80, formatter=NumberFormatter(format="0.0"))]
data_table = DataTable(source=source, columns=columns, width=1200, editable=True)

# Set up EndPoint DataTable
endpoint_table_title = Div(text="<b>DVH Endpoints</b>", width=1200)
data_table_endpoints = DataTable(source=source_endpoint_calcs, columns=[], width=1200, editable=True)

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Custom group titles
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
group_1_title = 'Group 1 (%s) Custom Title:' % GROUP_1_COLOR.capitalize()
group_2_title = 'Group 2 (%s) Custom Title:' % GROUP_2_COLOR.capitalize()
custom_title_query_blue = TextInput(value='', title=group_1_title, width=300)
custom_title_query_red = TextInput(value='', title=group_2_title, width=300)
custom_title_dvhs_blue = TextInput(value='', title=group_1_title, width=300)
custom_title_dvhs_red = TextInput(value='', title=group_2_title, width=300)
custom_title_rad_bio_blue = TextInput(value='', title=group_1_title, width=300)
custom_title_rad_bio_red = TextInput(value='', title=group_2_title, width=300)
custom_title_roi_viewer_blue = TextInput(value='', title=group_1_title, width=300)
custom_title_roi_viewer_red = TextInput(value='', title=group_2_title, width=300)
custom_title_planning_blue = TextInput(value='', title=group_1_title, width=300)
custom_title_planning_red = TextInput(value='', title=group_2_title, width=300)
custom_title_time_series_blue = TextInput(value='', title=group_1_title, width=300)
custom_title_time_series_red = TextInput(value='', title=group_2_title, width=300)
custom_title_correlation_blue = TextInput(value='', title=group_1_title, width=300)
custom_title_correlation_red = TextInput(value='', title=group_2_title, width=300)
custom_title_regression_blue = TextInput(value='', title=group_1_title, width=300)
custom_title_regression_red = TextInput(value='', title=group_2_title, width=300)

custom_title_query_blue.on_change('value', custom_title_blue_ticker)
custom_title_query_red.on_change('value', custom_title_red_ticker)
custom_title_dvhs_blue.on_change('value', custom_title_blue_ticker)
custom_title_dvhs_red.on_change('value', custom_title_red_ticker)
custom_title_rad_bio_blue.on_change('value', custom_title_blue_ticker)
custom_title_rad_bio_red.on_change('value', custom_title_red_ticker)
custom_title_roi_viewer_blue.on_change('value', custom_title_blue_ticker)
custom_title_roi_viewer_red.on_change('value', custom_title_red_ticker)
custom_title_planning_blue.on_change('value', custom_title_blue_ticker)
custom_title_planning_red.on_change('value', custom_title_red_ticker)
custom_title_time_series_blue.on_change('value', custom_title_blue_ticker)
custom_title_time_series_red.on_change('value', custom_title_red_ticker)
custom_title_correlation_blue.on_change('value', custom_title_blue_ticker)
custom_title_correlation_red.on_change('value', custom_title_red_ticker)
custom_title_regression_blue.on_change('value', custom_title_blue_ticker)
custom_title_regression_red.on_change('value', custom_title_red_ticker)

# Setup axis normalization radio buttons
radio_group_dose = RadioGroup(labels=["Absolute Dose", "Relative Dose (Rx)"], active=0, width=200)
radio_group_dose.on_change('active', radio_group_dose_ticker)
radio_group_volume = RadioGroup(labels=["Absolute Volume", "Relative Volume"], active=1, width=200)
radio_group_volume.on_change('active', radio_group_volume_ticker)

# Setup selectors for dvh review
select_reviewed_mrn = Select(title='MRN to review',
                             value='',
                             options=dvh_review_mrns,
                             width=300)
# select_reviewed_mrn.on_change('value', update_dvh_review_rois)

select_reviewed_dvh = Select(title='ROI to review',
                             value='',
                             options=[''],
                             width=360)
# select_reviewed_dvh.on_change('value', select_reviewed_dvh_ticker)

review_rx = TextInput(value='', title="Rx Dose (Gy):", width=170)
# review_rx.on_change('value', review_rx_ticker)

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ROI Viewer Objects
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
roi_colors = plot_colors.cnames.keys()
roi_colors.sort()
roi_viewer_options = [''] + source.data['mrn']
roi_viewer_mrn_select = Select(value='', options=roi_viewer_options, width=200, title='MRN')
roi_viewer_study_date_select = Select(value='', options=[''], width=200, title='Sim Study Date')
roi_viewer_uid_select = Select(value='', options=[''], width=400, title='Study Instance UID')
roi_viewer_roi_select = Select(value='', options=[''], width=250, title='ROI 1 Name')
roi_viewer_roi2_select = Select(value='', options=[''], width=200, title='ROI 2 Name')
roi_viewer_roi3_select = Select(value='', options=[''], width=200, title='ROI 3 Name')
roi_viewer_roi4_select = Select(value='', options=[''], width=200, title='ROI 4 Name')
roi_viewer_roi5_select = Select(value='', options=[''], width=200, title='ROI 5 Name')
roi_viewer_roi1_select_color = Select(value='blue', options=roi_colors, width=150, title='ROI 1 Color')
roi_viewer_roi2_select_color = Select(value='green', options=roi_colors, width=200, height=100, title='ROI 2 Color')
roi_viewer_roi3_select_color = Select(value='red', options=roi_colors, width=200, height=100, title='ROI 3 Color')
roi_viewer_roi4_select_color = Select(value='orange', options=roi_colors, width=200, height=100, title='ROI 4 Color')
roi_viewer_roi5_select_color = Select(value='lightgreen', options=roi_colors, width=200, height=100, title='ROI 5 Color')
roi_viewer_slice_select = Select(value='', options=[''], width=200, title='Slice: z = ')
roi_viewer_previous_slice = Button(label="<", button_type="primary", width=50)
roi_viewer_next_slice = Button(label=">", button_type="primary", width=50)
roi_viewer_flip_text = Div(text="<b>NOTE:</b> Axis flipping requires a figure reset (Click the circular double-arrow)",
                           width=1025)
roi_viewer_flip_x_axis_button = Button(label='Flip X-Axis', button_type='primary', width=100)
roi_viewer_flip_y_axis_button = Button(label='Flip Y-Axis', button_type='primary', width=100)
roi_viewer_plot_tv_button = Button(label='Plot TV', button_type='primary', width=100)

roi_viewer_mrn_select.on_change('value', roi_viewer_mrn_ticker)
roi_viewer_study_date_select.on_change('value', roi_viewer_study_date_ticker)
roi_viewer_uid_select.on_change('value', roi_viewer_uid_ticker)
roi_viewer_roi_select.on_change('value', roi_viewer_roi_ticker)
roi_viewer_roi2_select.on_change('value', roi_viewer_roi2_ticker)
roi_viewer_roi3_select.on_change('value', roi_viewer_roi3_ticker)
roi_viewer_roi4_select.on_change('value', roi_viewer_roi4_ticker)
roi_viewer_roi5_select.on_change('value', roi_viewer_roi5_ticker)
roi_viewer_roi1_select_color.on_change('value', roi_viewer_roi1_color_ticker)
roi_viewer_roi2_select_color.on_change('value', roi_viewer_roi2_color_ticker)
roi_viewer_roi3_select_color.on_change('value', roi_viewer_roi3_color_ticker)
roi_viewer_roi4_select_color.on_change('value', roi_viewer_roi4_color_ticker)
roi_viewer_roi5_select_color.on_change('value', roi_viewer_roi5_color_ticker)
roi_viewer_slice_select.on_change('value', roi_viewer_slice_ticker)
roi_viewer_previous_slice.on_click(roi_viewer_go_to_previous_slice)
roi_viewer_next_slice.on_click(roi_viewer_go_to_next_slice)
roi_viewer_flip_x_axis_button.on_click(roi_viewer_flip_x_axis)
roi_viewer_flip_y_axis_button.on_click(roi_viewer_flip_y_axis)
roi_viewer_plot_tv_button.on_click(roi_viewer_plot_tv)

roi_viewer = figure(plot_width=825, plot_height=600, logo=None, match_aspect=True,
                    tools="pan,wheel_zoom,reset,crosshair,save")
roi_viewer.xaxis.axis_label_text_font_size = PLOT_AXIS_LABEL_FONT_SIZE
roi_viewer.yaxis.axis_label_text_font_size = PLOT_AXIS_LABEL_FONT_SIZE
roi_viewer.xaxis.major_label_text_font_size = PLOT_AXIS_MAJOR_LABEL_FONT_SIZE
roi_viewer.yaxis.major_label_text_font_size = PLOT_AXIS_MAJOR_LABEL_FONT_SIZE
roi_viewer.min_border_left = min_border
roi_viewer.min_border_bottom = min_border
roi_viewer.y_range.flipped = True
roi_viewer_patch1 = roi_viewer.patch('x', 'y', source=source_roi_viewer, color='blue', alpha=0.5)
roi_viewer_patch2 = roi_viewer.patch('x', 'y', source=source_roi2_viewer, color='green', alpha=0.5)
roi_viewer_patch3 = roi_viewer.patch('x', 'y', source=source_roi3_viewer, color='red', alpha=0.5)
roi_viewer_patch4 = roi_viewer.patch('x', 'y', source=source_roi4_viewer, color='orange', alpha=0.5)
roi_viewer_patch5 = roi_viewer.patch('x', 'y', source=source_roi5_viewer, color='lightgreen', alpha=0.5)
roi_viewer.patch('x', 'y', source=source_tv, color='black', alpha=0.5)
roi_viewer.xaxis.axis_label = "Lateral DICOM Coordinate (mm)"
roi_viewer.yaxis.axis_label = "Anterior/Posterior DICOM Coordinate (mm)"
roi_viewer.on_event(events.MouseWheel, roi_viewer_wheel_event)
roi_viewer_scrolling = CheckboxGroup(labels=["Enable Slice Scrolling with Mouse Wheel"], active=[])

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Layout objects
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!
layout_query = column(row(custom_title_query_blue, Spacer(width=50), custom_title_query_red,
                          Spacer(width=50), query_button),
                      div_selector,
                      add_selector_row_button,
                      row(selector_row, Spacer(width=10), select_category1, select_category2, group_selector,
                          delete_selector_row_button, Spacer(width=10), selector_not_operator_checkbox),
                      selection_filter_data_table,
                      div_selector_end,
                      div_range,
                      add_range_row_button,
                      row(range_row, Spacer(width=10), select_category, text_min, text_max, group_range,
                          delete_range_row_button, Spacer(width=10), range_not_operator_checkbox),
                      range_filter_data_table,
                      div_range_end,
                      div_endpoint,
                      add_endpoint_row_button,
                      row(ep_row, Spacer(width=10), select_ep_type, ep_text_input, ep_units_in, delete_ep_row_button),
                      ep_data_table)

layout_dvhs = column(row(custom_title_dvhs_blue, Spacer(width=50), custom_title_dvhs_red),
                     row(radio_group_dose, radio_group_volume),
                     row(select_reviewed_mrn, select_reviewed_dvh, review_rx),
                     dvh_plots,
                     data_table_title,
                     data_table,
                     endpoint_table_title,
                     data_table_endpoints)

roi_viewer_layout = column(row(custom_title_roi_viewer_blue, Spacer(width=50), custom_title_roi_viewer_red),
                           row(roi_viewer_mrn_select, roi_viewer_study_date_select, roi_viewer_uid_select),
                           Div(text="<hr>", width=800),
                           row(roi_viewer_roi_select, roi_viewer_roi1_select_color, roi_viewer_slice_select,
                               roi_viewer_previous_slice, roi_viewer_next_slice),
                           Div(text="<hr>", width=800),
                           row(roi_viewer_roi2_select, roi_viewer_roi3_select,
                               roi_viewer_roi4_select, roi_viewer_roi5_select),
                           row(roi_viewer_roi2_select_color, roi_viewer_roi3_select_color,
                               roi_viewer_roi4_select_color, roi_viewer_roi5_select_color),
                           row(roi_viewer_flip_text),
                           row(roi_viewer_flip_x_axis_button, roi_viewer_flip_y_axis_button,
                               roi_viewer_plot_tv_button),
                           row(roi_viewer_scrolling),
                           row(roi_viewer),
                           row(Spacer(width=1000, height=100)))

query_tab = Panel(child=layout_query, title='Query')
dvh_tab = Panel(child=layout_dvhs, title='DVHs')
# rad_bio_tab = Panel(child=layout_rad_bio, title='Rad Bio')
roi_viewer_tab = Panel(child=roi_viewer_layout, title='ROI Viewer')
# planning_data_tab = Panel(child=layout_planning_data, title='Planning Data')
# trending_tab = Panel(child=layout_time_series, title='Time-Series')
# correlation_matrix_tab = Panel(child=layout_correlation_matrix, title='Correlation')
# correlation_tab = Panel(child=layout_regression, title='Regression')

tabs = Tabs(tabs=[query_tab, dvh_tab, roi_viewer_tab])

curdoc().add_root(tabs)
curdoc().title = "DVH Analytics"
