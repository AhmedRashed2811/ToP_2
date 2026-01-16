from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply numeric value * arg. Returns '' if invalid."""
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return ""
    


@register.filter(name="to_percent")
def to_percent(value, ndigits=2):
    """Return value*100 formatted as a percent string."""
    try:
        ndigits = int(ndigits)
        return f"{float(value) * 100:.{ndigits}f}%"
    except (TypeError, ValueError):
        return ""
    
    

@register.filter
def replace_underscore_with_space(value):
    return value.replace("_", " ")


@register.filter
def get_value(obj, index):
    if index == 1:
        return obj.dp1 or 0
    elif index == 2:
        return obj.dp2 or 0
    else:
        return getattr(obj, f'installment_{index - 2}', 0)
    


from django import template
register = template.Library()

@register.filter
def getattr(obj, attr):
    return getattr(obj, attr, "")
