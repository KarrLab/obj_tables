""" Test examples

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-18
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import io
from obj_tables import utils
import obj_tables
import os
import unittest


class ExamplesTestCase(unittest.TestCase):
    def test_web_app_example(self):
        filename = 'obj_tables/web_app/examples/parents_children.xlsx'
        sbtab = True

        schema = utils.init_schema(filename, sbtab=sbtab)
        models = list(utils.get_models(schema).values())

        io.Reader().run(filename,
                        models=models,
                        group_objects_by_model=False,
                        sbtab=sbtab,
                        **io.SBTAB_DEFAULT_READER_OPTS)

        #########################
        # import parents_children
        parents_children = schema

        #########################
        # Create parents
        jane_doe = parents_children.Parent(id='jane_doe', name='Jane Doe')
        john_doe = parents_children.Parent(id='john_doe', name='John Doe')
        mary_roe = parents_children.Parent(id='mary_roe', name='Mary Roe')
        richard_roe = parents_children.Parent(id='richard_roe', name='Richard Roe')

        # Create children
        jamie_doe = parents_children.Child(id='jamie_doe',
                                           name='Jamie Doe',
                                           gender=parents_children.Child.gender.enum_class.female,
                                           parents=[jane_doe, john_doe])
        jamie_doe.favorite_video_game = parents_children.Game(name='Legend of Zelda: Ocarina of Time',
                                                              publisher='Nintendo',
                                                              year=1998)

        jimie_doe = parents_children.Child(id='jimie_doe',
                                           name='Jimie Doe',
                                           gender=parents_children.Child.gender.enum_class.male,
                                           parents=[jane_doe, john_doe])
        jimie_doe.favorite_video_game = parents_children.Game(name='Super Mario Brothers',
                                                              publisher='Nintendo',
                                                              year=1985)
        linda_roe = parents_children.Child(id='linda_roe',
                                           name='Linda Roe',
                                           gender=parents_children.Child.gender.enum_class.female,
                                           parents=[mary_roe, richard_roe])
        linda_roe.favorite_video_game = parents_children.Game(name='Sonic the Hedgehog',
                                                              publisher='Sega',
                                                              year=1991)
        mike_roe = parents_children.Child(id='mike_roe',
                                          name='Michael Roe',
                                          gender=parents_children.Child.gender.enum_class.male,
                                          parents=[mary_roe, richard_roe])
        mike_roe.favorite_video_game = parents_children.Game(name='SimCity',
                                                             publisher='Electronic Arts',
                                                             year=1989)

        #########################
        mike_roe = mary_roe.children.get_one(id='mike_roe')
        mikes_parents = mike_roe.parents
        mikes_sisters = mikes_parents[0].children.get(gender=parents_children.Child.gender.enum_class.female)

        #########################
        jamie_doe.favorite_video_game.name = 'Legend of Zelda'
        jamie_doe.favorite_video_game.year = 1986

        #########################
        import obj_tables

        objects = [jane_doe, john_doe, mary_roe, richard_roe,
                   jamie_doe, jimie_doe, linda_roe, mike_roe]
        errors = obj_tables.Validator().run(objects)
        assert errors is None

        #########################
        import obj_tables.io

        filename = 'obj_tables/web_app/examples/parents_children.xlsx'
        objects = obj_tables.io.Reader().run(filename, sbtab=True,
                                            models=[parents_children.Parent, parents_children.Child],
                                            group_objects_by_model=True)
        parents = objects[parents_children.Parent]
        jane_doe_2 = next(parent for parent in parents if parent.id == 'jane_doe')

        #########################
        filename = 'obj_tables/web_app/examples/parents_children_copy.xlsx'
        objects = [jane_doe, john_doe, mary_roe, richard_roe,
                   jamie_doe, jimie_doe, linda_roe, mike_roe]
        obj_tables.io.Writer().run(filename, objects,
                                  models=[parents_children.Parent, parents_children.Child],
                                  sbtab=True)

        #########################
        assert jane_doe.is_equal(jane_doe_2)

        #########################
        # cleanup
        os.remove(filename)
