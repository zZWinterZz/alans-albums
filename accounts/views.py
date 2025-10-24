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
import re


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
    filter_year = request.GET.get('year', '').strip() or None
    filter_format = request.GET.get('format', '').strip() or None
    filter_country = request.GET.get('country', '').strip() or None
    try:
        page = int(request.GET.get('page', '1'))
        if page < 1: page = 1
    except Exception:
        page = 1
    results = None
    pagination = {}
    if query:
        # Call the Discogs API helper. It will use Django cache and handle
        # retries/backoff. Ensure DISCOGS_TOKEN is set in the environment.
        try:
            # Request pagination info so we can present prev/next links
            maybe = discogs_search_api(
                query, page=page, per_page=12, year=filter_year, format_=filter_format, country=filter_country, return_pagination=True
            )
            if isinstance(maybe, tuple):
                raw_results, pagination = maybe
            else:
                raw_results = maybe
                pagination = {}
        except Exception:
            raw_results = []
            pagination = {}

        # Build result cards from the search response only (avoid N+1 remote calls)
        results = []
        # collect raw items first so we can apply a secondary ordering
        raw_items = []
        for r in (raw_results or []):
            # use fields provided by the search hit to populate the card quickly
            release_id = r.get('id')
            artists = ''
            # search hits sometimes include 'title' with artist/title combined,
            # but may also include separate fields
            title = r.get('title') or ''
            release_year = r.get('year') or ''
            country = r.get('country') or r.get('country_code') or ''
            # formats in search hits can be in 'format' or 'format_title'
            formats = r.get('format') or r.get('format_title') or ''
            formats_lines = [formats] if formats else []
            catalog_number = r.get('catno') or ''
            release_notes = ''
            suggested_price = ''

            item = {
                'artist': artists,
                'title': title,
                'year': release_year,
                'country': country,
                'catalog_number': catalog_number,
                'formats': formats,
                'formats_lines': formats_lines,
                'release_notes': release_notes,
                'suggested_price': suggested_price,
                'thumb': r.get('thumb', ''),
                'resource_url': r.get('resource_url'),
                'release_id': release_id,
            }

            # Apply the same post-filters (year, format, country) against the
            # lightweight item to ensure the UI only shows matching cards.
            passes = True
            if filter_year:
                try:
                    if int(str(item.get('year') or '')) != int(filter_year):
                        passes = False
                except Exception:
                    if str(item.get('year') or '').strip() != str(filter_year).strip():
                        passes = False

            if passes and filter_format:
                ff = str(filter_format).strip().lower()
                fmt_join = ' '.join([str(item.get('formats') or '' )] + [str(x) for x in (item.get('formats_lines') or [])]).lower()
                if ff not in fmt_join:
                    passes = False

            if passes and filter_country:
                fc = str(filter_country).strip().lower()
                if fc and fc not in str(item.get('country') or '').lower():
                    passes = False

            if not passes:
                continue

            raw_items.append(item)

        # Apply secondary ordering: keep Discogs API order between groups,
        # but for multiple variants of the same release (same artist+title)
        # sort those variants by year descending. This preserves relevance
        # as returned by Discogs but surfaces newer pressings first within a
        # group of otherwise-identical records.
        ordered = []
        def norm(s):
            try:
                return (s or '').strip().lower()
            except Exception:
                return ''

        # build mapping from key -> list preserving appearance order
        groups = {}
        first_seen_index = {}
        for idx, it in enumerate(raw_items):
            key = (norm(it.get('artist')), norm(it.get('title')))
            groups.setdefault(key, []).append(it)
            if key not in first_seen_index:
                first_seen_index[key] = idx

        # iterate groups in order of first appearance
        for key, _ in sorted(first_seen_index.items(), key=lambda x: x[1]):
            group = groups.get(key) or []
            if len(group) <= 1:
                ordered.extend(group)
                continue
            # sort group by year desc (missing years go last)
            def year_key(it):
                y = it.get('year')
                try:
                    return -int(y) if y not in (None, '') else float('inf')
                except Exception:
                    return float('inf')

            sorted_group = sorted(group, key=year_key)
            ordered.extend(sorted_group)

        results = ordered
    has_token = bool(__import__('os').environ.get('DISCOGS_TOKEN'))
    context = {
        'query': query,
        'results': results,
        'has_token': has_token,
        'year': filter_year or '',
        'format': filter_format or '',
        'country': filter_country or '',
        'pagination': pagination,
        'page': page,
        # normalize pagination helpers for templates
        'cur_page': int(pagination.get('page')) if (pagination and pagination.get('page')) else page,
        'total_pages': int(pagination.get('pages')) if (pagination and pagination.get('pages')) else None,
        'has_prev': (int(pagination.get('page')) > 1) if (pagination and pagination.get('page')) else (page > 1),
        'has_next': ((int(pagination.get('page')) < int(pagination.get('pages'))) if (pagination and pagination.get('page') and pagination.get('pages')) else (not bool(pagination))) ,
        'prev_page': (int(pagination.get('page')) - 1) if (pagination and pagination.get('page')) else max(1, page - 1),
        'next_page': (int(pagination.get('page')) + 1) if (pagination and pagination.get('page')) else (page + 1),
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
def discogs_release_details_view(request, release_id: int):
    """Return minimal release details (notes) as JSON for on-demand fetching."""
    data = {'notes': ''}
    try:
        rel = discogs_get_release(int(release_id))
        if rel:
            raw = rel.get('notes') or ''
            # Instead of stripping URL BBCode completely (which made some
            # surrounding text look odd after removal), mark URL blocks so
            # the UI can highlight them for manual deletion. We replace
            # [url=...]text[/url] and [url]text[/url] with a visible token
            # like [[REMOVE:text]] so the frontend can style it.
            note = raw
            try:
                # replace [url=...]text[/url] -> [[REMOVE:text]] (keep inner text)
                note = re.sub(r"\[url=[^\]]*\](.*?)\[/url\]", r"[[REMOVE:\1]]", note, flags=re.IGNORECASE|re.DOTALL)
                # replace [url]text[/url]
                note = re.sub(r"\[url\](.*?)\[/url\]", r"[[REMOVE:\1]]", note, flags=re.IGNORECASE|re.DOTALL)
                # replace image tags with a small marker
                note = re.sub(r"\[img\].*?\[/img\]", "[[REMOVE:image]]", note, flags=re.IGNORECASE|re.DOTALL)
                # remove simple BBCode tags like [b], [i], [u], [size], [quote]
                note = re.sub(r"\[((?:b|i|u|size|quote))(?:=[^\]]*)?\](.*?)\[/\1\]", r"\2", note, flags=re.IGNORECASE|re.DOTALL)
            except Exception:
                note = raw

            # collapse repeated whitespace and trim
            note = re.sub(r"\s+", " ", note).strip()
            data['notes'] = note
            # build formats_lines similarly to the previous detailed view
            formats_lines = []
            for f in rel.get('formats', []):
                parts = []
                name = f.get('name')
                if name:
                    parts.append(name)
                text = f.get('text')
                if text:
                    parts.append(text)
                descs = f.get('descriptions') or []
                if descs:
                    parts.append(', '.join(descs))
                line = ' — '.join([p for p in parts if p])
                if line:
                    formats_lines.append(line)
            data['formats_lines'] = formats_lines
    except Exception:
        data['notes'] = ''
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
        # Do not prefill price or condition from GET params to avoid unintended injection via links
        'price': '',
        'featured': False,
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



        except Exception:
            pass

    if request.method == 'POST':
        # Persist a Listing record from the posted form data
        from .models import Listing

        pdata = {k: request.POST.get(k, '') for k in pre.keys()}
        # featured is a checkbox; normalize to boolean
        try:
            featured_flag = bool(request.POST.get('featured'))
        except Exception:
            featured_flag = False
        # Convert numeric fields
        price_val = None
        try:
            price_val = float(pdata.get('price'))
        except Exception:
            price_val = None

        listing = Listing.objects.create(
            artist=pdata.get('artist', ''),
            title=pdata.get('title', ''),
            year=(int(pdata.get('year')) if pdata.get('year') else None),
            country=pdata.get('country', ''),
            catalog_number=pdata.get('catalog_number', ''),
            formats=pdata.get('formats', ''),
            release_notes=pdata.get('release_notes', ''),
            price=price_val,
            # Use the release_id (if any) as the resource reference rather than accepting arbitrary resource_url via GET
            resource_url=str(release_id) if release_id else '',
            thumb=pdata.get('thumb', ''),
            created_by=request.user if request.user.is_authenticated else None,
            featured=featured_flag,
        )
        # Handle uploaded images (optional)
        try:
            files = request.FILES.getlist('images')
        except Exception:
            files = []
        if files:
            from .models import ListingImage
            for f in files:
                if not f:
                    continue
                try:
                    li = ListingImage(listing=listing, uploaded_by=request.user if request.user.is_authenticated else None)
                    li.image = f
                    li.save()
                except Exception:
                    # don't abort listing creation if an image fails to upload
                    continue

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
            'release_notes', 'price', 'condition', 'thumb', 'featured'
        ]


