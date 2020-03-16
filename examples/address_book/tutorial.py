def run():
    #########################
    # import schema
    import schema as address_book
    PersonType = address_book.Person.type.enum_class

    #########################
    # Create companies
    apple = address_book.Company(name='Apple',
                                 url='https://www.apple.com/',
                                 address=address_book.Address(street='10600 N Tantau Ave',
                                                              city='Cupertino',
                                                              state='CA',
                                                              zip_code='95014',
                                                              country='US'))
    facebook = address_book.Company(name='Facebook',
                                    url='https://www.facebook.com/',
                                    address=address_book.Address(street='1 Hacker Way #15',
                                                                 city='Menlo Park', state='CA',
                                                                 zip_code='94025',
                                                                 country='US'))
    google = address_book.Company(name='Google',
                                  url='https://www.google.com/',
                                  address=address_book.Address(street='1600 Amphitheatre Pkwy',
                                                               city='Mountain View',
                                                               state='CA',
                                                               zip_code='94043',
                                                               country='US'))
    netflix = address_book.Company(name='Netflix',
                                   url='https://www.netflix.com/',
                                   address=address_book.Address(street='100 Winchester Cir',
                                                                city='Los Gatos',
                                                                state='CA',
                                                                zip_code='95032',
                                                                country='US'))
    companies = [apple, facebook, google, netflix]

    #########################
    # Create CEOs
    cook = address_book.Person(name='Tim Cook',
                               type=PersonType.business,
                               company=apple,
                               email_address='tcook@apple.com',
                               phone_number='408-996-1010',
                               address=apple.address)
    hastings = address_book.Person(name='Reed Hastings',
                                   type=PersonType.business,
                                   company=netflix,
                                   email_address='reed.hastings@netflix.com',
                                   phone_number='408-540-3700',
                                   address=netflix.address)
    pichai = address_book.Person(name='Sundar Pichai',
                                 type=PersonType.business,
                                 company=google,
                                 email_address='sundar@google.com',
                                 phone_number='650-253-0000',
                                 address=google.address)
    zuckerberg = address_book.Person(name='Mark Zuckerberg',
                                     type=PersonType.family,
                                     company=facebook,
                                     email_address='zuck@fb.com',
                                     phone_number='650-543-4800',
                                     address=facebook.address)

    ceos = [cook, hastings, pichai, zuckerberg]

    #########################
    # Validate address book
    import obj_tables
    errors = obj_tables.Validator().run(companies + ceos)
    assert errors is None

    #########################
    # Get a property of a company
    assert facebook.url == 'https://www.facebook.com/'

    #########################
    # Edit a property of a company
    facebook.url = 'https://about.fb.com/'

    #########################
    # Export address book
    import obj_tables.io
    import os
    import tempfile
    dirname = tempfile.mkdtemp()
    filename_xlsx = os.path.join(dirname, 'address_book.xlsx')
    obj_tables.io.Writer().run(filename_xlsx, companies + ceos,
                               models=[address_book.Company, address_book.Person])

    #########################
    # Import address book
    objects = obj_tables.io.Reader().run(filename_xlsx,
                                         models=[address_book.Company, address_book.Person],
                                         group_objects_by_model=False,
                                         ignore_sheet_order=True)

    #########################
    # Chek if two CEOs are semantically equivalent
    zuckerberg_copy = next(el for el in objects if isinstance(el, address_book.Person) and el.name == 'Mark Zuckerberg')
    assert zuckerberg_copy.is_equal(zuckerberg)
    assert zuckerberg_copy.difference(zuckerberg) == ''

    #########################
    # Cleanup temporary directory
    import shutil
    shutil.rmtree(dirname)
