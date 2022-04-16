# Helpers to work around wtforms 2/3 differences.
try:
    from wtforms.validators import DataRequired
except ImportError:
    from wtforms.validators import Required as DataRequired
