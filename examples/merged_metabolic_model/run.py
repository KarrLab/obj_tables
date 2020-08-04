""" Merge kinetic and thermodynamic information about Escherichia coli metabolism

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2020-06-02
:Copyright: 2020, Karr Lab
:License: MIT
"""

from obj_tables.__main__ import get_schema_models
from matplotlib import pyplot
import math
import numpy
import obj_tables.io
import os
import wc_utils.workbook.io

DIRNAME = os.path.dirname(__file__)
DATA_FILENAME = os.path.join(DIRNAME, 'data.merged-comparison.xlsx')
PLOT_FILENAME = os.path.join(DIRNAME, 'delta-g-vs-k-cat.pdf')


def read_data():
    kinetics_dir = os.path.join(DIRNAME, '..', 'kinetic_metabolic_model')
    thermodynamics_dir = os.path.join(DIRNAME, '..', 'thermodynamic_metabolic_model')

    kinetics_schema_path = os.path.join(kinetics_dir, 'schema.py')
    thermodynamics_schema_path = os.path.join(thermodynamics_dir, 'schema.py')

    kinetics_data_path = os.path.join(kinetics_dir, 'data.xlsx')
    thermodynamics_data_path = os.path.join(thermodynamics_dir, 'data.xlsx')

    _, kinetics_schema, kinetics_models = get_schema_models(kinetics_schema_path)
    _, thermodynamics_schema, thermodynamics_models = get_schema_models(thermodynamics_schema_path)

    reader = obj_tables.io.Reader()
    kinetics_objs = reader.run(kinetics_data_path,
                               models=kinetics_models,
                               group_objects_by_model=True,
                               ignore_sheet_order=True,
                               ignore_attribute_order=True,
                               ignore_missing_attributes=True)
    thermodynamics_objs = reader.run(thermodynamics_data_path,
                                     models=thermodynamics_models,
                                     group_objects_by_model=True,
                                     ignore_sheet_order=True,
                                     ignore_attribute_order=True,
                                     ignore_missing_attributes=True)


def plot_data(data_filename=DATA_FILENAME, plot_filename=PLOT_FILENAME):
    data = wc_utils.workbook.io.read(data_filename)['!!Data']
    data = data[3:]

    rxn_ids = []
    k_cats = []
    k_cat_errs = []
    delta_gs = []
    delta_g_errs = []
    conditions = ['a. Acetate', 'b. Fructose', 'c. Galactose', 'd. Glucose', 'e. Glycerol', 'f. Gluconate', 'g. Pyruvate', 'h. Succinate']
    for datum in data:
        rxn_ids.append(datum[0])

        k_cats.append(datum[-20])
        k_cat_errs.append(datum[-19])

        delta_gs.append(datum[-16::2])
        delta_g_errs.append(datum[-15::2])

    k_cats = numpy.array(k_cats)
    k_cat_errs = numpy.array(k_cat_errs)
    delta_gs = numpy.array(delta_gs)
    delta_g_errs = numpy.array(delta_g_errs)

    pyplot.style.use('default')
    pyplot.rcParams['xtick.major.pad'] = '2'
    pyplot.rcParams['ytick.major.pad'] = '2'
    pyplot.rcParams['font.family'] = ['Arial', 'Helvetica', 'sans-serif']
    pyplot.rcParams['axes.unicode_minus'] = False
    fig, axes = pyplot.subplots(nrows=2, ncols=4,
                                gridspec_kw={
                                    'wspace': 0.35,
                                    'hspace': 0.45,
                                },
                                figsize=(6.5, 3.17),
                                )
    for i_condition, condition in enumerate(conditions):
        i_row = int(math.floor(i_condition / 4))
        i_col = i_condition % 4
        axis = axes[i_row][i_col]

        axis.scatter(k_cats, delta_gs[:, i_condition],
                     linewidths=1, marker='o', edgecolors='#1565f9', facecolors='none')
        axis.set_title(condition, fontdict={'fontsize': 8, 'fontweight': 'bold'})
        axis.set_xscale('log')
        axis.set_xlim(xmin=5e-3, xmax=2e4)
        axis.set_xticks([1e-2, 1e0, 1e2, 1e4])
        axis.set_ylim(ymin=-53, ymax=28)
        axis.set_yticks([-50, -25, 0, 25])
        for label in axis.get_xticklabels():
            label.set_fontsize(7)
        for label in axis.get_yticklabels():
            label.set_fontsize(7)
        axis.set_axisbelow(True)
        axis.grid(True, linewidth=0.5)

        axis.get_ylim()
    fig.savefig(plot_filename,
                transparent=True,
                bbox_inches='tight',
                pad_inches=0)
    pyplot.close(fig)


plot_data()
