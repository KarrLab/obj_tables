# Schema automatically generated at 2020-04-26 21:15:32

import obj_tables


__all__ = [
    'Child',
    'Game',
    'Parent',
]


class Game(obj_tables.Model):
    name = obj_tables.StringAttribute(unique=True, primary=True)
    publisher = obj_tables.StringAttribute()
    year = obj_tables.IntegerAttribute()

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.multiple_cells
        attribute_order = (
            'name',
            'publisher',
            'year',
        )
        verbose_name = 'Game'
        verbose_name_plural = 'Game'


class Child(obj_tables.Model):
    id = obj_tables.StringAttribute(unique=True, primary=True)
    name = obj_tables.StringAttribute()
    gender = obj_tables.EnumAttribute(['female', 'male'])
    parents = obj_tables.ManyToManyAttribute('Parent', related_name='children')
    favorite_video_game = obj_tables.ManyToOneAttribute('Game', related_name='children')

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.row
        attribute_order = (
            'id',
            'name',
            'gender',
            'parents',
            'favorite_video_game',
        )
        verbose_name = 'Child'
        verbose_name_plural = 'Child'


class Parent(obj_tables.Model):
    id = obj_tables.StringAttribute(unique=True, primary=True)
    name = obj_tables.StringAttribute()

    class Meta(obj_tables.Model.Meta):
        table_format = obj_tables.TableFormat.column
        attribute_order = (
            'id',
            'name',
        )
        verbose_name = 'Parent'
        verbose_name_plural = 'Parent'
