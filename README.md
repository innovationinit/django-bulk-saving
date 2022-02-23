# Django Bulk Saving

![Test package](https://github.com/innovationinit/django-bulk-saving/actions/workflows/test-package.yml/badge.svg?branch=main)
[![Coverage Status](https://coveralls.io/repos/github/innovationinit/django-bulk-saving/badge.svg)](https://coveralls.io/github/innovationinit/django-bulk-saving)


## About

This package provides utility for saving multiple Django model instances using one SQL query.

## Install

```bash
pip install django-bulk-saving
```

## Usage

Inherit from _BulkSavableModel_:

```python
from bulk_saving.models import BulkSavableModel
from django.db import models


class Product(BulkSavableModel):
    name = models.CharField(max_length=30)
```

Use as follows:

```python
with Product.bulk_saving():
    for idx, product in enumerate(Product.objects.all(), 1):
        product.name = 'Product nr %s' % idx
        product.save_later()
```

Products will be saved after exit from context.

## License
The Django Wicked Historian package is licensed under the [FreeBSD
License](https://opensource.org/licenses/BSD-2-Clause).
