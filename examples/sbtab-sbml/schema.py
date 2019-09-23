# Schema automatically generated at 2019-09-23 11:05:07

import obj_tables


class Reaction(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    modifier = obj_tables.StringAttribute(verbose_name='Modifier')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    s_b_m_l_reaction_id = obj_tables.StringAttribute(verbose_name='SBML:reaction:id')
    reaction_formula = obj_tables.LongStringAttribute(verbose_name='ReactionFormula')
    location = obj_tables.StringAttribute(verbose_name='Location')
    enzyme = obj_tables.StringAttribute(verbose_name='Enzyme')
    model = obj_tables.StringAttribute(verbose_name='Model')
    pathway = obj_tables.StringAttribute(verbose_name='Pathway')
    subreaction_of = obj_tables.StringAttribute(verbose_name='SubreactionOf')
    is_complete = obj_tables.BooleanAttribute(verbose_name='IsComplete')
    is_reversible = obj_tables.BooleanAttribute(verbose_name='IsReversible')
    is_in_equilibrium = obj_tables.BooleanAttribute(verbose_name='IsInEquilibrium')
    is_exchange_reaction = obj_tables.BooleanAttribute(verbose_name='IsExchangeReaction')
    flux = obj_tables.FloatAttribute(verbose_name='Flux')
    is_non_enzymatic = obj_tables.BooleanAttribute(verbose_name='IsNonEnzymatic')
    kinetic_law = obj_tables.LongStringAttribute(verbose_name='KineticLaw')
    kinetic_law_name = obj_tables.StringAttribute(verbose_name='KineticLaw:Name')
    kinetic_law_formula = obj_tables.StringAttribute(verbose_name='KineticLaw:Formula')
    gene = obj_tables.StringAttribute(verbose_name='Gene')
    gene_symbol = obj_tables.StringAttribute(verbose_name='Gene:Symbol')
    operon = obj_tables.StringAttribute(verbose_name='Operon')
    enzyme_s_b_m_l_species_id = obj_tables.StringAttribute(verbose_name='Enzyme:SBML:species:id')
    enzyme_s_b_m_l_parameter_id = obj_tables.StringAttribute(verbose_name='Enzyme:SBML:parameter:id')
    build_reaction = obj_tables.BooleanAttribute(verbose_name='BuildReaction')
    build_enzyme = obj_tables.BooleanAttribute(verbose_name='BuildEnzyme')
    build_enzyme_production = obj_tables.BooleanAttribute(verbose_name='BuildEnzymeProduction')
    s_b_o_term = obj_tables.StringAttribute(verbose_name='SBOTerm')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')
    identifiers_kegg_reaction = obj_tables.StringAttribute(verbose_name='Identifiers:kegg.reaction')
    identifiers_obo_sbo = obj_tables.StringAttribute(verbose_name='Identifiers:obo.sbo')
    identifiers_ec_code = obj_tables.StringAttribute(verbose_name='Identifiers:ec-code')
    s_b_m_l_fbc_gene_association = obj_tables.LongStringAttribute(verbose_name='SBML:fbc:GeneAssociation')
    s_b_m_l_fbc_lower_bound = obj_tables.StringAttribute(verbose_name='SBML:fbc:LowerBound')
    s_b_m_l_fbc_upper_bound = obj_tables.StringAttribute(verbose_name='SBML:fbc:UpperBound')
    regulator = obj_tables.StringAttribute(verbose_name='Regulator')
    name_for_plots = obj_tables.StringAttribute(verbose_name='NameForPlots')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'modifier', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'i_d', 's_b_m_l_reaction_id', 'reaction_formula', 'location', 'enzyme', 'model', 'pathway', 'subreaction_of', 'is_complete', 'is_reversible', 'is_in_equilibrium', 'is_exchange_reaction', 'flux', 'is_non_enzymatic', 'kinetic_law', 'kinetic_law_name', 'kinetic_law_formula', 'gene', 'gene_symbol', 'operon', 'enzyme_s_b_m_l_species_id', 'enzyme_s_b_m_l_parameter_id', 'build_reaction', 'build_enzyme', 'build_enzyme_production', 's_b_o_term', 'identifiers', 'identifiers_kegg_reaction', 'identifiers_obo_sbo', 'identifiers_ec_code', 's_b_m_l_fbc_gene_association', 's_b_m_l_fbc_lower_bound', 's_b_m_l_fbc_upper_bound', 'regulator', 'name_for_plots',)
        verbose_name = 'Reaction'
        verbose_name_plural = 'Reaction'


