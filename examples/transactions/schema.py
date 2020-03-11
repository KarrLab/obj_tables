# Schema automatically generated at 2020-03-10 22:52:34

import obj_tables


__all__ = [
    'Transaction'
]


class Transaction(obj_tables.Model):
    """ Stores transactions """

    amount = obj_tables.PositiveFloatAttribute(verbose_name='None')
    category = obj_tables.StringAttribute(verbose_name='None')
    date = obj_tables.DateAttribute(verbose_name='None')
    payee = obj_tables.StringAttribute(verbose_name='None')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = ('amount', 'category', 'date', 'payee',)
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transaction'
        description = 'Stores transactions'
