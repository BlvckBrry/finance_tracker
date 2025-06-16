from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
import base64

User = get_user_model()

class RegisterView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        usernameOrEmail = request.data.get('username') or request.data.get('email')
        password = request.data.get('password')
        
        if usernameOrEmail and password:
            user = authenticate(username=usernameOrEmail, password=password)

            if not user:
                try:
                    user_by_email = User.objects.get(email=usernameOrEmail)
                    user = authenticate(username=user_by_email.username, password=password)
                except User.DoesNotExist:
                    user = None
            
            if user:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_staff': user.is_staff,
                    }
                }, status=status.HTTP_200_OK)

            else:
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response({
                'error': 'Username/email and password required'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserListView(APIView):
    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)

        return Response(serializer.data)
        

class UserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)

        return Response(serializer.data)


class EmailVerificationSendView(APIView):
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                return Response({
                    'message': 'Email already confirmed'
                }, status=status.HTTP_200_OK)
            
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
            return Response({
                'message': 'Email confirmation instructions have been sent to your email.'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'message': 'If such an email exists, instructions have been sent to the email.'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Email verification error: {str(e)}") 
            return Response({
                'error': f'Error sending email: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmailVerificationConfirmView(APIView):
    def post(self, request):
        token = request.data.get('token')
        email = request.data.get('email')
        if not all([token, email]):
            return Response({
                'error': 'Email and token required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            if default_token_generator.check_token(user, token):
                user.is_active = True
                user.save()
                return Response({
                    'message': 'Email successfully confirmed'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid or outdated token'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({
                'error': 'User with this email does not exist.'
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'error': 'Error while confirming email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordResetRequestView(APIView):
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
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
            
            return Response({
                'message': 'Password recovery instructions have been sent to your email.'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'message': 'If such an email exists, instructions have been sent to the email.'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Error sending email: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordResetConfirmView(APIView):
    def post(self, request):
        email = request.data.get('email')
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        if not all([email, token, new_password]):
            return Response({
                'error': 'Email, token and new password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            if default_token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response({
                    'message': 'Password changed successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid or outdated token'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({
                'error': 'User with this email does not exist.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'error': 'Error while changing password'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)