class Compound(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    s_b_m_l_species_id = obj_tables.StringAttribute(verbose_name='SBML:species:id')
    s_b_m_l_speciestype_id = obj_tables.StringAttribute(verbose_name='SBML:speciestype:id')
    initial_value = obj_tables.FloatAttribute(verbose_name='InitialValue')
    initial_concentration = obj_tables.FloatAttribute(verbose_name='InitialConcentration')
    unit = obj_tables.StringAttribute(verbose_name='Unit')
    location = obj_tables.StringAttribute(verbose_name='Location')
    state = obj_tables.StringAttribute(verbose_name='State')
    compound_sum_formula = obj_tables.StringAttribute(verbose_name='CompoundSumFormula')
    structure_formula = obj_tables.StringAttribute(verbose_name='StructureFormula')
    charge = obj_tables.IntegerAttribute(verbose_name='Charge')
    mass = obj_tables.FloatAttribute(verbose_name='Mass')
    is_constant = obj_tables.BooleanAttribute(verbose_name='IsConstant')
    enzyme_role = obj_tables.StringAttribute(verbose_name='EnzymeRole')
    regulator_role = obj_tables.StringAttribute(verbose_name='RegulatorRole')
    s_b_o_term = obj_tables.StringAttribute(verbose_name='SBOTerm')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')
    identifiers_sbo_kegg = obj_tables.StringAttribute(verbose_name='Identifiers:sbo.kegg')
    identifiers_kegg_compound = obj_tables.StringAttribute(verbose_name='Identifiers:kegg.compound')
    identifiers_obo_chebi = obj_tables.StringAttribute(verbose_name='Identifiers:obo.chebi')
    s_b_m_l_fbc_chemical_formula = obj_tables.StringAttribute(verbose_name='SBML:fbc:ChemicalFormula')
    s_b_m_l_fbc_charge = obj_tables.FloatAttribute(verbose_name='SBML:fbc:Charge')
    has_only_substance_units = obj_tables.BooleanAttribute(verbose_name='HasOnlySubstanceUnits')
    name_for_plots = obj_tables.StringAttribute(verbose_name='NameForPlots')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'i_d', 's_b_m_l_species_id', 's_b_m_l_speciestype_id', 'initial_value', 'initial_concentration', 'unit', 'location', 'state', 'compound_sum_formula', 'structure_formula', 'charge', 'mass', 'is_constant', 'enzyme_role', 'regulator_role', 's_b_o_term', 'identifiers', 'identifiers_sbo_kegg', 'identifiers_kegg_compound', 'identifiers_obo_chebi', 's_b_m_l_fbc_chemical_formula', 's_b_m_l_fbc_charge', 'has_only_substance_units', 'name_for_plots',)
        verbose_name = 'Compound'
        verbose_name_plural = 'Compound'


class Enzyme(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    catalysed_reaction = obj_tables.StringAttribute(verbose_name='CatalysedReaction')
    kinetic_law = obj_tables.StringAttribute(verbose_name='KineticLaw')
    kinetic_law_name = obj_tables.StringAttribute(verbose_name='KineticLaw:Name')
    kinetic_law_formula = obj_tables.StringAttribute(verbose_name='KineticLaw:Formula')
    pathway = obj_tables.StringAttribute(verbose_name='Pathway')
    gene = obj_tables.StringAttribute(verbose_name='Gene')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'i_d', 'catalysed_reaction', 'kinetic_law', 'kinetic_law_name', 'kinetic_law_formula', 'pathway', 'gene', 'identifiers',)
        verbose_name = 'Enzyme'
        verbose_name_plural = 'Enzyme'


class Protein(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    gene = obj_tables.StringAttribute(verbose_name='Gene')
    mass = obj_tables.FloatAttribute(verbose_name='Mass')
    size = obj_tables.FloatAttribute(verbose_name='Size')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'i_d', 'gene', 'mass', 'size',)
        verbose_name = 'Protein'
        verbose_name_plural = 'Protein'


class Compartment(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    s_b_m_l_compartment_id = obj_tables.StringAttribute(verbose_name='SBML:compartment:id')
    outer_compartment = obj_tables.StringAttribute(verbose_name='OuterCompartment')
    outer_compartment_s_b_m_l_compartment_id = obj_tables.StringAttribute(verbose_name='OuterCompartment:SBML:compartment:id')
    size = obj_tables.FloatAttribute(verbose_name='Size')
    unit = obj_tables.StringAttribute(verbose_name='Unit')
    s_b_o_term = obj_tables.StringAttribute(verbose_name='SBOTerm')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')
    identifiers_sbo_go = obj_tables.StringAttribute(verbose_name='Identifiers:sbo.go')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'i_d', 's_b_m_l_compartment_id', 'outer_compartment', 'outer_compartment_s_b_m_l_compartment_id', 'size', 'unit', 's_b_o_term', 'identifiers', 'identifiers_sbo_go',)
        verbose_name = 'Compartment'
        verbose_name_plural = 'Compartment'


