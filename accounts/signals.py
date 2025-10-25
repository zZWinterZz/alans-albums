from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.db.models.signals import post_save


@receiver(post_save, dispatch_uid='listing_unfeature_on_zero_stock')
def unfeature_on_zero_stock(sender, instance, created, **kwargs):
    """If a Listing's stock becomes 0 ensure it's not featured.

    Use an update query to avoid calling instance.save() again and causing
    recursion.
    """
    try:
        # import locally to avoid circular import at module import time
        if sender.__name__ != 'Listing':
            return
        if getattr(instance, 'stock', None) == 0 and getattr(instance, 'featured', False):
            # Use queryset update to avoid triggering save() again
            sender.objects.filter(pk=instance.pk, featured=True).update(featured=False)
    except Exception:
        pass


@receiver(user_logged_in)
def merge_session_basket_into_user(sender, request, user, **kwargs):
    """When a user logs in, merge any session-based basket into their persistent basket.

    Session basket format: { '<listing_id>': qty, ... }
    """
    try:
        session_basket = request.session.get('basket', {}) or {}
        if not session_basket:
            return
        # Import here to avoid circular imports at module load time
        from .models import Basket, BasketItem
        from django.db import transaction

        basket, _ = Basket.objects.get_or_create(user=user)
        with transaction.atomic():
            for lid, qty in session_basket.items():
                try:
                    lid_int = int(lid)
                except Exception:
                    continue
                try:
                    bi = BasketItem.objects.filter(basket=basket, listing_id=lid_int).first()
                    if bi:
                        bi.quantity = bi.quantity + int(qty)
                        bi.save(update_fields=['quantity'])
                    else:
                        BasketItem.objects.create(basket=basket, listing_id=lid_int, quantity=int(qty))
                except Exception:
                    continue
        # Clear session basket after merge
        try:
            request.session['basket'] = {}
            request.session.modified = True
        except Exception:
            pass
    except Exception:
        # Never raise during login signal handling
        pass
