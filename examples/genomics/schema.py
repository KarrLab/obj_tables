# Schema automatically generated at 2020-05-14 17:19:04

import obj_tables


__all__ = [
    'Gene',
    'Location',
    'Transcript',
]


class Location(obj_tables.Model):
    chromosome = obj_tables.StringAttribute(verbose_name='Chromosome')
    five_prime = obj_tables.PositiveIntegerAttribute(primary=True, unique=True, verbose_name='5\'')
    three_prime = obj_tables.PositiveIntegerAttribute(verbose_name='3\'')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.multiple_cells
        attribute_order = (
            'chromosome',
            'five_prime',
            'three_prime',
        )
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'


class Transcript(obj_tables.Model):
    id = obj_tables.StringAttribute(primary=True, unique=True, verbose_name='Id')
    gene = obj_tables.ManyToOneAttribute('Gene', related_name='transcripts', verbose_name='Gene')
    location = obj_tables.ManyToOneAttribute('Location', related_name='transcripts', verbose_name='Location')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'id',
            'gene',
            'location',
        )
        verbose_name = 'Transcript'
        verbose_name_plural = 'Transcripts'


class Gene(obj_tables.Model):
    id = obj_tables.StringAttribute(primary=True, unique=True, verbose_name='Id')
    symbol = obj_tables.StringAttribute(verbose_name='Symbol')
    location = obj_tables.ManyToOneAttribute('Location', related_name='genes', verbose_name='Location')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'id',
            'symbol',
            'location',
        )
        verbose_name = 'Gene'
        verbose_name_plural = 'Genes'
