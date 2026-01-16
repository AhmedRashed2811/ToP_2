from django import template

register = template.Library()

@register.filter
def get_attribute(value, arg):
    """
    Gets an attribute of an object dynamically from a string name.
    Usage: {{ object|get_attribute:field_name }}
    """
    if hasattr(value, str(arg)):
        return getattr(value, arg)
    elif isinstance(value, dict) and arg in value:
        return value[arg]
    return ""



@register.filter
def replace(value, args):
    """
    Replaces characters in a string.
    Usage: {{ value|replace:"old|new" }}
    Example: {{ "first_name"|replace:"_| " }} -> "first name"
    """
    if args and "|" in args:
        old, new = args.split("|")
        return str(value).replace(old, new)
    return value