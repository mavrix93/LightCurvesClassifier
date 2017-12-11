from django.contrib import admin

# Register your models here.

from .models import DbQuery, StarsFilter

admin.site.register(DbQuery)
admin.site.register(StarsFilter)