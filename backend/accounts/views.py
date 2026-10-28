import logging

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from notifications.sms import SMSError

from . import password_reset
from .models import User
from .permissions import HasBusiness, IsOwner, IsOwnerOrReadOnly
from .serializers import (
    BusinessSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    StaffSerializer,
    UserSerializer,
    tokens_for,
)

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    """Create a new business together with its owner account, and log the owner in."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'user': UserSerializer(user).data, **tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class BusinessView(generics.RetrieveUpdateAPIView):
    serializer_class = BusinessSerializer
    permission_classes = [HasBusiness, IsOwnerOrReadOnly]

    def get_object(self):
        return self.request.user.business


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        return Response({'detail': 'Password changed.'})


class PasswordResetRequestView(APIView):
    """Forgot password, step 1: text a 6-digit code to the phone number."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            simulated_code = password_reset.request_code(serializer.validated_data['phone'])
        except SMSError:
            logger.exception('Password reset SMS failed')
            return Response(
                {'detail': 'We could not send the SMS right now. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        # The same answer whether or not the number has an account
        answer = {'detail': 'If this number has an account, a code has been sent by SMS.'}
        if simulated_code:
            # Only on a developer's computer without SMS keys (see notifications.sms.is_simulated)
            answer['simulated_code'] = simulated_code
        return Response(answer)


class PasswordResetConfirmView(APIView):
    """Forgot password, step 2: the code from the SMS and the new password."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            password_reset.reset_password(**serializer.validated_data)
        except password_reset.InvalidCode:
            return Response(
                {'code': ['This code is wrong or has expired. Ask for a new one.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'detail': 'Password changed. You can now log in.'})


class StaffListCreateView(generics.ListCreateAPIView):
    serializer_class = StaffSerializer
    permission_classes = [HasBusiness, IsOwner]
    pagination_class = None

    def get_queryset(self):
        return User.objects.filter(business=self.request.user.business).order_by('date_joined')

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.business)


class StaffDeleteView(generics.DestroyAPIView):
    permission_classes = [HasBusiness, IsOwner]

    def get_queryset(self):
        # Owners can remove staff, but never themselves
        return User.objects.filter(business=self.request.user.business, role=User.Role.STAFF)
