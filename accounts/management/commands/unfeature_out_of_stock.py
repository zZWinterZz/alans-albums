from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Unfeature any listings that have stock == 0'

    def handle(self, *args, **options):
        from accounts.models import Listing
        qs = Listing.objects.filter(stock=0, featured=True)
        total = qs.count()
        qs.update(featured=False)
        self.stdout.write(self.style.SUCCESS(f'Unfeatured {total} listing(s) with stock==0'))
