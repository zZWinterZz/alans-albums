from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required, user_passes_test
from integrations.discogs import search as discogs_search_api, get_release as discogs_get_release
from integrations.discogs import price_suggestions as discogs_price_suggestions
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django import forms
import re
from django.conf import settings
from django.core.mail import send_mail
from .forms import MessageForm, ReplyForm, GuestReplyForm, ProfileForm
from .models import (
    Message, MessageImage, Reply, ReplyImage,
    MessageRead, ReplyRead,
)
from django.utils import timezone
from django.db.models import Q


def staff_required(view_func):
    return user_passes_test(lambda u: u.is_active and u.is_staff)(view_func)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created. You can now log in.', extra_tags='account')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def contact_view(request):
    """Public contact form: saves Message/Images and emails site owner.

    For subject 'selling' the form accepts image uploads (validated in the form).
    """
    form = MessageForm(request.POST or None, files=request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            # Save the message
            msg = form.save(commit=False)
            if request.user.is_authenticated:
                msg.user = request.user
                # populate username automatically for authenticated users
                msg.username = request.user.username
            msg.save()

            # Mark the message as read for the sender (if a registered user).
            # Without this, the context processor counts the owner's own message
            # as "unread" because there is no MessageRead record for them.
            try:
                if msg.user:
                    MessageRead.objects.create(message=msg, user=msg.user, read_at=timezone.now())
            except Exception:
                # best-effort; don't block saving the message on read-marker failures
                pass

            # Save uploaded images when present and when subject == selling
            files = form.cleaned_data.get('images') or []
            if msg.subject == Message.SUBJECT_SELLING or files:
                for f in files:
                    # limit is enforced by the form
                    mi = MessageImage(message=msg)
                    mi.image = f
                    if request.user.is_authenticated:
                        mi.uploaded_by = request.user
                    mi.save()

            # Notify site owner by email (best-effort)
            subject = f"Contact form: {msg.subject}"
            text = f"From: {msg.name} <{msg.email}>\n\n{msg.body}"
            recipient_list = []
            if getattr(settings, 'CONTACT_EMAIL', None):
                recipient_list = [settings.CONTACT_EMAIL]
            elif getattr(settings, 'DEFAULT_FROM_EMAIL', None):
                recipient_list = [settings.DEFAULT_FROM_EMAIL]

            if recipient_list:
                try:
                    send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, recipient_list, fail_silently=True)
                except Exception:
                    # don't block user flow on email errors
                    pass

            messages.success(request, 'Thanks — your message has been saved. We will reply shortly.', extra_tags='contact')
            # If this was sent by a guest (no user), email them a secure reply link
            if not msg.user:
                try:
                    from django.urls import reverse
                    reply_url = request.build_absolute_uri(reverse('guest_reply', args=[str(msg.reference)]))
                    guest_subject = f"Thanks for your message on {getattr(settings, 'SITE_NAME', 'the site')}"
                    guest_text = (
                        f"Hi {msg.name},\n\n"
                        "Thanks for getting in touch. If you'd like to reply to this thread you can do so here:\n\n"
                        f"{reply_url}\n\n"
                        "Note: replies via this link accept text only."
                    )
                    send_mail(guest_subject, guest_text, settings.DEFAULT_FROM_EMAIL, [msg.email], fail_silently=True)
                except Exception:
                    pass

            return redirect('contact')
        except Exception:
            messages.error(request, 'Unable to save your message right now. Please try again later.', extra_tags='contact')

    contact_email = getattr(settings, 'CONTACT_EMAIL', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    return render(request, 'contact.html', {'form': form, 'contact_email': contact_email})


class CustomLoginView(LoginView):
    """Login view that respects a 'remember_me' checkbox on the login form.

    If 'remember_me' is checked the session expiry will be extended (30 days).
    Otherwise the session will expire on browser close (set_expiry(0)).
    """
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        # Let the LoginView perform the usual login flow first
        response = super().form_valid(form)
        try:
            remember = self.request.POST.get('remember_me')
            if remember:
                # 30 days
                self.request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                # expire on browser close
                self.request.session.set_expiry(0)
        except Exception:
            # best effort; don't crash login
            pass
        return response


@login_required
@staff_required
def manage_landing(request):
    """Front-facing manage landing for staff tools."""
    return render(request, 'manage.html')


@login_required
def dashboard_view(request):
    """Render the user dashboard showing recent orders and account actions.

    - Regular users see only their orders.
    - Staff users see all orders.
    """
    # Import locally to avoid circular imports at module import time
    try:
        from .models import Order
    except Exception:
        Order = None

    orders = []
    if Order:
        if request.user.is_staff:
            orders = Order.objects.all().order_by('-created_at')
        else:
            orders = Order.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'dashboard.html', {'orders': orders})


