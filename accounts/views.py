from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from integrations.discogs import search as discogs_search_api, get_release as discogs_get_release
from integrations.discogs import price_suggestions as discogs_price_suggestions
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django import forms


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
            raw_results = discogs_search_api(query, page=1, per_page=12)
        except Exception:
            raw_results = []

        # For each search hit, attempt to fetch the full release details so we
        # can present Artist / Title / Year / Formats / Suggested price.
        results = []
        for r in (raw_results or []):
            release = None
            release_id = r.get('id')
            if not release_id:
                # try to parse id from resource_url like /releases/12345
                resource = r.get('resource_url') or ''
                if resource and '/releases/' in resource:
                    try:
                        release_id = int(resource.rstrip('/').split('/')[-1])
                    except Exception:
                        release_id = None
            if release_id:
                try:
                    release = discogs_get_release(release_id)
                except Exception:
                    release = None

            # Extract display fields with fallbacks to the search hit
            if release:
                artists = ', '.join([
                    a.get('name') for a in release.get('artists', []) if a.get('name')
                ])
                title = release.get('title') or r.get('title', '')
                year = release.get('year') or r.get('year', '')
                country = release.get('country') or ''
                # Extract catalog numbers from labels if present
                label_catnos = [lbl.get('catno') for lbl in release.get('labels', []) if lbl.get('catno')]
                catalog_number = '; '.join(label_catnos) if label_catnos else ''
                # Build a richer, line-oriented description for formats so we
                # surface details like 'embossed', 'gatefold', qty and free-text
                # that Discogs returns.
                formats_lines = []
                for f in release.get('formats', []):
                    parts = []
                    name = f.get('name')
                    if name:
                        parts.append(name)
                    # omit qty per request; only include free-text and descriptions
                    text = f.get('text')
                    if text:
                        parts.append(text)
                    descs = f.get('descriptions') or []
                    if descs:
                        parts.append(', '.join(descs))
                    line = ' — '.join([p for p in parts if p])
                    if line:
                        formats_lines.append(line)

                # Include release-level notes which sometimes contain details
                # like embossing or special packaging. (Do not surface styles here.)
                # Move release notes to their own field so the template can
                # render them in a collapsible area (many notes are long).
                release_notes = release.get('notes') or ''

                formats = '; '.join(formats_lines)
                # Determine a GBP-only suggested price. Prefer marketplace price_suggestions
                suggested_price = ''
                try:
                    ps = discogs_price_suggestions(release_id) or {}
                    # look for a GBP suggestion
                    for k, v in ps.items():
                        cur = (v.get('currency') or '').strip().upper()
                        if cur in ('GBP', '£'):
                            val = v.get('value')
                            try:
                                suggested_price = f"{float(val):.2f}"
                                break
                            except Exception:
                                suggested_price = str(val)
                                break
                except Exception:
                    suggested_price = ''

                if not suggested_price:
                    # fallback to community price or lowest_price (assume GBP if provided)
                    cp = release.get('community', {}).get('price')
                    lp = release.get('lowest_price')
                    for cand in (cp, lp):
                        if cand:
                            try:
                                suggested_price = f"{float(cand):.2f}"
                                break
                            except Exception:
                                suggested_price = str(cand)
                                break
            else:
                # Best-effort fallbacks
                # Some search hits include 'title' containing artist/title; prefer dedicated fields
                artists = ''
                title = r.get('title', '')
                year = r.get('year', '')
                formats = r.get('format') or r.get('format_title') or ''
                formats_lines = [formats] if formats else []
                suggested_price = ''
                # try common fallback keys for catalog/label info
                catalog_number = r.get('catno') or r.get('label') or ''

            results.append({
                'artist': artists,
                'title': title,
                'year': year,
                'country': country if 'country' in locals() else '',
                'catalog_number': catalog_number if 'catalog_number' in locals() else '',
                'formats': formats,
                'formats_lines': formats_lines,
                'release_notes': release_notes if 'release_notes' in locals() else '',
                'suggested_price': suggested_price,
                'thumb': r.get('thumb', ''),
                'resource_url': r.get('resource_url'),
                'release_id': release_id,
            })
    has_token = bool(__import__('os').environ.get('DISCOGS_TOKEN'))
    context = {
        'query': query,
        'results': results,
        'has_token': has_token,
    }
    return render(request, 'discogs_search.html', context)


@login_required
@staff_required
def discogs_price_suggestions_view(request, release_id: int):
    """Proxy endpoint to fetch Discogs price suggestions for a release.

    Returns cached JSON from the integrations helper.
    """
    data = {}
    try:
        data = discogs_price_suggestions(release_id)
    except Exception:
        data = {}
    return JsonResponse(data)


