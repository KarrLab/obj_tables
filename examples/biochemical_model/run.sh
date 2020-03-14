obj-tables init-schema \
    schema.csv \
    schema.py
obj-tables gen-template \
    schema.csv \
    template.xlsx \
    --write-schema
obj-tables validate \
    schema.csv \
    data.xlsx
obj-tables convert \
    schema.csv \
    data.xlsx \
    data-copy.xlsx \
    --write-schema
obj-tables diff \
    schema.csv \
    Model data.xlsx \
    data-copy.xlsx