@login_required
def profile_edit(request):
    """Allow users to edit basic profile fields: username, email, first/last name.

    Password changes should use Django's built-in password change views.
    """
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Profile updated.', extra_tags='profile')
            return redirect('dashboard')
        except Exception:
            messages.error(request, 'Unable to save profile. Please try again.', extra_tags='profile')

    return render(request, 'profile_edit.html', {'form': form})


@login_required
def messages_inbox(request):
    """Simple inbox view for staff to browse messages."""
    if request.user.is_authenticated and not request.user.is_staff:
        qs = Message.objects.filter(user=request.user).order_by('-created_at')
    else:
        qs = Message.objects.all().order_by('-created_at')

    # Prefetch replies and reads to reduce DB hits
    qs = qs.prefetch_related('replies', 'reads', 'replies__reads')

    messages_list = []
    total_unread = 0
    for m in qs:
        # Count unread replies relevant to this user
        if request.user.is_staff:
            unread_replies = m.replies.filter(Q(user__isnull=True) | Q(user__is_staff=False)).exclude(reads__user=request.user).count()
            # initial message unread for staff when they haven't marked it
            initial_unread = 0 if m.reads.filter(user=request.user, read_at__isnull=False).exists() else 1
        else:
            # owner's unread replies are replies by staff
            unread_replies = m.replies.filter(user__is_staff=True).exclude(reads__user=request.user).count()
            # initial_unread only counts when the message wasn't created by this user
            if m.user and m.user != request.user:
                initial_unread = 0 if m.reads.filter(user=request.user, read_at__isnull=False).exists() else 1
            else:
                initial_unread = 0

        m.unread_count = unread_replies + initial_unread
        # Determine who posted the last reply (if any) and expose flags that
        # indicate whether the last reply was from staff or from the current
        # viewing user. This ensures the 'Replied' badge reflects the last
        # message author, not any historical reply.
        try:
            last = m.replies.order_by('-created_at').first()
            if last and last.user:
                m.staff_has_replied = bool(getattr(last.user, 'is_staff', False))
                m.owner_has_replied = (request.user.is_authenticated and last.user == request.user)
            else:
                m.staff_has_replied = False
                m.owner_has_replied = False
        except Exception:
            m.staff_has_replied = False
            m.owner_has_replied = False
        # If the current user is the owner, determine whether the message has
        # been read by any staff member. If not, show a small 'Sent' indicator
        # because the owner has sent a message that staff haven't seen yet.
        try:
            if (
                m.user and request.user.is_authenticated and m.user == request.user
                and not m.replies.exists()
            ):
                m.sent_unread_for_staff = not MessageRead.objects.filter(
                    message=m, user__is_staff=True, read_at__isnull=False
                ).exists()
            else:
                m.sent_unread_for_staff = False
        except Exception:
            m.sent_unread_for_staff = False
        total_unread += m.unread_count
        messages_list.append(m)

    return render(request, 'messages.html', {'messages_list': messages_list, 'total_unread': total_unread})