class Quantity(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    quantity = obj_tables.StringAttribute(verbose_name='Quantity')
    reference = obj_tables.StringAttribute(verbose_name='Reference')
    quantity_name = obj_tables.StringAttribute(verbose_name='QuantityName')
    quantity_type = obj_tables.StringAttribute(verbose_name='QuantityType')
    value = obj_tables.FloatAttribute(verbose_name='Value')
    mean = obj_tables.FloatAttribute(verbose_name='Mean')
    std = obj_tables.FloatAttribute(verbose_name='Std')
    min = obj_tables.FloatAttribute(verbose_name='Min')
    max = obj_tables.FloatAttribute(verbose_name='Max')
    median = obj_tables.FloatAttribute(verbose_name='Median')
    geometric_mean = obj_tables.FloatAttribute(verbose_name='GeometricMean')
    sign = obj_tables.EnumAttribute(['+', '-', '0'], default='0', verbose_name='Sign')
    prob_dist = obj_tables.StringAttribute(verbose_name='ProbDist')
    s_b_m_l_parameter_id = obj_tables.StringAttribute(verbose_name='SBML:parameter:id')
    unit = obj_tables.StringAttribute(verbose_name='Unit')
    scale = obj_tables.StringAttribute(verbose_name='Scale')
    time = obj_tables.FloatAttribute(verbose_name='Time')
    time_point = obj_tables.StringAttribute(verbose_name='TimePoint')
    condition = obj_tables.StringAttribute(verbose_name='Condition')
    p_h = obj_tables.FloatAttribute(verbose_name='pH')
    temperature = obj_tables.FloatAttribute(verbose_name='Temperature')
    location = obj_tables.StringAttribute(verbose_name='Location')
    location_s_b_m_l_compartment_id = obj_tables.StringAttribute(verbose_name='Location:SBML:compartment:id')
    compound = obj_tables.StringAttribute(verbose_name='Compound')
    compound_s_b_m_l_species_id = obj_tables.StringAttribute(verbose_name='Compound:SBML:species:id')
    reaction = obj_tables.StringAttribute(verbose_name='Reaction')
    reaction_s_b_m_l_reaction_id = obj_tables.StringAttribute(verbose_name='Reaction:SBML:reaction:id')
    enyzme = obj_tables.StringAttribute(verbose_name='Enyzme')
    enyzme_s_b_m_l_species_id = obj_tables.StringAttribute(verbose_name='Enyzme:SBML:species:id')
    enyzme_s_b_m_l_parameter_id = obj_tables.StringAttribute(verbose_name='Enyzme:SBML:parameter:id')
    gene = obj_tables.StringAttribute(verbose_name='Gene')
    organism = obj_tables.StringAttribute(verbose_name='Organism')
    provenance = obj_tables.StringAttribute(verbose_name='Provenance')
    s_b_o_term = obj_tables.StringAttribute(verbose_name='SBOTerm')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')
    identifiers_kegg_reaction = obj_tables.StringAttribute(verbose_name='Identifiers:kegg.reaction')
    identifiers_kegg_compound = obj_tables.StringAttribute(verbose_name='Identifiers:kegg.compound')
    identifiers_obo_chebi = obj_tables.StringAttribute(verbose_name='Identifiers:obo.chebi')
    reaction_identifiers_kegg_reaction = obj_tables.StringAttribute(verbose_name='Reaction:Identifiers:kegg.reaction')
    compound_identifiers_kegg_compound = obj_tables.StringAttribute(verbose_name='Compound:Identifiers:kegg.compound')
    biological_element = obj_tables.StringAttribute(verbose_name='BiologicalElement')
    mathematical_type = obj_tables.StringAttribute(verbose_name='MathematicalType')
    data_geometric_std = obj_tables.FloatAttribute(verbose_name='DataGeometricStd')
    prior_median = obj_tables.FloatAttribute(verbose_name='PriorMedian')
    prior_std = obj_tables.FloatAttribute(verbose_name='PriorStd')
    prior_geometric_std = obj_tables.FloatAttribute(verbose_name='PriorGeometricStd')
    lower_bound = obj_tables.FloatAttribute(verbose_name='LowerBound')
    upper_bound = obj_tables.FloatAttribute(verbose_name='UpperBound')
    data_std = obj_tables.FloatAttribute(verbose_name='DataStd')
    physical_type = obj_tables.StringAttribute(verbose_name='PhysicalType')
    dependence = obj_tables.StringAttribute(verbose_name='Dependence')
    use_as_prior_information = obj_tables.BooleanAttribute(verbose_name='UseAsPriorInformation')
    s_b_m_l_element = obj_tables.StringAttribute(verbose_name='SBMLElement')
    abbreviation = obj_tables.StringAttribute(verbose_name='Abbreviation')
    matrix_info = obj_tables.StringAttribute(verbose_name='MatrixInfo')
    s_b_o_equilibrium_constant = obj_tables.FloatAttribute(verbose_name='SBO:equilibrium_constant')
    s_b_o_identifiers_obo_sbo = obj_tables.StringAttribute(verbose_name='SBO:Identifiers:obo.sbo')
    s_b_o_concentration = obj_tables.FloatAttribute(verbose_name='SBO:concentration')
    s_b_o_concentration_[m_m_log10]_median = obj_tables.FloatAttribute(verbose_name='SBO:concentration [mM:Log10]:Median')
    value_type = obj_tables.StringAttribute(verbose_name='ValueType')
    concentration_min = obj_tables.FloatAttribute(verbose_name='Concentration:Min')
    concentration_max = obj_tables.FloatAttribute(verbose_name='Concentration:Max')
    parameter_s_b_m_l_parameter_id = obj_tables.StringAttribute(verbose_name='Parameter:SBML:parameter:id')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'i_d', 'quantity', 'reference', 'quantity_name', 'quantity_type', 'value', 'mean', 'std', 'min', 'max', 'median', 'geometric_mean', 'sign', 'prob_dist', 's_b_m_l_parameter_id', 'unit', 'scale', 'time', 'time_point', 'condition', 'p_h', 'temperature', 'location', 'location_s_b_m_l_compartment_id', 'compound', 'compound_s_b_m_l_species_id', 'reaction', 'reaction_s_b_m_l_reaction_id', 'enyzme', 'enyzme_s_b_m_l_species_id', 'enyzme_s_b_m_l_parameter_id', 'gene', 'organism', 'provenance', 's_b_o_term', 'identifiers', 'identifiers_kegg_reaction', 'identifiers_kegg_compound', 'identifiers_obo_chebi', 'reaction_identifiers_kegg_reaction', 'compound_identifiers_kegg_compound', 'biological_element', 'mathematical_type', 'data_geometric_std', 'prior_median', 'prior_std', 'prior_geometric_std', 'lower_bound', 'upper_bound', 'data_std', 'physical_type', 'dependence', 'use_as_prior_information', 's_b_m_l_element', 'abbreviation', 'matrix_info', 's_b_o_equilibrium_constant', 's_b_o_identifiers_obo_sbo', 's_b_o_concentration', 's_b_o_concentration_[m_m_log10]_median', 'value_type', 'concentration_min', 'concentration_max', 'parameter_s_b_m_l_parameter_id',)
        verbose_name = 'Quantity'
        verbose_name_plural = 'Quantity'


