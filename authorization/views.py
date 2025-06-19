from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import (
    UserSerializer,
    LoginSerializer,
    EmailVerificationSendSerializer,
    EmailVerificationConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)

User = get_user_model()

class RegisterView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            tokens_data = serializer.get_tokens()
            return Response(tokens_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)


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

class UserDeleteView(APIView):
    def delete(self, request):
        username = request.data.get('username')

        try:
            user = User.objects.get(username=username)
        
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        user.delete()

        return Response({'message': 'User deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


class EmailVerificationSendView(APIView):
    def post(self, request):
        serializer = EmailVerificationSendSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.send_verification_email()
                return Response({
                    'message': 'Email confirmation instructions have been sent to your email.'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailVerificationConfirmView(APIView):
    def post(self, request):
        serializer = EmailVerificationConfirmSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.confirm_email()
                return Response({
                    'message': 'Email successfully confirmed'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'error': 'Error while confirming email'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.send_reset_email()
                return Response({
                    'message': 'Password recovery instructions have been sent to your email.'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.reset_password()
                return Response({
                    'message': 'Password changed successfully'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'error': 'Error while changing password'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)