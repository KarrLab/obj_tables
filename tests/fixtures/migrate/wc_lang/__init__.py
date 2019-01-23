import pkg_resources

with open(pkg_resources.resource_filename('tests.fixtures.migrate.wc_lang', 'VERSION'), 'r') as file:
    __version__ = file.read().strip()
# :obj:`str`: version

# API
'''
migration doesn't support relative imports
from .core import (TimeUnit, TaxonRank,
                   CompartmentBiologicalType, CompartmentPhysicalType, CompartmentGeometry,
                   SubmodelAlgorithm, SpeciesTypeType,
                   RandomDistribution,
                   RateLawDirection, RateLawType,
                   ParameterType, EvidenceType, ReferenceType,
                   Model, Taxon, Submodel, Compartment,
                   SpeciesType, Species, DistributionInitConcentration, DfbaObjective, DfbaObjectiveExpression,
                   Observable, ObservableExpression,
                   Function, FunctionExpression,
                   Reaction, SpeciesCoefficient, RateLaw, RateLawExpression,
                   DfbaNetSpecies, DfbaNetReaction, Parameter,
                   StopCondition, StopConditionExpression,
                   Evidence, DatabaseReference, Reference,
                   Validator)
'''
# these modules and packages not needed
# from . import config
# from . import io
# from . import sbml
# from . import transform
# from . import util
