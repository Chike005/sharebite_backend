import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sharebite', '0007_donation_collection_point_donation_collection_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='donation',
            name='collection_point',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='donations',
                to='sharebite.dropofflocation',
            ),
        ),
    ]
