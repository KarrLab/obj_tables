import pkg_resources

with open(pkg_resources.resource_filename('obj_tables', 'VERSION'), 'r') as file:
    __version__ = file.read().strip()
# :obj:`str`: version

# API
from .core import (Model, Attribute,
                   LiteralAttribute, NumericAttribute, EnumAttribute, BooleanAttribute,
                   FloatAttribute, PositiveFloatAttribute,
                   IntegerAttribute, PositiveIntegerAttribute, StringAttribute, LongStringAttribute,
                   RegexAttribute, SlugAttribute, UrlAttribute, EmailAttribute, DateAttribute, TimeAttribute,
                   DateTimeAttribute, 
                   RelatedManager, OneToManyRelatedManager, ManyToOneRelatedManager, ManyToManyRelatedManager,
                   RelatedAttribute, OneToOneAttribute, OneToManyAttribute, ManyToOneAttribute, ManyToManyAttribute,
                   InvalidObjectSet, InvalidModel, InvalidObject, InvalidAttribute, Validator,
                   ObjTablesWarning, SchemaWarning,
                   ModelSource, TabularOrientation,
                   get_models, get_model, excel_col_name,
                   ModelMerge,
                   TOC_NAME, SBTAB_TOC_NAME, SCHEMA_NAME, SBTAB_SCHEMA_NAME)
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
