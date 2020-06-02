""" Schema for Luca Gerosa, Bart R B Haverkorn van Rijsewijk, Dimitris Christodoulou, Karl Kochanowski,
Thomas S B Schmidt, Elad Noor, Uwe Sauer. Pseudo-transition Analysis Identifies the Key Regulators of 
Dynamic Metabolic Adaptations From Steady-State Data. *Cell Systems* 1 (4), 270-282
(2015). DOI: `10.1016/j.cels.2015.09.008 <https://doi.org/10.1016/j.cels.2015.09.008>`_.

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2020-06-02
:Copyright: 2020, Karr Lab
:License: MIT
"""

import obj_tables
import obj_tables.chem


__all__ = [
    'Compartment',
    'Metabolite',
    'Reaction',
    'Reference',
]


class Compartment(obj_tables.Model):
    id = obj_tables.StringAttribute(primary=True, unique=True)
    name = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None)

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'id',
            'name',
        )
        verbose_name = 'Compartment'
        verbose_name_plural = 'Compartments'


class Metabolite(obj_tables.Model):
    id = obj_tables.StringAttribute(primary=True, unique=True)
    name = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None)
    formula = obj_tables.chem.ChemicalFormulaAttribute()

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'id',
            'name',
            'formula',
        )
        verbose_name = 'Metabolite'
        verbose_name_plural = 'Metabolites'


