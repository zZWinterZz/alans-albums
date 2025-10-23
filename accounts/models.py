from django.db import models
from django.conf import settings
from cloudinary.models import CloudinaryField


class Listing(models.Model):
    CONDITION_CHOICES = [
        ('P', 'Poor'),
        ('F', 'Fair'),
        ('G', 'Good'),
        ('G+', 'Good Plus'),
        ('VG', 'Very Good'),
        ('VG+', 'Very Good Plus'),
        ('NM', 'Near Mint'),
        ('M', 'Mint'),
    ]

    artist = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    country = models.CharField(max_length=128, blank=True)
    catalog_number = models.CharField(max_length=128, blank=True)
    formats = models.TextField(blank=True)
    release_notes = models.TextField(blank=True)
    suggested_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    thumb = models.URLField(blank=True)
    resource_url = models.URLField(blank=True)
    release_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    condition = models.CharField(max_length=4, choices=CONDITION_CHOICES, blank=True)
    featured = models.BooleanField(default=False, help_text='Mark listing as featured')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.artist} - {self.title} ({self.catalog_number})"


class ListingImage(models.Model):
    """Additional images for a Listing stored on Cloudinary."""
    listing = models.ForeignKey(Listing, related_name='images', on_delete=models.CASCADE)
    image = CloudinaryField('image', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"Image for {self.listing} ({self.pk})"
