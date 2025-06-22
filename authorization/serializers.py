import base64
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.contrib.auth.hashers import check_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'created_at')
        extra_kwargs = {'password': {'write_only': True}}
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.is_staff = False
        user.is_superuser = False
        user.is_active = False  
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField()  
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        login = attrs.get('login')
        password = attrs.get('password')
        
        if not login:
            raise serializers.ValidationError('Login is required')
        
        if not password:
            raise serializers.ValidationError('Password is required')
        
        user = authenticate(username=login, password=password)
        
        if not user and '@' in login:
            try:
                user_obj = User.objects.get(email=login)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if not user:
            raise serializers.ValidationError('Invalid credentials')
        
        attrs['user'] = user
        return attrs
    
    def get_tokens(self):
        user = self.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_staff': user.is_staff,
            }
        }


class EmailVerificationSendSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            if user.is_active:
                raise serializers.ValidationError('Email already confirmed')
            return value
        except User.DoesNotExist:
            return value
    
    def send_verification_email(self):
        email = self.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            token = default_token_generator.make_token(user)
            email_encoded = base64.urlsafe_b64encode(email.encode()).decode()
            verification_url = f"{settings.FRONTEND_URL}/verify-email/{email_encoded}/{token}/"
            
            subject = 'Email address confirmation'
            message = f'''
Hello dear {user.username}!

Thank you for registering! To complete registration, please confirm your email address.

Follow the link below:
{verification_url}

If you have not registered on our website, simply ignore this email.

The link is valid for 24 hours.

Token: {token}
            '''
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return True
            
        except User.DoesNotExist:
            return True
        except Exception as e:
            raise serializers.ValidationError(f'Error sending email: {str(e)}')


class EmailVerificationConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        token = attrs.get('token')
        
        try:
            user = User.objects.get(email=email)
            
            if not default_token_generator.check_token(user, token):
                raise serializers.ValidationError('Invalid or outdated token')
            
            attrs['user'] = user
            return attrs
            
        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist')
    
    def confirm_email(self):
        user = self.validated_data['user']
        user.is_active = True
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def send_reset_email(self):
        email = self.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            token = default_token_generator.make_token(user)
            email_encoded = base64.urlsafe_b64encode(email.encode()).decode()
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{email_encoded}/{token}/"
            
            subject = 'Password recovery'
            message = f'''
Hello dear {user.username}!

You have requested a password reset. Please follow the link below:
{reset_url}

If you did not request a password reset, simply ignore this email.

The link is valid for 1 hour.

Token: {token}
            '''
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return True
            
        except User.DoesNotExist:
            return True
        except Exception as e:
            raise serializers.ValidationError(f'Error sending email: {str(e)}')


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        token = attrs.get('token')
        new_password = attrs.get('new_password')
        
        try:
            user = User.objects.get(email=email)
            
            if not default_token_generator.check_token(user, token):
                raise serializers.ValidationError('Invalid or outdated token')

            if user.check_password(new_password):
                raise serializers.ValidationError('Your password should be different')
            
            attrs['user'] = user
            return attrs
            
        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist')
    
    def reset_password(self):
        user = self.validated_data['user']
        new_password = self.validated_data['new_password']
        
        user.set_password(new_password)
        user.save()
        return user