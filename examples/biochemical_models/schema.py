# Schema automatically generated at 2019-10-10 23:09:02

import obj_tables


class Model(obj_tables.Model):
    """ Model """

    id = obj_tables.SlugAttribute(verbose_name='Id')
    name = obj_tables.StringAttribute(verbose_name='Name')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.column
        attribute_order = ('id', 'name',)
        verbose_name = 'Model'
        verbose_name_plural = 'Model'
        description = 'Model'


class Compound(obj_tables.Model):
    """ Compound """

    model = obj_tables.ManyToOneAttribute('Model', related_name='compounds', verbose_name='Model')
    id = obj_tables.SlugAttribute(verbose_name='Id')
    name = obj_tables.StringAttribute(verbose_name='Name')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')
    is_constant = obj_tables.BooleanAttribute(verbose_name='IsConstant')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('model', 'id', 'name', 'identifiers', 'is_constant',)
        verbose_name = 'Compound'
        verbose_name_plural = 'Compound'
        description = 'Compound'


class Reaction(obj_tables.Model):
    """ Reaction """

    model = obj_tables.ManyToOneAttribute('Model', related_name='reactions', verbose_name='Model')
    id = obj_tables.SlugAttribute(verbose_name='Id')
    name = obj_tables.StringAttribute(verbose_name='Name')
    identifiers = obj_tables.StringAttribute(verbose_name='Identifiers')
    equation = obj_tables.StringAttribute(verbose_name='Equation')
    is_reversible = obj_tables.BooleanAttribute(verbose_name='IsReversible')
    gene = obj_tables.StringAttribute(verbose_name='Gene')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('model', 'id', 'name', 'identifiers', 'equation', 'is_reversible', 'gene',)
        verbose_name = 'Reaction'
        verbose_name_plural = 'Reaction'
        description = 'Reaction'
