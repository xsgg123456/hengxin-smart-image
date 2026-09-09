from pydantic import Field


def omitted(*, alias=None):
    """TS `field?: T`: omit absent values, reject an explicitly supplied null.

    The annotation remains T. None is only the unvalidated internal default,
    never a wire value; required nullable fields do not use this helper.
    """
    return Field(default=None, alias=alias, exclude_if=lambda value: value is None,
                 json_schema_extra=lambda schema: schema.pop('default', None))
