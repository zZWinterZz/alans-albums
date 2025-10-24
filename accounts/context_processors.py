from django.db.models import Q
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