class Regulator(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    state = obj_tables.StringAttribute(verbose_name='State')
    target_gene = obj_tables.StringAttribute(verbose_name='TargetGene')
    target_operon = obj_tables.StringAttribute(verbose_name='TargetOperon')
    target_promoter = obj_tables.StringAttribute(verbose_name='TargetPromoter')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'i_d', 'state', 'target_gene', 'target_operon', 'target_promoter', 'identifiers',)
        verbose_name = 'Regulator'
        verbose_name_plural = 'Regulator'


class Gene(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    locus_name = obj_tables.StringAttribute(verbose_name='LocusName')
    gene_product = obj_tables.StringAttribute(verbose_name='GeneProduct')
    gene_product_s_b_m_l_species_id = obj_tables.StringAttribute(verbose_name='GeneProduct:SBML:species:id')
    operon = obj_tables.StringAttribute(verbose_name='Operon')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')
    s_b_m_l_fbc_i_d = obj_tables.StringAttribute(verbose_name='SBML:fbc:ID')
    s_b_m_l_fbc_name = obj_tables.StringAttribute(verbose_name='SBML:fbc:Name')
    s_b_m_l_fbc_gene_product = obj_tables.BooleanAttribute(verbose_name='SBML:fbc:GeneProduct')
    s_b_m_l_fbc_gene_association = obj_tables.BooleanAttribute(verbose_name='SBML:fbc:GeneAssociation')
    s_b_m_l_fbc_label = obj_tables.StringAttribute(verbose_name='SBML:fbc:Label')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'i_d', 'locus_name', 'gene_product', 'gene_product_s_b_m_l_species_id', 'operon', 'identifiers', 's_b_m_l_fbc_i_d', 's_b_m_l_fbc_name', 's_b_m_l_fbc_gene_product', 's_b_m_l_fbc_gene_association', 's_b_m_l_fbc_label',)
        verbose_name = 'Gene'
        verbose_name_plural = 'Gene'


