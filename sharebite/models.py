""" models.py """

from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

# user model
class User(AbstractUser):
    """ Base user types """
    is_donor = models.BooleanField(default=False)
    is_receiver = models.BooleanField(default=False)

# Donations Model
class Donation(models.Model):
    """ Base donation models """
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Successful', 'Successful'),
    ]
    donor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='donations')
    title = models.CharField(max_length=255)
    description = models.TextField()
    food_image = models.ImageField(upload_to='donations/', blank=True, null=True)
    quantity = models.PositiveIntegerField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    location = models.CharField(max_length=255)
    is_reserved = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    reserved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name='reserved_donations'
    )
    status = models.CharField(max_length=15, \
                              choices=STATUS_CHOICES, default='Pending')  # Default status
    collection_point = models.ForeignKey(
        'DropoffLocation',
        on_delete=models.PROTECT,
        related_name='donations',
    )
    COLLECTION_STATUS_CHOICES = [
        ('awaiting_dropoff', 'Awaiting drop-off'),
        ('received_at_collection_point', 'Received at collection point'),
    ]
    collection_status = models.CharField(
        max_length=40,
        choices=COLLECTION_STATUS_CHOICES,
        default='awaiting_dropoff',
    )

    def cancel_reservation(self):
        """ Pick up of donation cancelled """
        self.is_reserved = False
        self.reserved_by = None
        self.save()

    def __str__(self):
        return f"{self.title} - Donor: {self.donor.username}"

# Proof Model
class Proof(models.Model):
    """ Basic Proofs """
    donation = models.OneToOneField(Donation, on_delete=models.CASCADE, related_name='proof')
    proof_image = models.ImageField(upload_to='proofs/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"Proof for Donation ID: {self.donation.id}"


# Admin Drop- Off Sites
class DropOffsite(models.Model):
    """ Drop off sites """
    location = models.CharField(max_length=255)
    added_by = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, related_name='added_sites')
    created_at = models.DateTimeField(auto_now_add=True)

# Reciepts
class Receipt(models.Model):
    """ Receipt Models """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receipt')
    donation = models.OneToOneField(Donation, on_delete=models.CASCADE, related_name='receipt')
    proof_image = models.ImageField(upload_to='receipts/', null=True, blank=True)
    pickup_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Receipt for {self.donation.title} by {self.user.username}"

#drop off location
class DropoffLocation(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=255, blank=True, null=True)
    opening_hours = models.CharField(max_length=255, blank=True, default='')
    accepted_food_types = models.JSONField(default=list)
    instructions = models.TextField(blank=True, default='')

    def __str__(self):
        return self.name
