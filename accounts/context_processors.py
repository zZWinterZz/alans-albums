from django.db.models import Q, Sum
from .models import Message, Reply


def messages_count(request):
    """Provide a small messages_count for the navbar.

    - For staff users: count threads where the most recent reply was not from staff
      (i.e., threads that need staff attention).
    - For non-staff authenticated users: count their threads where the most
      recent reply was not from them (i.e., new replies from staff or no reply).

    Returns an empty dict for anonymous users to avoid exposing counts.
    """
    if not request.user or not request.user.is_authenticated:
        return {}

    user = request.user
    total_unread = 0

    if user.is_staff:
        unread_replies = Reply.objects.filter(
            Q(user__isnull=True) | Q(user__is_staff=False)
        ).exclude(reads__user=user).count()

        unread_messages = Message.objects.exclude(reads__user=user).count()
        total_unread = unread_replies + unread_messages
    else:
        unread_replies = Reply.objects.filter(
            message__user=user,
            user__is_staff=True,
        ).exclude(reads__user=user).count()

        unread_messages = Message.objects.filter(user=user).exclude(reads__user=user).count()
        total_unread = unread_replies + unread_messages

    return {'messages_count': total_unread}


def basket_count(request):
    """Provide a small basket_count for the navbar.

    - For authenticated users: sum quantities in their persistent Basket (if any).
    - For anonymous users: sum quantities in the session-backed 'basket' dict.

    Returns an empty dict when zero to avoid rendering a badge with '0'.
    """
    total = 0
    try:
        if request.user and request.user.is_authenticated:
            # Import BasketItem here to avoid circular imports at module load
            from .models import BasketItem
            agg = BasketItem.objects.filter(basket__user=request.user).aggregate(total_qty=Sum('quantity'))
            total = int(agg.get('total_qty') or 0)
        else:
            session_basket = request.session.get('basket', {}) or {}
            # session_basket is {listing_id: qty}; remove entries for deleted or
            # out-of-stock listings so the count reflects available items only.
            if session_basket:
                from .models import Listing
                changed = False
                running = 0
                for lid, v in list(session_basket.items()):
                    try:
                        listing = Listing.objects.get(pk=int(lid))
                        if listing.stock is not None and listing.stock == 0:
                            # remove from session
                            del session_basket[lid]
                            changed = True
                            continue
                        running += int(v)
                    except Exception:
                        try:
                            del session_basket[lid]
                            changed = True
                        except Exception:
                            pass
                if changed:
                    try:
                        request.session.modified = True
                    except Exception:
                        pass
                total = running
            else:
                total = 0
    except Exception:
        # On any error, don't break templates; return 0
        total = 0

    return {'basket_count': total} if total else {}