class Relation(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    from = obj_tables.StringAttribute(verbose_name='From')
    to = obj_tables.StringAttribute(verbose_name='To')
    is_symmetric = obj_tables.BooleanAttribute(verbose_name='IsSymmetric')
    value_quantity_type = obj_tables.FloatAttribute(verbose_name='Value:QuantityType')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'i_d', 'from', 'to', 'is_symmetric', 'value_quantity_type',)
        verbose_name = 'Relation'
        verbose_name_plural = 'Relation'


class Definition(obj_tables.Model):
    component_name = obj_tables.StringAttribute(verbose_name='ComponentName')
    component_type = obj_tables.StringAttribute(verbose_name='ComponentType')
    is_part_of = obj_tables.StringAttribute(verbose_name='IsPartOf')
    format = obj_tables.StringAttribute(verbose_name='Format')
    description = obj_tables.StringAttribute(verbose_name='Description')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('component_name', 'component_type', 'is_part_of', 'format', 'description',)
        verbose_name = 'Definition'
        verbose_name_plural = 'Definition'


class QuantityMatrix(obj_tables.Model):
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    reference_name = obj_tables.StringAttribute(verbose_name='ReferenceName')
    reference_pub_med = obj_tables.StringAttribute(verbose_name='ReferencePubMed')
    reference_d_o_i = obj_tables.StringAttribute(verbose_name='ReferenceDOI')
    description = obj_tables.StringAttribute(verbose_name='Description')
    name = obj_tables.StringAttribute(verbose_name='Name')
    miriam_annotations = obj_tables.StringAttribute(verbose_name='MiriamAnnotations')
    type = obj_tables.StringAttribute(verbose_name='Type')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')
    time = obj_tables.FloatAttribute(verbose_name='Time')
    time_point = obj_tables.StringAttribute(verbose_name='TimePoint')
    _table_column = obj_tables.StringAttribute(verbose_name='>Table:Column')
    _document_table_column = obj_tables.StringAttribute(verbose_name='>Document:Table:Column')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    quantity_name = obj_tables.StringAttribute(verbose_name='QuantityName')
    quantity_type = obj_tables.StringAttribute(verbose_name='QuantityType')
    value = obj_tables.FloatAttribute(verbose_name='Value')
    mean = obj_tables.FloatAttribute(verbose_name='Mean')
    std = obj_tables.FloatAttribute(verbose_name='Std')
    min = obj_tables.FloatAttribute(verbose_name='Min')
    max = obj_tables.FloatAttribute(verbose_name='Max')
    median = obj_tables.FloatAttribute(verbose_name='Median')
    geometric_mean = obj_tables.FloatAttribute(verbose_name='GeometricMean')
    sign = obj_tables.EnumAttribute(['+', '-', '0'], default='0', verbose_name='Sign')
    prob_dist = obj_tables.StringAttribute(verbose_name='ProbDist')
    s_b_m_l_parameter_id = obj_tables.StringAttribute(verbose_name='SBML:parameter:id')
    unit = obj_tables.StringAttribute(verbose_name='Unit')
    scale = obj_tables.StringAttribute(verbose_name='Scale')
    compound = obj_tables.StringAttribute(verbose_name='Compound')
    compound_s_b_m_l_species_id = obj_tables.StringAttribute(verbose_name='Compound:SBML:species:id')
    reaction = obj_tables.StringAttribute(verbose_name='Reaction')
    reaction_s_b_m_l_reaction_id = obj_tables.StringAttribute(verbose_name='Reaction:SBML:reaction:id')
    enyzme = obj_tables.StringAttribute(verbose_name='Enyzme')
    enyzme_s_b_m_l_species_id = obj_tables.StringAttribute(verbose_name='Enyzme:SBML:species:id')
    enyzme_s_b_m_l_parameter_id = obj_tables.StringAttribute(verbose_name='Enyzme:SBML:parameter:id')
    protein = obj_tables.StringAttribute(verbose_name='Protein')
    protein_s_b_m_l_species_id = obj_tables.StringAttribute(verbose_name='Protein:SBML:species:id')
    gene = obj_tables.StringAttribute(verbose_name='Gene')
    identifiers_obo_chebi = obj_tables.StringAttribute(verbose_name='Identifiers:obo.chebi')
    _concentration_glucose = obj_tables.FloatAttribute(verbose_name='>Concentration:Glucose')
    _concentration_fructose = obj_tables.FloatAttribute(verbose_name='>Concentration:Fructose')
    _sample_t0 = obj_tables.FloatAttribute(verbose_name='>Sample:t0')
    _sample_t1 = obj_tables.FloatAttribute(verbose_name='>Sample:t1')
    _t_p_t0_mean = obj_tables.FloatAttribute(verbose_name='>TP:t0:mean')
    _t_p_t0_std = obj_tables.FloatAttribute(verbose_name='>TP:t0:std')
    _t_p_t1_mean = obj_tables.FloatAttribute(verbose_name='>TP:t1:mean')
    _t_p_t1_std = obj_tables.FloatAttribute(verbose_name='>TP:t1:std')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('comment', 'reference_name', 'reference_pub_med', 'reference_d_o_i', 'description', 'name', 'miriam_annotations', 'type', 'symbol', 'position_x', 'position_y', 'time', 'time_point', '_table_column', '_document_table_column', 'i_d', 'quantity_name', 'quantity_type', 'value', 'mean', 'std', 'min', 'max', 'median', 'geometric_mean', 'sign', 'prob_dist', 's_b_m_l_parameter_id', 'unit', 'scale', 'compound', 'compound_s_b_m_l_species_id', 'reaction', 'reaction_s_b_m_l_reaction_id', 'enyzme', 'enyzme_s_b_m_l_species_id', 'enyzme_s_b_m_l_parameter_id', 'protein', 'protein_s_b_m_l_species_id', 'gene', 'identifiers_obo_chebi', '_concentration_glucose', '_concentration_fructose', '_sample_t0', '_sample_t1', '_t_p_t0_mean', '_t_p_t0_std', '_t_p_t1_mean', '_t_p_t1_std',)
        verbose_name = 'QuantityMatrix'
        verbose_name_plural = 'QuantityMatrix'


