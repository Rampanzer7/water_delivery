from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.views.decorators.debug import sensitive_variables

UserModel = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authentication backend that permits users to authenticate using either
    their username or their registered email address.
    """
    @sensitive_variables('password')
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD) or kwargs.get('email')
        if not username or not password:
            return None

        clean_username = username.strip()
        if not clean_username:
            return None

        # Look up candidate users by case-insensitive username or email
        users = list(UserModel.objects.filter(
            Q(username__iexact=clean_username) | Q(email__iexact=clean_username)
        ))

        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        if not users:
            UserModel().set_password(password)

        return None
