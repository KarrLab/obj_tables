import pkg_resources

with open(pkg_resources.resource_filename('obj_model', 'VERSION'), 'r') as file:
    __version__ = file.read().strip()
# :obj:`str`: version

# API
from .core import (Model, Attribute,
                   LiteralAttribute, NumericAttribute, EnumAttribute, BooleanAttribute,
                   FloatAttribute, PositiveFloatAttribute,
                   IntegerAttribute, PositiveIntegerAttribute, StringAttribute, LongStringAttribute,
                   RegexAttribute, SlugAttribute, UrlAttribute, DateAttribute, TimeAttribute,
                   DateTimeAttribute, RelatedAttribute, OneToOneAttribute, OneToManyAttribute,
                   ManyToOneAttribute, ManyToManyAttribute,
                   InvalidObjectSet, InvalidModel, InvalidObject, InvalidAttribute, Validator,
                   ObjModelWarning, SchemaWarning,
                   ModelSource, TabularOrientation,
                   get_models, get_model, excel_col_name,
                   ModelMerge)
from . import abstract
from . import expression
from . import io
from . import utils

# domain-specific attributes
from . import bio
from . import chem
from . import obj_math
from . import ontology
from . import units
