import pkg_resources

from ._version import __version__
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
                   ModelSource, TableFormat,
                   get_models, get_model, excel_col_name,
                   ModelMerge,
                   TOC_TABLE_TYPE, TOC_SHEET_NAME,
                   SCHEMA_TABLE_TYPE, SCHEMA_SHEET_NAME)
from . import abstract
from . import expression
from . import grammar
from . import io
from . import utils

# domain-specific attributes
from . import bio
from . import chem
from . import obj_math
from . import ontology
from . import refs
from . import units