class StoichiometricMatrix(obj_tables.Model):
    reaction_i_d = obj_tables.StringAttribute(verbose_name='ReactionID')
    stoichiometry = obj_tables.StringAttribute(verbose_name='Stoichiometry')
    substrate = obj_tables.StringAttribute(verbose_name='Substrate')
    product = obj_tables.StringAttribute(verbose_name='Product')
    location = obj_tables.StringAttribute(verbose_name='Location')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('reaction_i_d', 'stoichiometry', 'substrate', 'product', 'location',)
        verbose_name = 'StoichiometricMatrix'
        verbose_name_plural = 'StoichiometricMatrix'


class Measurement(obj_tables.Model):
    sample = obj_tables.StringAttribute(verbose_name='Sample')
    time = obj_tables.StringAttribute(verbose_name='Time')
    unit = obj_tables.StringAttribute(verbose_name='Unit')
    value_type = obj_tables.StringAttribute(verbose_name='ValueType')
    description = obj_tables.StringAttribute(verbose_name='Description')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('sample', 'time', 'unit', 'value_type', 'description',)
        verbose_name = 'Measurement'
        verbose_name_plural = 'Measurement'


class QuantityInfo(obj_tables.Model):
    quantity_type = obj_tables.StringAttribute(verbose_name='QuantityType')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    unit = obj_tables.StringAttribute(verbose_name='Unit')
    constant = obj_tables.StringAttribute(verbose_name='Constant')
    element = obj_tables.StringAttribute(verbose_name='Element')
    related_element = obj_tables.StringAttribute(verbose_name='RelatedElement')
    scaling = obj_tables.StringAttribute(verbose_name='Scaling')
    dependence = obj_tables.StringAttribute(verbose_name='Dependence')
    prior_median = obj_tables.FloatAttribute(verbose_name='PriorMedian')
    prior_std = obj_tables.FloatAttribute(verbose_name='PriorStd')
    lower_bound = obj_tables.FloatAttribute(verbose_name='LowerBound')
    upper_bound = obj_tables.FloatAttribute(verbose_name='UpperBound')
    error_std = obj_tables.FloatAttribute(verbose_name='ErrorStd')
    data_std = obj_tables.FloatAttribute(verbose_name='DataStd')
    s_b_m_l_element = obj_tables.StringAttribute(verbose_name='SBMLElement')
    s_b_m_l_element_type = obj_tables.StringAttribute(verbose_name='SBMLElementType')
    abbreviation = obj_tables.StringAttribute(verbose_name='Abbreviation')
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    matrix_info = obj_tables.StringAttribute(verbose_name='MatrixInfo')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('quantity_type', 'symbol', 'unit', 'constant', 'element', 'related_element', 'scaling', 'dependence', 'prior_median', 'prior_std', 'lower_bound', 'upper_bound', 'error_std', 'data_std', 's_b_m_l_element', 's_b_m_l_element_type', 'abbreviation', 'i_d', 'matrix_info',)
        verbose_name = 'QuantityInfo'
        verbose_name_plural = 'QuantityInfo'