@login_required
def message_thread(request, pk: int):
    """View a message thread and allow replies by the message owner or staff."""
    msg = get_object_or_404(Message, pk=pk)
    # permission: staff or owner
    if not (request.user.is_staff or (request.user.is_authenticated and msg.user and msg.user == request.user)):
        # if guest message, show a read-only view instructing to use email/phone
        return render(request, 'messages_thread.html', {'message': msg, 'can_reply': False})

    # Mark the message thread as read for the current user (per-user marker)
    try:
        mr, _ = MessageRead.objects.get_or_create(message=msg, user=request.user)
        mr.mark_read()
    except Exception:
        # best-effort; don't block the thread view on DB issues
        pass

    # Mark any replies authored by others as read for the current user
    try:
        for r in msg.replies.exclude(user=request.user):
            if not r.reads.filter(user=request.user).exists():
                ReplyRead.objects.create(reply=r, user=request.user, read_at=timezone.now())
    except Exception:
        pass

    can_reply = True
    form = None
    if request.method == 'POST':
        # Toggle replied checkbox action
        if 'toggle_replied' in request.POST:
            try:
                # Checkbox presence indicates True; absence means False
                new_val = 'replied' in request.POST
                msg.replied = new_val
                msg.save(update_fields=['replied'])
            except Exception:
                # Silently ignore toggle failures to avoid cross-page flash messages
                pass
            return redirect('message_thread', pk=msg.pk)

        # Otherwise handle posting a reply
        form = ReplyForm(request.POST, files=request.FILES or None)
        if form.is_valid():
            try:
                r = Reply.objects.create(user=request.user, message=msg, body=form.cleaned_data['body'])
                # mark the new reply as read for the author
                try:
                    ReplyRead.objects.create(reply=r, user=request.user, read_at=timezone.now())
                except Exception:
                    pass
                files = form.cleaned_data.get('images') or []
                for f in files:
                    ri = ReplyImage(reply=r)
                    ri.image = f
                    ri.save()

                # Notify the other party that a new reply exists (registered users get an email)
                try:
                    # If the original message belongs to a registered user and the replier
                    # is not the same user, send that user an email notifying them of the reply.
                    if (
                        msg.user
                        and msg.user.email
                        and (not request.user or msg.user != request.user)
                    ):
                        notify_subject = (
                            "New reply to your message: "
                            f"{msg.get_subject_display()}"
                        )
                        thread_url = request.build_absolute_uri(
                            reverse('message_thread', args=[msg.pk])
                        )
                        excerpt = r.body[:200] + ('...' if len(r.body) > 200 else '')
                        notify_text = (
                            f"Hi {msg.name or msg.username},\n\n"
                            "You have a new reply to your message on {site_name}.\n\n"
                            f"Reply excerpt:\n{excerpt}\n\n"
                            f"View the conversation: {thread_url}\n\n"
                            "If you no longer wish to receive these notifications, reply to the thread."
                        )
                        try:
                            send_mail(
                                notify_subject,
                                notify_text.format(
                                    site_name=getattr(settings, 'SITE_NAME', 'the site')
                                ),
                                settings.DEFAULT_FROM_EMAIL,
                                [msg.user.email],
                                fail_silently=True,
                            )
                        except Exception:
                            # swallow email errors; do not block reply creation
                            pass

                    # If the message was from a guest (no user) and a staff/owner replied, the existing
                    # guest-email flow (above) will notify the guest; nothing extra needed here.
                except Exception:
                    # best-effort notify; ignore failures
                    pass

                # mark message as replied when owner/staff sends a reply
                if not msg.replied:
                    msg.replied = True
                    msg.save(update_fields=['replied'])

                # If the original message is from a guest (no user), send an email to them with the reply
                if not msg.user:
                    # only send email when owner/staff replies
                    try:
                        send_mail(
                            f"Reply to your message: {msg.get_subject_display()}",
                            r.body,
                            settings.DEFAULT_FROM_EMAIL,
                            [msg.email],
                            fail_silently=True,
                        )
                    except Exception:
                        pass

                messages.success(request, 'Reply sent.', extra_tags='inbox')
                return redirect('message_thread', pk=msg.pk)
            except Exception:
                messages.error(request, 'Unable to save reply.')
    else:
        form = ReplyForm()

    # per-user read markers are handled via MessageRead/ReplyRead models above

    return render(request, 'messages_thread.html', {'message': msg, 'can_reply': can_reply, 'form': form})