@login_required
@staff_required
def create_listing(request):
    """Simple listing creation form pre-filled from Discogs release or query params.

    GET: shows a form with fields prefilled from ?release_id=123 or other query params.
    POST: accepts the form and flashes a message (no persistence implemented).
    """
    release_id = request.GET.get('release_id')
    pre = {
        'artist': request.GET.get('artist', ''),
        'title': request.GET.get('title', ''),
        'year': request.GET.get('year', ''),
        'country': request.GET.get('country', ''),
        'catalog_number': request.GET.get('catalog_number', ''),
        'formats': request.GET.get('formats', ''),
        'release_notes': request.GET.get('release_notes', ''),
        'thumb': request.GET.get('thumb', ''),
        'suggested_price': request.GET.get('suggested_price', ''),
    }

    if release_id:
        try:
            release = discogs_get_release(int(release_id))
            if release:
                pre['artist'] = ', '.join([a.get('name') for a in release.get('artists', []) if a.get('name')])
                pre['title'] = release.get('title') or pre['title']
                pre['year'] = release.get('year') or pre['year']
                pre['country'] = release.get('country') or pre['country']
                label_catnos = [lbl.get('catno') for lbl in release.get('labels', []) if lbl.get('catno')]
                pre['catalog_number'] = '; '.join(label_catnos) if label_catnos else pre['catalog_number']
                # build a compact formats string
                fmts = []
                for f in release.get('formats', []):
                    p = []
                    if f.get('name'):
                        p.append(f.get('name'))
                    if f.get('text'):
                        p.append(f.get('text'))
                    if f.get('descriptions'):
                        p.append(', '.join(f.get('descriptions')))
                    if p:
                        fmts.append(' — '.join(p))
                pre['formats'] = '; '.join(fmts) if fmts else pre['formats']
                pre['release_notes'] = release.get('notes') or pre['release_notes']
                # pick a reasonable thumbnail if available
                imgs = release.get('images') or []
                if imgs:
                    first = imgs[0] or {}
                    pre['thumb'] = first.get('uri') or first.get('resource_url') or first.get('uri150') or pre.get('thumb', '')
                # normalize suggested price to GBP-only numeric string when possible
                try:
                    ps = discogs_price_suggestions(int(release_id)) or {}
                    for k, v in ps.items():
                        cur = (v.get('currency') or '').strip().upper()
                        if cur in ('GBP', '£'):
                            val = v.get('value')
                            try:
                                pre['suggested_price'] = f"{float(val):.2f}"
                                break
                            except Exception:
                                pre['suggested_price'] = str(val)
                                break
                except Exception:
                    pass

                if not pre.get('suggested_price'):
                    cp = release.get('community', {}).get('price')
                    lp = release.get('lowest_price')
                    for cand in (cp, lp):
                        if cand:
                            try:
                                pre['suggested_price'] = f"{float(cand):.2f}"
                                break
                            except Exception:
                                pre['suggested_price'] = str(cand)
                                break
        except Exception:
            pass

    if request.method == 'POST':
        # Persist a Listing record from the posted form data
        from .models import Listing

        pdata = {k: request.POST.get(k, '') for k in pre.keys()}
        # Convert numeric fields
        suggested = None
        try:
            suggested = float(pdata.get('suggested_price'))
        except Exception:
            suggested = None

        listing = Listing.objects.create(
            artist=pdata.get('artist', ''),
            title=pdata.get('title', ''),
            year=(int(pdata.get('year')) if pdata.get('year') else None),
            country=pdata.get('country', ''),
            catalog_number=pdata.get('catalog_number', ''),
            formats=pdata.get('formats', ''),
            release_notes=pdata.get('release_notes', ''),
            suggested_price=suggested,
            resource_url=request.GET.get('release_id') or '',
            thumb=pdata.get('thumb', ''),
            created_by=request.user if request.user.is_authenticated else None,
        )
        messages.success(request, f"Listing created for {listing.artist} - {listing.title}")
        return redirect(reverse('manage_discogs'))

    return render(request, 'create_listing.html', pre)


@login_required
@staff_required
def listing_list(request):
    """Show a list of store listings with basic actions."""
    from .models import Listing

    listings = Listing.objects.all().order_by('-created_at')
    return render(request, 'listing_list.html', {'listings': listings})


class ListingForm(forms.ModelForm):
    class Meta:
        from .models import Listing

        model = Listing
        fields = [
            'artist', 'title', 'year', 'country', 'catalog_number', 'formats',
            'release_notes', 'suggested_price', 'price', 'condition', 'thumb', 'featured'
        ]


@login_required
@staff_required
def listing_edit(request, pk: int):
    from .models import Listing

    obj = get_object_or_404(Listing, pk=pk)
    if request.method == 'POST':
        form = ListingForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Listing updated')
            return redirect(reverse('listing_list'))
    else:
        form = ListingForm(instance=obj)
    return render(request, 'listing_edit.html', {'form': form, 'listing': obj})


@login_required
@staff_required
def listing_delete(request, pk: int):
    from .models import Listing

    obj = get_object_or_404(Listing, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Listing deleted')
        return redirect(reverse('listing_list'))
    return render(request, 'listing_confirm_delete.html', {'listing': obj})


@login_required
@staff_required
def listing_toggle_featured(request, pk: int):
    from .models import Listing

    obj = get_object_or_404(Listing, pk=pk)
    if request.method == 'POST':
        obj.featured = not bool(obj.featured)
        obj.save()
        messages.success(request, 'Listing updated')
    return redirect(reverse('listing_list'))


def store_list(request):
    """Public store page: featured first, then all listings with filters."""
    from .models import Listing

    artist_q = request.GET.get('artist', '').strip()
    title_q = request.GET.get('title', '').strip()
    format_q = request.GET.get('format', '').strip()

    featured = Listing.objects.filter(featured=True).order_by('-created_at')[:8]

    qs = Listing.objects.all().order_by('-featured', '-created_at')
    if artist_q:
        qs = qs.filter(artist__icontains=artist_q)
    if title_q:
        qs = qs.filter(title__icontains=title_q)
    if format_q:
        qs = qs.filter(formats__icontains=format_q)

    listings = qs

    context = {
        'featured': featured,
        'listings': listings,
        'artist_q': artist_q,
        'title_q': title_q,
        'format_q': format_q,
    }
    return render(request, 'store_list.html', context)