class PbConfig(obj_tables.Model):
    option = obj_tables.StringAttribute(verbose_name='Option')
    value = obj_tables.StringAttribute(verbose_name='Value')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('option', 'value',)
        verbose_name = 'PbConfig'
        verbose_name_plural = 'PbConfig'


class rxnconContingencyList(obj_tables.Model):
    u_i_d_contingency = obj_tables.IntegerAttribute(verbose_name='UID:Contingency')
    target = obj_tables.StringAttribute(verbose_name='Target')
    contingency = obj_tables.StringAttribute(verbose_name='Contingency')
    modifier = obj_tables.StringAttribute(verbose_name='Modifier')
    reference_identifiers_pubmed = obj_tables.StringAttribute(verbose_name='Reference:Identifiers:pubmed')
    quality = obj_tables.StringAttribute(verbose_name='Quality')
    comment = obj_tables.StringAttribute(verbose_name='Comment')
    internal_complex_i_d = obj_tables.StringAttribute(verbose_name='InternalComplexID')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('u_i_d_contingency', 'target', 'contingency', 'modifier', 'reference_identifiers_pubmed', 'quality', 'comment', 'internal_complex_i_d',)
        verbose_name = 'rxnconContingencyList'
        verbose_name_plural = 'rxnconContingencyList'


class rxnconReactionList(obj_tables.Model):
    i_d = obj_tables.IntegerAttribute(verbose_name='ID')
    u_i_d_reaction = obj_tables.StringAttribute(verbose_name='UID:Reaction')
    component_a_name = obj_tables.StringAttribute(verbose_name='ComponentA:Name')
    component_a_domain = obj_tables.StringAttribute(verbose_name='ComponentA:Domain')
    component_a_residue = obj_tables.StringAttribute(verbose_name='ComponentA:Residue')
    reaction = obj_tables.StringAttribute(verbose_name='Reaction')
    component_b_name = obj_tables.StringAttribute(verbose_name='ComponentB:Name')
    component_b_domain = obj_tables.StringAttribute(verbose_name='ComponentB:Domain')
    component_b_residue = obj_tables.StringAttribute(verbose_name='ComponentB:Residue')
    quality = obj_tables.StringAttribute(verbose_name='Quality')
    literature_identifiers_pubmed = obj_tables.StringAttribute(verbose_name='Literature:Identifiers:pubmed')
    comment = obj_tables.StringAttribute(verbose_name='Comment')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('i_d', 'u_i_d_reaction', 'component_a_name', 'component_a_domain', 'component_a_residue', 'reaction', 'component_b_name', 'component_b_domain', 'component_b_residue', 'quality', 'literature_identifiers_pubmed', 'comment',)
        verbose_name = 'rxnconReactionList'
        verbose_name_plural = 'rxnconReactionList'


class FbcObjective(obj_tables.Model):
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    name = obj_tables.StringAttribute(verbose_name='Name')
    s_b_m_l_fbc_type = obj_tables.StringAttribute(verbose_name='SBML:fbc:type')
    s_b_m_l_fbc_active = obj_tables.BooleanAttribute(verbose_name='SBML:fbc:active')
    s_b_m_l_fbc_objective = obj_tables.StringAttribute(verbose_name='SBML:fbc:objective')
    s_b_m_l_fbc_reaction = obj_tables.StringAttribute(verbose_name='SBML:fbc:reaction')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('i_d', 'name', 's_b_m_l_fbc_type', 's_b_m_l_fbc_active', 's_b_m_l_fbc_objective', 's_b_m_l_fbc_reaction',)
        verbose_name = 'FbcObjective'
        verbose_name_plural = 'FbcObjective'


