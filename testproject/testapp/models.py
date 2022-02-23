from django.db import models

from bulk_saving.models import BulkSavableModel


class Foreign(models.Model):
    name = models.CharField(max_length=10)


class Bulky(BulkSavableModel):
    field = models.CharField(max_length=10)
    foreign = models.ForeignKey(Foreign, null=True, on_delete=models.CASCADE)

