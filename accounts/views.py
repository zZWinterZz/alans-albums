from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from integrations.discogs import search as discogs_search_api


def staff_required(view_func):
    return user_passes_test(lambda u: u.is_active and u.is_staff)(view_func)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created. You can now log in.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
@staff_required
def manage_landing(request):
    """Front-facing manage landing for staff tools."""
    return render(request, 'manage.html')


@login_required
@staff_required
def discogs_search(request):
    """Placeholder Discogs search view; will call API utility later."""
    query = request.GET.get('q', '')
    results = None
    if query:
        # Call the Discogs API helper. It will use Django cache and handle
        # retries/backoff. Ensure DISCOGS_TOKEN is set in the environment.
        try:
            results = discogs_search_api(query, page=1, per_page=12)
        except Exception:
            # On error, fall back to empty list so the page still loads
            results = []
    has_token = bool(__import__('os').environ.get('DISCOGS_TOKEN'))
    context = {
        'query': query,
        'results': results,
        'has_token': has_token,
    }
    return render(request, 'discogs_search.html', context)
