from django.db import migrations


def forwards(apps, schema_editor):
    Listing = apps.get_model('accounts', 'Listing')
    # Copy suggested_price into price when price is empty
    for obj in Listing.objects.all():
        # Use getattr to tolerate both states during migration
        sp = getattr(obj, 'suggested_price', None)
        if sp is not None and (obj.price is None):
            obj.price = sp
            obj.save(update_fields=['price'])


def backwards(apps, schema_editor):
    # No-op: we won't restore suggested_price automatically
    return


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name='listing',
            name='suggested_price',
        ),
    ]
