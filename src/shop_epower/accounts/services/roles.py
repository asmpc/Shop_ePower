def is_manager(user) -> bool:
    if not user.is_authenticated:
        return False

    return user.role in ["manager", "admin"]


def is_admin(user) -> bool:
    if not user.is_authenticated:
        return False

    return user.role == "admin"


def is_client(user) -> bool:
    if not user.is_authenticated:
        return True

    return user.role == "client"