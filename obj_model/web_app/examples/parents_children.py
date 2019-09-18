# Schema automatically generated at 2019-09-18 13:22:29

import obj_model


class Parent(obj_model.Model):
    id = obj_model.StringAttribute(unique=True, primary=True, verbose_name='!Id')
    name = obj_model.StringAttribute(verbose_name='!Name')

    class Meta(obj_model.Model.Meta):
        table_format = obj_model.TabularOrientation.column
        attribute_order = ('id', 'name',)
        verbose_name = '!Parent'
        verbose_name_plural = '!Parent'


class Child(obj_model.Model):
    id = obj_model.StringAttribute(unique=True, primary=True, verbose_name='!Id')
    name = obj_model.StringAttribute(verbose_name='!Name')
    gender = obj_model.EnumAttribute(['female', 'male'], verbose_name='!Gender')
    parents = obj_model.ManyToManyAttribute('Parent', related_name='children', verbose_name='!Parents')
    favorite_video_game = obj_model.ManyToOneAttribute('Game', related_name='children', verbose_name='!FavoriteVideoGame')

    class Meta(obj_model.Model.Meta):
        table_format = obj_model.TabularOrientation.row
        attribute_order = ('id', 'name', 'gender', 'parents', 'favorite_video_game',)
        verbose_name = '!Child'
        verbose_name_plural = '!Child'


class Game(obj_model.Model):
    name = obj_model.StringAttribute(unique=True, primary=True, verbose_name='!Name')
    publisher = obj_model.StringAttribute(verbose_name='!Publisher')
    year = obj_model.IntegerAttribute(verbose_name='!Year')

    class Meta(obj_model.Model.Meta):
        table_format = obj_model.TabularOrientation.multiple_cells
        attribute_order = ('name', 'publisher', 'year',)
        verbose_name = '!Game'
        verbose_name_plural = '!Game'
