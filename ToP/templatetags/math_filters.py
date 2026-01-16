from django import template

register = template.Library()

@register.filter
def floatmultiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''
