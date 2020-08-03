""" Schema for Ali Khodayari & Costas D. Maranas. A genome-scale Escherichia coli kinetic metabolic
model k-ecoli457 satisfying flux data for multiple mutant strains. *Nature Communications* 7, 13806
(2016). DOI: `10.1038/ncomms13806 <https://doi.org/10.1038/ncomms13806>`_.

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2020-05-27
:Copyright: 2020, Karr Lab
:License: MIT
"""

import enum
import obj_tables
import obj_tables.chem


__all__ = [
    'Compartment',
    'Metabolite',
    'Reaction',
    'ImageType',
    'Kinetics',
    'Regulation',
    'RegulationType',
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


ImageType = enum.Enum('ImageType', type=str, names=[
    ('2D-image', '2D-image'),
])


class Kinetics(obj_tables.Model):
    value = obj_tables.RangeAttribute()
    molecule = obj_tables.StringAttribute()
    organism = obj_tables.StringAttribute()
    uniprot_ids = obj_tables.ListAttribute(verbose_name='UniProt ids')
    comments = obj_tables.LongStringAttribute()
    pubmed_ids = obj_tables.ListAttribute(verbose_name='PubMed ids')
    image = obj_tables.EnumAttribute(ImageType, none=True)

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.cell
        attribute_order = (
            'value',
            'molecule',
            'organism',
            'uniprot_ids',
            'comments',
            'pubmed_ids',
            'image',
        )
        verbose_name = 'Kinetics'
        verbose_name_plural = 'Kinetics'
        unique_together = (
            ('value', 'molecule', 'organism', 'uniprot_ids', 'comments', 'pubmed_ids', 'image'),
        )


class Reaction(obj_tables.Model):
    id = obj_tables.StringAttribute(primary=True, unique=True)
    id_i_a_f1260 = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None, verbose_name='Id (iAF1260 [Ref1])')
    name = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None)
    equation = obj_tables.chem.ReactionEquationAttribute(species_cls=Metabolite, compartment_cls=Compartment)
    reversible = obj_tables.BooleanAttribute()
    subsystem = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None)
    ec_number = obj_tables.RegexAttribute(pattern='\d+\.\d+\.\d+\.\d+', none=True, default=None,
                                          default_cleaned_value=None, verbose_name='EC number')
    gene_rule = obj_tables.StringAttribute(none=True, default=None, default_cleaned_value=None)
    obs_k_ms = obj_tables.ManyToManyAttribute(Kinetics, related_name='k_m_reactions',
                                              verbose_name='Measured Km (mM) [Ref2, Ref3]', cell_dialect='tsv')
    obs_range_k_ms = obj_tables.LongStringAttribute(verbose_name='Measured Km range (mM) [Ref2, Ref3]')
    est_range_k_ms = obj_tables.LongStringAttribute(verbose_name='Estimated Km range (mM)')
    obs_k_cats = obj_tables.ManyToManyAttribute(Kinetics, related_name='k_cat_reactions',
                                                verbose_name='Measured kcat (s^-1) [Ref2, Ref3]', cell_dialect='tsv')
    min_obs_for_k_cat = obj_tables.FloatAttribute(verbose_name='Minimum measured forward kcat (s^-1) [Ref2, Ref3]')
    max_obs_for_k_cat = obj_tables.FloatAttribute(verbose_name='Maximum measured forward kcat (s^-1) [Ref2, Ref3]')
    min_obs_back_k_cat = obj_tables.FloatAttribute(verbose_name='Minimum measured backward kcat (s^-1) [Ref2, Ref3]')
    max_obs_back_k_cat = obj_tables.FloatAttribute(verbose_name='Maximum measured backward kcat (s^-1) [Ref2, Ref3]')
    min_est_for_k_cat = obj_tables.FloatAttribute(verbose_name='Minimum estimated forward kcat (s^-1)')
    max_est_for_k_cat = obj_tables.FloatAttribute(verbose_name='Maximum estimated forward kcat (s^-1)')
    min_est_back_k_cat = obj_tables.FloatAttribute(verbose_name='Minimum estimated backward kcat (s^-1)')
    max_est_back_k_cat = obj_tables.FloatAttribute(verbose_name='Maximum estimated backward kcat (s^-1)')
    obs_k_cat_k_ms = obj_tables.ManyToManyAttribute(Kinetics, related_name='k_cat_k_m_reactions',
                                                    verbose_name='Measured kcat/Km (mM^-1 s^-1) [Ref2, Ref3]', cell_dialect='tsv')
    obs_k_is = obj_tables.ManyToManyAttribute(Kinetics, related_name='k_i_reactions',
                                              verbose_name='Measured Ki (mM) [Ref2, Ref3]', cell_dialect='tsv')
    coupled_to_biomass = obj_tables.BooleanAttribute()

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
            'gene_rule',
            'obs_k_ms',
            'obs_range_k_ms',
            'est_range_k_ms',
            'obs_k_cats',
            'min_obs_for_k_cat',
            'max_obs_for_k_cat',
            'min_obs_back_k_cat',
            'max_obs_back_k_cat',
            'min_est_for_k_cat',
            'max_est_for_k_cat',
            'min_est_back_k_cat',
            'max_est_back_k_cat',
            'obs_k_cat_k_ms',
            'obs_k_is',
            'coupled_to_biomass',
        )
        verbose_name = 'Reaction'
        verbose_name_plural = 'Reactions'


RegulationType = enum.Enum('RegulationType', type=str, names=[
    ('activation', 'activation'),
    ('competitive inhibition', 'competitive inhibition'),
    ('mixed inhibition', 'mixed inhibition'),
])


class Regulation(obj_tables.Model):
    reaction = obj_tables.ManyToOneAttribute(Reaction, related_name='regulations')
    regulator = obj_tables.ManyToOneAttribute(Metabolite, related_name='regulated_reactions')
    regulator_compartment = obj_tables.ManyToOneAttribute(Compartment, related_name='regulated_reactions')
    type = obj_tables.EnumAttribute(RegulationType, verbose_name='Type [Ref2, Ref3]')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'reaction',
            'regulator',
            'type',
        )
        verbose_name = 'Regulation'
        verbose_name_plural = 'Regulations'


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
