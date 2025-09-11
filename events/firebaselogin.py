from oauth2_provider.oauth2_validators import OAuth2Validator
from google.oauth2 import id_token
from google.auth.transport import requests
from django.contrib.auth import get_user_model
from firebase_admin import auth

class FirebaseOAuth2Validator(OAuth2Validator):
    def validate_grant_type(self, grant_type, client, request, *args, **kwargs):
        # Cho phép grant_type=firebase
        if grant_type == 'firebase':
            return True
        return super().validate_grant_type(grant_type, client, request, *args, **kwargs)

    def authenticate_client(self, request, *args, **kwargs):
        # Bỏ qua xác thực client_id/client_secret nếu muốn đơn giản
        return True

    def validate_user(self, request, *args, **kwargs):
        token = request.extra_credentials.get('token')
        try:
            decoded_token = auth.verify_id_token(token)
            email = decoded_token.get('email')
            name = decoded_token.get('name', '')
            User = get_user_model()
            user, _ = User.objects.get_or_create(
                username=email,
                defaults={'email': email, 'first_name': name, 'role': 'attendee'}
            )
            request.user = user
            return True
        except Exception as e:
            print("Firebase token verify failed:", e)
            return False
