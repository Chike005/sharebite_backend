""" admin.py """
from django.contrib import admin
from .models import Donation, DropoffLocation, Proof, Receipt, User

@admin.register(DropoffLocation)
class DropoffLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "latitude", "longitude")
    search_fields = ("name",)

admin.site.register(User)
admin.site.register(Donation)
admin.site.register(Proof)
admin.site.register(Receipt)
