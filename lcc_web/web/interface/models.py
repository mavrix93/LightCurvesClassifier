from __future__ import unicode_literals

from django.db import models
from django.utils import timezone
import json
# Create your models here.


class StarsFilter(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey('auth.User')
    status = models.CharField(default="Not started", max_length=15)
    start_date = models.DateTimeField(
        default=timezone.now)
    finish_date = models.DateTimeField(null=True, default=None)
    deciders = models.TextField(default="")
    descriptors = models.TextField(default="")


class DbQuery(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey('auth.User')
    status = models.CharField(default="Not started", max_length=15)
    start_date = models.DateTimeField(
        default=timezone.now)
    finish_date = models.DateTimeField(null=True, default=None)
    queries = models.IntegerField(null=True, default=None)
    used_filters = models.TextField(default="---")
    connectors = models.TextField(default="")
