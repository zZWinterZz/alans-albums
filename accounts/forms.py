from django import forms
from django.forms import ModelForm
from django.contrib.auth import get_user_model
from .models import Message


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    subject = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6})
    )

    def clean_message(self):
        msg = self.cleaned_data.get('message', '')
        # basic length guard
        if len(msg.strip()) < 10:
            raise forms.ValidationError(
                'Please provide a longer message (at least 10 characters).'
            )
        return msg


class MessageForm(ModelForm):
    images = forms.FileField(
        required=False,
        # Widget rendered in template uses the `multiple` attribute there; keep
        # a normal ClearableFileInput here to avoid widget-time errors.
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        help_text='Optional images (jpg/png). Max 5 files.'
    )

    class Meta:
        model = Message
        # username is populated automatically for authenticated users
        fields = ['name', 'phone', 'email', 'subject', 'body', 'contact_preference']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'contact_preference': forms.Select(attrs={'class': 'form-select'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        }

    def clean_images(self):
        files = self.files.getlist('images') if hasattr(self, 'files') else []
        if not files:
            return []
        if len(files) > 5:
            raise forms.ValidationError('Please upload at most 5 images.')
        allowed = ('image/jpeg', 'image/png')
        max_size = 5 * 1024 * 1024
        for f in files:
            if f.content_type not in allowed:
                raise forms.ValidationError('Only JPG and PNG images are allowed.')
            if f.size > max_size:
                raise forms.ValidationError('Each image must be smaller than 5MB.')
        return files


class ReplyForm(forms.Form):
    body = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
    )
    images = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        help_text='Optional images (jpg/png). Max 5 files.'
    )

    def clean_images(self):
        files = self.files.getlist('images') if hasattr(self, 'files') else []
        if not files:
            return []
        if len(files) > 5:
            raise forms.ValidationError('Please upload at most 5 images.')
        allowed = ('image/jpeg', 'image/png')
        max_size = 5 * 1024 * 1024
        for f in files:
            if f.content_type not in allowed:
                raise forms.ValidationError('Only JPG and PNG images are allowed.')
            if f.size > max_size:
                raise forms.ValidationError('Each image must be smaller than 5MB.')
        return files


class GuestReplyForm(forms.Form):
    """Simple text-only reply form for non-registered users replying via a secure link."""
    body = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
    )

    def clean_body(self):
        b = self.cleaned_data.get('body', '')
        if len(b.strip()) < 3:
            raise forms.ValidationError('Please enter a short reply (at least 3 characters).')
        return b


class ProfileForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'username': 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'
        }