def guest_reply(request, reference):
    """Allow non-registered users to reply to their message via a secure UUID reference.

    This view accepts only a short text reply (no images) and sends a notification to the
    site owner/staff. It creates a Reply with no associated user.
    """
    msg = get_object_or_404(Message, reference=reference)
    # If the message belongs to a registered user, direct them to the internal thread.
    if msg.user:
        return redirect('message_thread', pk=msg.pk)

    form = GuestReplyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            r = Reply.objects.create(user=None, message=msg, body=form.cleaned_data['body'])
            # notify site owner/staff about guest reply
            try:
                subj = f"Guest replied to your message: {msg.get_subject_display()}"
                text = f"Guest reply from {msg.name} <{msg.email}>:\n\n{r.body}"
                recipients = []
                if getattr(settings, 'CONTACT_EMAIL', None):
                    recipients = [settings.CONTACT_EMAIL]
                elif getattr(settings, 'DEFAULT_FROM_EMAIL', None):
                    recipients = [settings.DEFAULT_FROM_EMAIL]
                if recipients:
                    send_mail(subj, text, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
            except Exception:
                pass

            messages.success(request, 'Thanks — your reply has been recorded. The owner will be notified.', extra_tags='inbox')
            return redirect('guest_reply', reference=reference)
        except Exception:
            messages.error(request, 'Unable to save your reply. Please try again later.', extra_tags='inbox')

    return render(request, 'guest_reply.html', {'message': msg, 'form': form})


@login_required
def delete_reply(request, reply_id: int):
    """Delete a single reply. Allowed for staff or the reply author.

    Expects POST. Redirects back to the message thread.
    """
    r = get_object_or_404(Reply, pk=reply_id)
    msg = r.message
    # permission: staff or reply author
    if not (request.user.is_staff or (request.user.is_authenticated and r.user and r.user == request.user)):
        messages.error(request, 'Permission denied.')
        return redirect('messages')

    if request.method == 'POST':
        try:
            r.delete()
            messages.success(request, 'Reply deleted.', extra_tags='inbox')
        except Exception:
            messages.error(request, 'Unable to delete reply.', extra_tags='inbox')
    return redirect('message_thread', pk=msg.pk)


@login_required
def delete_message(request, pk: int):
    """Delete a whole conversation (message + replies). Allowed for staff or owner.

    Expects POST. Redirects to inbox after deletion.
    """
    m = get_object_or_404(Message, pk=pk)
    if not (request.user.is_staff or (request.user.is_authenticated and m.user and m.user == request.user)):
        messages.error(request, 'Permission denied.')
        return redirect('messages')

    if request.method == 'POST':
        try:
            m.delete()
            messages.success(request, 'Conversation deleted.', extra_tags='inbox')
            return redirect('messages')
        except Exception:
            messages.error(request, 'Unable to delete conversation.', extra_tags='inbox')
            return redirect('message_thread', pk=pk)


@login_required
def delete_selected_messages(request):
    """Delete multiple selected messages from the inbox.

    The form should POST 'selected' values with message ids. Only messages
    owned by the user (or all messages if staff) will be deleted.
    """
    if request.method != 'POST':
        return redirect('messages')

    ids = request.POST.getlist('selected')
    if not ids:
        messages.info(request, 'No messages selected.', extra_tags='inbox')
        return redirect('messages')

    qs = Message.objects.filter(pk__in=ids)
    if not request.user.is_staff:
        # Restrict to messages owned by the user
        qs = qs.filter(user=request.user)

    deleted = 0
    for m in qs:
        try:
            m.delete()
            deleted += 1
        except Exception:
            pass

    messages.success(request, f'Deleted {deleted} message(s).', extra_tags='inbox')
    return redirect('messages')


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
    # ensure results is a list to avoid NoneType issues when checking length
    if results is None:
        results = []
    # pagination helpers
    per_page = 12
    cur_page = int(pagination.get('page')) if (pagination and pagination.get('page')) else page
    total_pages = int(pagination.get('pages')) if (pagination and pagination.get('pages')) else None
    # if the API provided pagination info, use it; otherwise infer has_next from results length
    has_prev = cur_page > 1
    if total_pages is not None:
        has_next = cur_page < total_pages
    else:
        # if we received at least `per_page` results, assume there may be a next page
        has_next = (len(results) >= per_page)

    context = {
        'query': query,
        'results': results,
        'has_token': has_token,
        'year': filter_year or '',
        'format': filter_format or '',
        'country': filter_country or '',
        'pagination': pagination,
        'page': page,
        'cur_page': cur_page,
        'total_pages': total_pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': max(1, cur_page - 1),
        'next_page': cur_page + 1,
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
        'stock': '',
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

        # parse stock if provided
        stock_val = None
        try:
            stock_val = int(pdata.get('stock')) if pdata.get('stock') not in (None, '') else None
        except Exception:
            stock_val = None

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
            stock=stock_val,
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


@login_required
@staff_required
def listing_quick_update(request, pk: int):
    """Quick update for price and stock from the manage listings list view.

    Expects POST with 'price' and 'stock' fields. Redirects back to listing_list.
    """
    from .models import Listing
    if request.method != 'POST':
        return redirect('listing_list')

    listing = get_object_or_404(Listing, pk=pk)
    price_val = None
    stock_val = None
    try:
        p = request.POST.get('price', '').strip()
        price_val = float(p) if p not in (None, '') else None
    except Exception:
        price_val = listing.price

    s = request.POST.get('stock', '').strip()
    try:
        stock_val = int(s) if s not in (None, '') else None
    except Exception:
        stock_val = None

    # Update fields
    try:
        listing.price = price_val
        listing.stock = stock_val
        listing.save(update_fields=['price', 'stock'])
        messages.success(request, 'Listing updated.', extra_tags='manage')
    except Exception:
        messages.error(request, 'Unable to update listing.', extra_tags='manage')

    return redirect('listing_list')


class ListingForm(forms.ModelForm):
    class Meta:
        from .models import Listing

        model = Listing
        fields = [
            'artist', 'title', 'year', 'country', 'catalog_number', 'formats',
            'release_notes', 'price', 'condition', 'thumb', 'featured', 'stock'
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
        # Toggle featured, but prevent featuring when stock == 0
        new_featured = not bool(obj.featured)
        if new_featured and obj.stock == 0:
            # Do not allow featuring an out-of-stock item
            messages.error(request, 'Cannot feature an item with 0 stock.', extra_tags='manage')
        else:
            obj.featured = new_featured
            obj.save()
            messages.success(request, 'Listing updated')
    return redirect(reverse('listing_list'))


def store_list(request):
    """Public store page: featured first, then all listings with filters."""
    from .models import Listing

    artist_q = request.GET.get('artist', '').strip()
    title_q = request.GET.get('title', '').strip()
    format_q = request.GET.get('format', '').strip()

    # Only include featured items that are not explicitly out of stock
    try:
        from django.db import models as djmodels
        featured = Listing.objects.filter(featured=True).filter(
            djmodels.Q(stock__isnull=True) | djmodels.Q(stock__gt=0)
        ).order_by('-created_at')[:8]
    except Exception:
        # If the DB schema doesn't yet have stock, fall back
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

    # Hide listings that are explicitly out of stock (stock == 0)
    try:
        from django.db import models as djmodels
        qs = qs.filter(djmodels.Q(stock__isnull=True) | djmodels.Q(stock__gt=0))
    except Exception:
        # If the DB schema doesn't have stock yet, ignore the filter
        pass

    listings = qs

    context = {
        'featured': featured,
        'listings': listings,
        'artist_q': artist_q,
        'title_q': title_q,
        'format_q': format_q,
    }
    return render(request, 'store_list.html', context)


# Basket and Stripe integration (session-backed basket + Stripe Checkout)
def _get_session_basket(request):
    """Return the basket dict stored in session (listing_id -> quantity)."""
    return request.session.setdefault('basket', {})


def _get_basket_map(request):
    """Return a mapping of listing_id -> quantity for the current request.

    If the user is authenticated, return the persistent basket contents from DB.
    Otherwise return the session-backed basket dict.
    """
    if request.user.is_authenticated:
        try:
            from .models import BasketItem
            items = BasketItem.objects.filter(basket__user=request.user).values_list('listing_id', 'quantity')
            return {str(lid): qty for lid, qty in items}
        except Exception:
            return {}
    else:
        # Clean session-backed basket by removing items that no longer exist
        # or have been set to out-of-stock (stock == 0). Mutate the session
        # in-place so subsequent requests see the cleaned basket.
        sb = _get_session_basket(request)
        if not sb:
            return sb
        from .models import Listing
        changed = False
        for lid in list(sb.keys()):
            try:
                listing = Listing.objects.get(pk=int(lid))
                # If stock is defined and zero, remove from session basket
                if listing.stock is not None and listing.stock == 0:
                    del sb[lid]
                    changed = True
            except Exception:
                # Remove stale ids
                try:
                    del sb[lid]
                    changed = True
                except Exception:
                    pass
        if changed:
            try:
                request.session.modified = True
            except Exception:
                pass
        return sb


def basket_view(request):
    from .models import Listing
    basket = _get_basket_map(request)
    items = []
    total = 0
    for lid, qty in list(basket.items()):
        try:
            listing = Listing.objects.get(pk=int(lid))
        except Exception:
            # remove stale ids
            try:
                del request.session['basket'][lid]
                request.session.modified = True
            except Exception:
                pass
            continue
        qty = int(qty)
        price = listing.price or 0
        line_total = price * qty
        items.append({'listing': listing, 'quantity': qty, 'line_total': line_total})
        total += line_total

    return render(request, 'basket.html', {'items': items, 'total': total})


def basket_add(request, listing_id: int):
    """Add one quantity of a listing to the session basket. Expects POST."""
    from django.http import JsonResponse
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
    if request.method != 'POST':
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)
        return redirect('store')
    key = str(listing_id)
    # Check stock before adding
    from .models import Listing
    try:
        listing = Listing.objects.get(pk=listing_id)
    except Exception:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Unknown item.'}, status=404)
        messages.error(request, 'Unknown item.', extra_tags='basket')
        return redirect('store')

    # If stock is defined and zero -> cannot add
    if listing.stock is not None and listing.stock == 0:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'This item is out of stock.'}, status=400)
        messages.error(request, 'This item is out of stock.', extra_tags='basket')
        return redirect('basket')

    if request.user.is_authenticated:
        # Persist into DB
        try:
            from .models import Basket, BasketItem
            from django.db import transaction
            basket, _ = Basket.objects.get_or_create(user=request.user)
            with transaction.atomic():
                bi, created = BasketItem.objects.get_or_create(
                    basket=basket,
                    listing_id=listing_id,
                    defaults={'quantity': 1}
                )
                if not created:
                    # Check we won't exceed stock
                    new_qty = bi.quantity + 1
                    if listing.stock is not None and new_qty > listing.stock:
                        if is_ajax:
                            return JsonResponse({'status': 'error', 'message': 'Not enough stock available.'}, status=400)
                        messages.error(request, 'Not enough stock available.', extra_tags='basket')
                        return redirect('basket')
                    bi.quantity = new_qty
                    bi.save(update_fields=['quantity'])
        except Exception:
            # fallback to session
            sb = _get_session_basket(request)
            sb[key] = int(sb.get(key, 0)) + 1
            request.session.modified = True
    else:
        basket = _get_session_basket(request)
        # Check session quantity vs stock
        cur = int(basket.get(key, 0))
        newq = cur + 1
        if listing.stock is not None and newq > listing.stock:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': 'Not enough stock available.'}, status=400)
            messages.error(request, 'Not enough stock available.', extra_tags='basket')
            return redirect('basket')
        basket[key] = newq
        request.session.modified = True
    if is_ajax:
        # return the updated basket count so the frontend can update the badge
        try:
            bm = _get_basket_map(request) or {}
            total_count = sum(int(v) for v in bm.values())
        except Exception:
            total_count = 0
        return JsonResponse({'status': 'ok', 'message': 'Added to basket.', 'count': total_count})
    messages.success(request, 'Added to basket.', extra_tags='basket')
    return redirect('basket')


