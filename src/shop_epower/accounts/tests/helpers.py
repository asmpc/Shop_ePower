import itertools

from django.contrib.auth import get_user_model

from shop_epower.accounts.models import Role


User = get_user_model()


_user_counter = itertools.count(1)
_manager_counter = itertools.count(1)


def create_test_user(
    *,
    email=None,
    username=None,
    password="testpass123",
    first_name="Test",
    last_name="User",
    phone="+375291234567",
    role=Role.CLIENT,
    **kwargs,
):
    idx = next(_user_counter)

    return User.objects.create_user(
        email=email or f"user{idx}@example.com",
        username=username or f"user{idx}",
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=role,
        **kwargs,
    )

def create_manager(
    email=None,
    username=None,
    **kwargs,
):
    idx = next(_user_counter)

    defaults = {
        "email": email or f"manager{idx}@example.com",
        "username": username or f"manager{idx}",
        "password": "testpass",
        "role": Role.MANAGER,
        "first_name": "Test",
        "last_name": "Manager",
        "phone": f"+37529111{idx:04d}",
    }

    defaults.update(kwargs)

    return create_test_user(
        **defaults,
    )