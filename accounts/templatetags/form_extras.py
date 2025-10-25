from django import template
from django.utils.html import conditional_escape

register = template.Library()


@register.filter(name='add_class')
def add_class(bound_field, css_class):
    """Return the field rendered with the given css class merged into any
    existing widget classes.

    Usage in template: {{ field|add_class:"form-control" }}
    """
    try:
        widget = bound_field.field.widget
        existing = widget.attrs.get('class', '')
        classes = (existing + ' ' + css_class).strip()
        return bound_field.as_widget(
            attrs={'class': conditional_escape(classes)}
        )
    except Exception:
        # Fallback: render the field normally
        try:
            return bound_field.as_widget()
        except Exception:
            return ''
