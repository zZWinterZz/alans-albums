from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
import uuid
from django.utils import timezone

try:
    # Prefer CloudinaryField if Cloudinary is configured in the project
    from cloudinary.models import CloudinaryField
    _ImageField = CloudinaryField
except Exception:
    # Fallback to Django's ImageField if Cloudinary isn't available
    from django.db.models import ImageField as _ImageField


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
    # The listing price. Previously named `suggested_price`; renamed to `price`.
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    thumb = models.URLField(blank=True)
    resource_url = models.URLField(blank=True)
    release_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
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


# Messaging models
MAX_MESSAGE_IMAGES = 5
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png']


def _validate_image_extension(value):
    # FileExtensionValidator expects extensions without dots
    validator = FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)
    return validator(value)


class Message(models.Model):
    SUBJECT_LISTINGS = 'listings'
    SUBJECT_ORDERS = 'orders'
    SUBJECT_SELLING = 'selling'
    SUBJECT_GENERAL = 'general'

    SUBJECT_CHOICES = [
        (SUBJECT_LISTINGS, 'Listings'),
        (SUBJECT_ORDERS, 'Orders'),
        (SUBJECT_SELLING, 'Selling'),
        (SUBJECT_GENERAL, 'General'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField(max_length=150, blank=True, help_text='Optional username or handle')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField()
    subject = models.CharField(max_length=32, choices=SUBJECT_CHOICES, default=SUBJECT_GENERAL)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_read = models.BooleanField(default=False)
    # Marked when the owner/staff has replied (helps tracking external replies)
    replied = models.BooleanField(default=False)
    reference = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    CONTACT_PREF_EMAIL = 'email'
    CONTACT_PREF_PHONE = 'phone'
    CONTACT_PREFERENCE_CHOICES = [
        (CONTACT_PREF_EMAIL, 'Email'),
        (CONTACT_PREF_PHONE, 'Phone'),
    ]
    contact_preference = models.CharField(
        max_length=10,
        choices=CONTACT_PREFERENCE_CHOICES,
        blank=True,
        help_text='Preferred contact method for non-registered users'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} from {self.name} <{self.email}> ({self.created_at:%Y-%m-%d %H:%M})"


class MessageImage(models.Model):
    message = models.ForeignKey(Message, related_name='images', on_delete=models.CASCADE)
    # Use project-preferred image field (CloudinaryField when available)
    image = _ImageField('image', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for message {self.message_id} ({self.pk})"


class Reply(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    message = models.ForeignKey(Message, related_name='replies', on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        who = self.user.username if self.user else f"anon ({self.message.email})"
        return f"Reply by {who} on {self.created_at:%Y-%m-%d %H:%M}"


class ReplyImage(models.Model):
    reply = models.ForeignKey(Reply, related_name='images', on_delete=models.CASCADE)
    image = _ImageField('image', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for reply {self.reply_id} ({self.pk})"


class MessageRead(models.Model):
    """Per-user read marker for a Message thread."""
    message = models.ForeignKey(Message, related_name='reads', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (('message', 'user'),)

    def mark_read(self):
        self.read_at = timezone.now()
        self.save(update_fields=['read_at'])


class ReplyRead(models.Model):
    """Per-user read marker for an individual Reply."""
    reply = models.ForeignKey(Reply, related_name='reads', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (('reply', 'user'),)

    def mark_read(self):
        self.read_at = timezone.now()
        self.save(update_fields=['read_at'])