def basket_remove(request, listing_id: int):
    """Remove a listing from the basket. Expects POST."""
    if request.method != 'POST':
        return redirect('basket')
    key = str(listing_id)
    if request.user.is_authenticated:
        try:
            from .models import BasketItem
            BasketItem.objects.filter(basket__user=request.user, listing_id=listing_id).delete()
            messages.success(request, 'Removed from basket.', extra_tags='basket')
        except Exception:
            messages.error(request, 'Unable to remove item from basket.', extra_tags='basket')
    else:
        basket = _get_session_basket(request)
        if key in basket:
            try:
                del basket[key]
                request.session.modified = True
                messages.success(request, 'Removed from basket.', extra_tags='basket')
            except Exception:
                messages.error(request, 'Unable to remove item from basket.', extra_tags='basket')
    return redirect('basket')


def basket_checkout(request):
    """Create a Stripe Checkout session for the basket and redirect the user.

    This view expects the Stripe secret key to be present in settings. It will
    redirect the browser to the hosted checkout page.
    """
    import stripe

    basket = _get_basket_map(request)
    if not basket:
        messages.error(request, 'Your basket is empty.', extra_tags='basket')
        return redirect('basket')

    # Build line items from listings
    from .models import Listing
    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    currency = getattr(settings, 'STRIPE_CURRENCY', 'gbp')
    line_items = []
    for lid, qty in basket.items():
        try:
            listing = Listing.objects.get(pk=int(lid))
        except Exception:
            continue
        unit_amount = int((listing.price or 0) * 100)
        # Stripe requires positive amounts
        if unit_amount <= 0:
            continue
        line_items.append({
            'price_data': {
                'currency': currency,
                'product_data': {'name': f"{listing.artist} - {listing.title}"},
                'unit_amount': unit_amount,
            },
            'quantity': int(qty),
        })

    if not line_items:
        messages.error(request, 'No payable items in basket.', extra_tags='basket')
        return redirect('basket')

    try:
        import json
        # If Stripe isn't configured for local/dev, shortcut to success so
        # developers can test the flow without real Stripe credentials.
        if not getattr(settings, 'STRIPE_SECRET_KEY', ''):
            # Clear session basket for guests and redirect to success for dev
            try:
                request.session['basket'] = {}
                request.session.modified = True
            except Exception:
                pass
            return redirect(reverse('basket_success') + '?session_id=dev')

        # Attach basket as metadata so the webhook can reconstruct order items
        metadata = {'basket': json.dumps(basket)}
        create_kwargs = dict(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri(reverse('basket_success')) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('basket_cancel')),
            metadata=metadata,
        )
        # If user is authenticated, include client_reference_id to link to DB basket/user
        if request.user and request.user.is_authenticated:
            create_kwargs['client_reference_id'] = str(request.user.pk)

        session = stripe.checkout.Session.create(**create_kwargs)
        # Redirect to the hosted Checkout page
        return redirect(session.url, code=303)
    except Exception as e:
        messages.error(request, f'Unable to create Stripe session: {e}', extra_tags='basket')
        return redirect('basket')


