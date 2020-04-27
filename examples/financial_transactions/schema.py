# Schema automatically generated at 2020-04-26 21:15:34

import obj_tables


__all__ = [
    'Transaction',
]


class Transaction(obj_tables.Model):
    """ Stores transactions """

    amount = obj_tables.PositiveFloatAttribute()
    category = obj_tables.StringAttribute()
    date = obj_tables.DateAttribute()
    payee = obj_tables.StringAttribute()

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'amount',
            'category',
            'date',
            'payee',
        )
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transaction'
        description = 'Stores transactions'
