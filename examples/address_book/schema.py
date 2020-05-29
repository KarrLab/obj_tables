# Schema automatically generated at 2020-05-29 00:18:50

import obj_tables


__all__ = [
    'Address',
    'Company',
    'Person',
]


class Company(obj_tables.Model):
    name = obj_tables.StringAttribute(primary=True, unique=True, verbose_name='Name')
    url = obj_tables.UrlAttribute(verbose_name='URL')
    address = obj_tables.OneToOneAttribute('Address', related_name='company', verbose_name='Address')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.column
        attribute_order = (
            'name',
            'url',
            'address',
        )
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'


class Person(obj_tables.Model):
    name = obj_tables.StringAttribute(primary=True, unique=True, verbose_name='Name')
    type = obj_tables.EnumAttribute(['family', 'friend', 'business'], verbose_name='Type')
    company = obj_tables.ManyToOneAttribute('Company', related_name='employees', verbose_name='Company')
    email_address = obj_tables.EmailAttribute(verbose_name='Email address')
    phone_number = obj_tables.StringAttribute(verbose_name='Phone number')
    address = obj_tables.OneToOneAttribute('Address', related_name='person', verbose_name='Address')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'name',
            'type',
            'company',
            'email_address',
            'phone_number',
            'address',
        )
        verbose_name = 'Person'
        verbose_name_plural = 'People'


class Address(obj_tables.Model):
    street = obj_tables.StringAttribute(primary=True, unique=True, verbose_name='Street')
    city = obj_tables.StringAttribute(verbose_name='City')
    state = obj_tables.StringAttribute(verbose_name='State')
    zip_code = obj_tables.StringAttribute(verbose_name='Zip code')
    country = obj_tables.StringAttribute(verbose_name='Country')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.multiple_cells
        attribute_order = (
            'street',
            'city',
            'state',
            'zip_code',
            'country',
        )
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