def basket_success(request):
    # Clear the basket for now; a webhook should be used to reliably fulfill orders
    session_id = request.GET.get('session_id')
    try:
        request.session['basket'] = {}
        request.session.modified = True
    except Exception:
        pass
    return render(request, 'basket_success.html', {'session_id': session_id})


def basket_cancel(request):
    return render(request, 'basket_cancel.html')


def stripe_webhook(request):
    """Basic Stripe webhook handler. Verify signature when STRIPE_WEBHOOK_SECRET is set.

    Currently this handler acknowledges events and does not create Orders.
    It's a safe place to extend fulfillment logic later.
    """
    import stripe
    import json
    from django.http import HttpResponse
    payload = request.body
    sig = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    try:
        if secret:
            event = stripe.Webhook.construct_event(payload, sig, secret)
        else:
            # If no webhook secret configured, fall back to parsing the JSON body
            event = json.loads(payload)
    except Exception:
        return HttpResponse(status=400)

    # Handle a completed Checkout session
    try:
        etype = event.get('type') if isinstance(event, dict) else getattr(event, 'type', None)
        if etype == 'checkout.session.completed':
            # Create an Order record from the metadata (preferred) or by
            # fetching line_items from Stripe as a fallback.
            try:
                data = event.get('data', {}).get('object', {}) if isinstance(event, dict) else getattr(event, 'data', None) and getattr(event.data, 'object', {})
                session_id = data.get('id') if isinstance(data, dict) else getattr(data, 'id', None)
                metadata = data.get('metadata') if isinstance(data, dict) else None
                basket_map = None
                if metadata and metadata.get('basket'):
                    import json as _json
                    try:
                        basket_map = _json.loads(metadata.get('basket'))
                    except Exception:
                        basket_map = None

                # Fallback: retrieve session and expand line_items
                if not basket_map and session_id:
                    try:
                        sess = stripe.checkout.Session.retrieve(session_id, expand=['line_items', 'customer_details'])
                        # line_items is an object with data list
                        li = getattr(sess, 'line_items', None) or (sess.get('line_items') if isinstance(sess, dict) else None)
                        items_list = []
                        if li:
                            for item in (li.data if hasattr(li, 'data') else (li.get('data') if isinstance(li, dict) else [])):
                                qty = int(item.get('quantity') or getattr(item, 'quantity', 0))
                                name = item.get('description') or item.get('price', {}).get('product', '')
                                items_list.append({'name': name, 'quantity': qty})
                        # We don't have listing ids here; downstream code will try to match by name.
                    except Exception:
                        items_list = []

                # Create Order in DB
                from django.apps import apps
                Order = apps.get_model('accounts', 'Order')
                OrderItem = apps.get_model('accounts', 'OrderItem')
                Listing = apps.get_model('accounts', 'Listing')

                # Determine user if client_reference_id present
                client_ref = data.get('client_reference_id') if isinstance(data, dict) else None
                user_obj = None
                if client_ref:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    try:
                        user_obj = User.objects.filter(pk=int(client_ref)).first()
                    except Exception:
                        user_obj = None

                order = Order.objects.create(user=user_obj, stripe_session_id=session_id)

                total = 0
                # If we have a basket_map (listing_id -> qty) use that
                if basket_map:
                    for lid, qty in basket_map.items():
                        try:
                            l = Listing.objects.filter(pk=int(lid)).first()
                            qty = int(qty)
                            unit_price = l.price or 0 if l else 0
                            OrderItem.objects.create(order=order, listing=l, quantity=qty, unit_price=unit_price)
                            total += (unit_price * qty)
                            # decrement stock if applicable
                            if l and l.stock is not None:
                                l.stock = max(0, l.stock - qty)
                                l.save(update_fields=['stock'])
                        except Exception:
                            continue
                else:
                    # Best-effort: create order items from items_list by matching listing title/name
                    for it in items_list:
                        try:
                            name = it.get('name') or ''
                            qty = int(it.get('quantity') or 0)
                            # match listing by artist - title substring
                            l = Listing.objects.filter(artist__icontains=name.split(' - ')[0] if ' - ' in name else name).first()
                            unit_price = l.price or 0 if l else 0
                            OrderItem.objects.create(order=order, listing=l, quantity=qty, unit_price=unit_price)
                            total += (unit_price * qty)
                            if l and l.stock is not None:
                                l.stock = max(0, l.stock - qty)
                                l.save(update_fields=['stock'])
                        except Exception:
                            continue

                # Mark order paid
                order.total_amount = total
                order.paid = True
                order.save(update_fields=['total_amount', 'paid'])

                # Remove persistent basket for this user if present
                if user_obj:
                    try:
                        Basket = apps.get_model('accounts', 'Basket')
                        BasketItem = apps.get_model('accounts', 'BasketItem')
                        BasketItem.objects.filter(basket__user=user_obj).delete()
                    except Exception:
                        pass
            except Exception:
                # swallow webhook errors to avoid 500 responses
                pass
    except Exception:
        pass

    return HttpResponse(status=200)