class Reaction(obj_tables.Model):
    id = obj_tables.StringAttribute(primary=True, unique=True)
    id_i_a_f1260 = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None, verbose_name='Id (iAF1260 [Ref1])')
    name = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None)
    equation = obj_tables.chem.ReactionEquationAttribute(species_cls=Metabolite, compartment_cls=Compartment)
    reversible = obj_tables.BooleanAttribute()
    subsystem = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None)
    ec_number = obj_tables.RegexAttribute(pattern='\d+\.\d+\.\d+\.\d+', none=True, default=None,
                                          default_cleaned_value=None, verbose_name='EC number')
    lower_bound = obj_tables.FloatAttribute()
    upper_bound = obj_tables.FloatAttribute()
    flux_acetate = obj_tables.FloatAttribute(verbose_name='Flux (Acetate media, mmol * gCDW^-1 * h^-1)')
    flux_acetate_uncertainty = obj_tables.FloatAttribute(verbose_name='Flux uncertainty (Acetate media, mmol * gCDW^-1 * h^-1)')
    flux_fructose = obj_tables.FloatAttribute(verbose_name='Flux (Fructose media, mmol * gCDW^-1 * h^-1)')
    flux_fructose_uncertainty = obj_tables.FloatAttribute(verbose_name='Flux uncertainty (Fructose media, mmol * gCDW^-1 * h^-1)')
    flux_galactose = obj_tables.FloatAttribute(verbose_name='Flux (Galactose media, mmol * gCDW^-1 * h^-1)')
    flux_galactose_uncertainty = obj_tables.FloatAttribute(verbose_name='Flux uncertainty (Galactose media, mmol * gCDW^-1 * h^-1)')
    flux_glucose = obj_tables.FloatAttribute(verbose_name='Flux (Glucose media, mmol * gCDW^-1 * h^-1)')
    flux_glucose_uncertainty = obj_tables.FloatAttribute(verbose_name='Flux uncertainty (Glucose media, mmol * gCDW^-1 * h^-1)')
    flux_glycerol = obj_tables.FloatAttribute(verbose_name='Flux (Glycerol media, mmol * gCDW^-1 * h^-1)')
    flux_glycerol_uncertainty = obj_tables.FloatAttribute(verbose_name='Flux uncertainty (Glycerol media, mmol * gCDW^-1 * h^-1)')
    flux_gluconate = obj_tables.FloatAttribute(verbose_name='Flux (Gluconate media, mmol * gCDW^-1 * h^-1)')
    flux_gluconate_uncertainty = obj_tables.FloatAttribute(verbose_name='Flux uncertainty (Gluconate media, mmol * gCDW^-1 * h^-1)')
    flux_pyruvate = obj_tables.FloatAttribute(verbose_name='Flux (Pyruvate media, mmol * gCDW^-1 * h^-1)')
    flux_pyruvate_uncertainty = obj_tables.FloatAttribute(verbose_name='Flux uncertainty (Pyruvate media, mmol * gCDW^-1 * h^-1)')
    flux_succinate = obj_tables.FloatAttribute(verbose_name='Flux (Succinate media, mmol * gCDW^-1 * h^-1)')
    flux_succinate_uncertainty = obj_tables.FloatAttribute(verbose_name='Flux uncertainty (Succinate media, mmol * gCDW^-1 * h^-1)')
    delta_g_acetate = obj_tables.FloatAttribute(verbose_name='ΔG (Acetate, kJ * mol^-1)')
    delta_g_acetate_uncertainty = obj_tables.FloatAttribute(verbose_name='ΔG uncertainty (Acetate, kJ * mol^-1)')
    delta_g_fructose = obj_tables.FloatAttribute(verbose_name='ΔG (Fructose, kJ * mol^-1)')
    delta_g_fructose_uncertainty = obj_tables.FloatAttribute(verbose_name='ΔG uncertainty (Fructose, kJ * mol^-1)')
    delta_g_galactose = obj_tables.FloatAttribute(verbose_name='ΔG (Galactose, kJ * mol^-1)')
    delta_g_galactose_uncertainty = obj_tables.FloatAttribute(verbose_name='ΔG uncertainty (Galactose, kJ * mol^-1)')
    delta_g_glucose = obj_tables.FloatAttribute(verbose_name='ΔG (Glucose, kJ * mol^-1)')
    delta_g_glucose_uncertainty = obj_tables.FloatAttribute(verbose_name='ΔG uncertainty (Glucose, kJ * mol^-1)')
    delta_g_glycerol = obj_tables.FloatAttribute(verbose_name='ΔG (Glycerol, kJ * mol^-1)')
    delta_g_glycerol_uncertainty = obj_tables.FloatAttribute(verbose_name='ΔG uncertainty (Glycerol, kJ * mol^-1)')
    delta_g_gluconate = obj_tables.FloatAttribute(verbose_name='ΔG (Gluconate, kJ * mol^-1)')
    delta_g_gluconate_uncertainty = obj_tables.FloatAttribute(verbose_name='ΔG uncertainty (Gluconate, kJ * mol^-1)')
    delta_g_pyruvate = obj_tables.FloatAttribute(verbose_name='ΔG (Pyruvate, kJ * mol^-1)')
    delta_g_pyruvate_uncertainty = obj_tables.FloatAttribute(verbose_name='ΔG uncertainty (Pyruvate, kJ * mol^-1)')
    delta_g_succinate = obj_tables.FloatAttribute(verbose_name='ΔG (Succinate, kJ * mol^-1)')
    delta_g_succinate_uncertainty = obj_tables.FloatAttribute(verbose_name='ΔG uncertainty (Succinate, kJ * mol^-1)')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'id',
            'id_i_a_f1260',
            'name',
            'equation',
            'reversible',
            'subsystem',
            'ec_number',
            'lower_bound',
            'upper_bound',
            'flux_acetate',
            'flux_acetate_uncertainty',
            'flux_fructose',
            'flux_fructose_uncertainty',
            'flux_galactose',
            'flux_galactose_uncertainty',
            'flux_glucose',
            'flux_glucose_uncertainty',
            'flux_glycerol',
            'flux_glycerol_uncertainty',
            'flux_gluconate',
            'flux_gluconate_uncertainty',
            'flux_pyruvate',
            'flux_pyruvate_uncertainty',
            'flux_succinate',
            'flux_succinate_uncertainty',
            'delta_g_acetate',
            'delta_g_acetate_uncertainty',
            'delta_g_fructose',
            'delta_g_fructose_uncertainty',
            'delta_g_galactose',
            'delta_g_galactose_uncertainty',
            'delta_g_glucose',
            'delta_g_glucose_uncertainty',
            'delta_g_glycerol',
            'delta_g_glycerol_uncertainty',
            'delta_g_gluconate',
            'delta_g_gluconate_uncertainty',
            'delta_g_pyruvate',
            'delta_g_pyruvate_uncertainty',
            'delta_g_succinate',
            'delta_g_succinate_uncertainty',
        )
        verbose_name = 'Reaction'
        verbose_name_plural = 'Reactions'


class Reference(obj_tables.Model):
    id = obj_tables.StringAttribute(primary=True, unique=True)
    title = obj_tables.LongStringAttribute()
    authors = obj_tables.LongStringAttribute()
    journal = obj_tables.StringAttribute()
    volume = obj_tables.PositiveIntegerAttribute()
    issue = obj_tables.PositiveIntegerAttribute()
    start_page = obj_tables.PositiveIntegerAttribute()
    end_page = obj_tables.PositiveIntegerAttribute()
    pubmed_id = obj_tables.PositiveIntegerAttribute(verbose_name='PubMed id')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'id',
            'title',
            'authors',
            'journal',
            'volume',
            'issue',
            'start_page',
            'end_page',
            'pubmed_id',
        )
        verbose_name = 'Reference'
        verbose_name_plural = 'References'