class Layout(obj_tables.Model):
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    name = obj_tables.StringAttribute(verbose_name='Name')
    s_b_m_l_layout_model_entity = obj_tables.StringAttribute(verbose_name='SBML:layout:modelEntity')
    s_b_m_l_layout_compartment_id = obj_tables.StringAttribute(verbose_name='SBML:layout:compartment:id')
    s_b_m_l_layout_reaction_id = obj_tables.StringAttribute(verbose_name='SBML:layout:reaction:id')
    s_b_m_l_layout_species_id = obj_tables.StringAttribute(verbose_name='SBML:layout:species:id')
    s_b_m_l_layout_curve_segment = obj_tables.StringAttribute(verbose_name='SBML:layout:curveSegment')
    s_b_m_l_layout_x = obj_tables.FloatAttribute(verbose_name='SBML:layout:X')
    s_b_m_l_layout_y = obj_tables.FloatAttribute(verbose_name='SBML:layout:Y')
    s_b_m_l_layout_width = obj_tables.FloatAttribute(verbose_name='SBML:layout:width')
    s_b_m_l_layout_height = obj_tables.FloatAttribute(verbose_name='SBML:layout:height')
    s_b_m_l_layout_text = obj_tables.StringAttribute(verbose_name='SBML:layout:text')
    s_b_m_l_layout_species_role = obj_tables.StringAttribute(verbose_name='SBML:layout:speciesRole')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('i_d', 'name', 's_b_m_l_layout_model_entity', 's_b_m_l_layout_compartment_id', 's_b_m_l_layout_reaction_id', 's_b_m_l_layout_species_id', 's_b_m_l_layout_curve_segment', 's_b_m_l_layout_x', 's_b_m_l_layout_y', 's_b_m_l_layout_width', 's_b_m_l_layout_height', 's_b_m_l_layout_text', 's_b_m_l_layout_species_role',)
        verbose_name = 'Layout'
        verbose_name_plural = 'Layout'


class ReactionStoichiometry(obj_tables.Model):
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    stoichiometry = obj_tables.StringAttribute(verbose_name='Stoichiometry')
    substrate = obj_tables.StringAttribute(verbose_name='Substrate')
    product = obj_tables.StringAttribute(verbose_name='Product')
    location = obj_tables.StringAttribute(verbose_name='Location')
    reaction = obj_tables.StringAttribute(verbose_name='Reaction')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('i_d', 'stoichiometry', 'substrate', 'product', 'location', 'reaction',)
        verbose_name = 'ReactionStoichiometry'
        verbose_name_plural = 'ReactionStoichiometry'


class SparseMatrixOrdered(obj_tables.Model):
    row_number = obj_tables.IntegerAttribute(verbose_name='RowNumber')
    column_number = obj_tables.IntegerAttribute(verbose_name='ColumnNumber')
    value = obj_tables.FloatAttribute(verbose_name='Value')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('row_number', 'column_number', 'value',)
        verbose_name = 'SparseMatrixOrdered'
        verbose_name_plural = 'SparseMatrixOrdered'


class SparseMatrix(obj_tables.Model):
    row_i_d = obj_tables.StringAttribute(verbose_name='RowID')
    column_i_d = obj_tables.StringAttribute(verbose_name='ColumnID')
    value = obj_tables.FloatAttribute(verbose_name='Value')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('row_i_d', 'column_i_d', 'value',)
        verbose_name = 'SparseMatrix'
        verbose_name_plural = 'SparseMatrix'


class SparseMatrixRow(obj_tables.Model):
    row_i_d = obj_tables.StringAttribute(verbose_name='RowID')
    row_string = obj_tables.StringAttribute(verbose_name='RowString')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('row_i_d', 'row_string',)
        verbose_name = 'SparseMatrixRow'
        verbose_name_plural = 'SparseMatrixRow'


class SparseMatrixColumn(obj_tables.Model):
    column_i_d = obj_tables.StringAttribute(verbose_name='ColumnID')
    column_string = obj_tables.StringAttribute(verbose_name='ColumnString')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('column_i_d', 'column_string',)
        verbose_name = 'SparseMatrixColumn'
        verbose_name_plural = 'SparseMatrixColumn'


class Relationship(obj_tables.Model):
    i_d = obj_tables.StringAttribute(verbose_name='ID')
    from = obj_tables.StringAttribute(verbose_name='From')
    to = obj_tables.StringAttribute(verbose_name='To')
    value = obj_tables.IntegerAttribute(verbose_name='Value')
    is_symmetric = obj_tables.BooleanAttribute(verbose_name='IsSymmetric')
    sign = obj_tables.EnumAttribute(['+', '-', '0'], default='0', verbose_name='Sign')
    relation = obj_tables.StringAttribute(verbose_name='Relation')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('i_d', 'from', 'to', 'value', 'is_symmetric', 'sign', 'relation',)
        verbose_name = 'Relationship'
        verbose_name_plural = 'Relationship'


class Position(obj_tables.Model):
    element = obj_tables.StringAttribute(verbose_name='Element')
    position_x = obj_tables.FloatAttribute(verbose_name='PositionX')
    position_y = obj_tables.FloatAttribute(verbose_name='PositionY')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('element', 'position_x', 'position_y',)
        verbose_name = 'Position'
        verbose_name_plural = 'Position'
