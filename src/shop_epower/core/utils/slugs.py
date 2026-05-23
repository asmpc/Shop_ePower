from django.utils.text import slugify


def generate_unique_slug(instance, field_value, slug_field='slug'):

    base_slug = slugify(field_value)

    slug = base_slug

    model_class = instance.__class__

    counter = 1

    while model_class.objects.filter(
        **{slug_field: slug}
    ).exclude(
        pk=instance.pk
    ).exists():

        slug = f'{base_slug}-{counter}'

        counter += 1

    return slug