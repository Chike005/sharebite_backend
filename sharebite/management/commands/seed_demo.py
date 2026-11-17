from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils import timezone

from sharebite.models import Donation, DropoffLocation, User


DEMO_USERS = (
    {
        'username': 'demo-staff',
        'email': 'demo-staff@sharebite.local',
        'first_name': 'Demo',
        'last_name': 'Staff',
        'is_staff': True,
        'is_donor': False,
        'is_receiver': False,
    },
    {
        'username': 'demo-donor',
        'email': 'demo-donor@sharebite.local',
        'first_name': 'Demo',
        'last_name': 'Donor',
        'is_staff': False,
        'is_donor': True,
        'is_receiver': False,
    },
    {
        'username': 'demo-receiver',
        'email': 'demo-receiver@sharebite.local',
        'first_name': 'Demo',
        'last_name': 'Receiver',
        'is_staff': False,
        'is_donor': False,
        'is_receiver': True,
    },
)


class Command(BaseCommand):
    help = 'Create local-only ShareBite demo accounts and staged donations.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                'Demo data can only be seeded when DJANGO_DEBUG=true.'
            )

        with transaction.atomic():
            demo_password = get_random_string(24)
            users = {}
            for user_data in DEMO_USERS:
                user, created = User.objects.get_or_create(
                    username=user_data['username'],
                    defaults=user_data,
                )
                if not created and (
                    user.email != user_data['email'] or user.is_superuser
                ):
                    raise CommandError(
                        f"Refusing to overwrite existing account "
                        f"{user_data['username']}."
                    )

                for field, value in user_data.items():
                    if field != 'username':
                        setattr(user, field, value)
                user.set_password(demo_password)
                user.save()
                users[user.username] = user

            try:
                collection_point = DropoffLocation.objects.get(
                    name='Ancoats Share Hub'
                )
            except DropoffLocation.DoesNotExist as error:
                raise CommandError(
                    'Collection points are missing. Run '
                    '`python manage.py migrate` first.'
                ) from error

            donation_defaults = {
                'description': 'Illustrative portfolio demo food donation.',
                'quantity': 8,
                'expiry_date': timezone.localdate() + timedelta(days=3),
                'location': collection_point.address,
                'collection_point': collection_point,
                'status': 'Pending',
                'is_reserved': False,
                'is_delivered': False,
                'reserved_by': None,
            }
            Donation.objects.get_or_create(
                donor=users['demo-donor'],
                title='Demo: Seasonal produce box',
                defaults={
                    **donation_defaults,
                    'collection_status': 'awaiting_dropoff',
                },
            )
            Donation.objects.get_or_create(
                donor=users['demo-donor'],
                title='Demo: Bakery bundle',
                defaults={
                    **donation_defaults,
                    'collection_status': 'received_at_collection_point',
                },
            )

        self.stdout.write(self.style.SUCCESS('ShareBite demo data is ready.'))
        self.stdout.write(f'Demo password (all accounts): {demo_password}')
        self.stdout.write('Accounts: demo-staff, demo-donor, demo-receiver')