@login_required
@staff_required
def listing_edit(request, pk: int):
    from .models import Listing

    obj = get_object_or_404(Listing, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        # If user clicked the 'Delete selected' button, only delete selected images and return
        if action == 'delete_selected':
            delete_ids = request.POST.getlist('images_to_delete')
            deleted_count = 0
            if delete_ids:
                from .models import ListingImage
                qs = ListingImage.objects.filter(listing=obj, pk__in=delete_ids)
                deleted_count = qs.count()
                if deleted_count:
                    qs.delete()
            if deleted_count:
                messages.success(request, f"{deleted_count} image(s) deleted")
            else:
                messages.info(request, 'No images selected for deletion')
            return redirect(reverse('listing_edit', args=[obj.pk]))

        # Otherwise it's the normal save/upload flow
        form = ListingForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            # If the form included a featured checkbox override, apply it explicitly
            try:
                if 'featured' in request.POST:
                    obj.featured = bool(request.POST.get('featured'))
                    obj.save(update_fields=['featured'])
            except Exception:
                pass
            # delete selected existing images (also allow deleting as part of save)
            delete_ids = request.POST.getlist('images_to_delete')
            deleted_count = 0
            if delete_ids:
                from .models import ListingImage
                qs = ListingImage.objects.filter(listing=obj, pk__in=delete_ids)
                deleted_count = qs.count()
                if deleted_count:
                    qs.delete()

            # handle uploaded images
            files = request.FILES.getlist('images')
            from .models import ListingImage
            for f in files:
                # skip empty uploads
                if not f:
                    continue
                try:
                    li = ListingImage(listing=obj, uploaded_by=request.user if request.user.is_authenticated else None)
                    # assign the uploaded file directly to the CloudinaryField and save the model
                    li.image = f
                    li.save()
                except Exception:
                    # avoid aborting the whole request if a single image fails to save
                    continue
            msg = 'Listing updated'
            if deleted_count:
                msg = f"{msg} — {deleted_count} image(s) deleted"
            messages.success(request, msg)
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

    # Previously we excluded featured items from the All listings section to
    # avoid duplicate DOM nodes. Templates now render unique overlay ids so
    # it's fine to show featured items in the main listings as well (helpful
    # for users who browse straight to the store). Keep featured items sorted
    # to the top of the list.
    qs = Listing.objects.order_by('-featured', '-created_at')
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
