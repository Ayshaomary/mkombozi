import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from notifications.mail import EmailError
from notifications.sms import SMSError

from . import password_reset, photos
from .models import Avatar, Logo, User
from .permissions import HasBusiness, IsOwner, IsOwnerOrReadOnly
from .serializers import (
    BusinessSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PhotoSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    StaffAccessSerializer,
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


class MyPhotoView(APIView):
    """PUT a new profile photo as {"image": "data:image/jpeg;base64,..."}, or DELETE it."""

    def put(self, request):
        serializer = PhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photos.set_photo(request.user, *serializer.validated_data['image'])
        return Response(UserSerializer(request.user).data)

    def delete(self, request):
        photos.remove_photo(request.user)
        return Response(UserSerializer(request.user).data)


@require_GET
def avatar_image(request, key):
    """A profile photo. Public, so <img> tags can show it; the key is long and random."""
    avatar = get_object_or_404(Avatar.objects.only('image', 'content_type'), key=key)
    response = HttpResponse(bytes(avatar.image), content_type=avatar.content_type)
    # A new photo gets a new key, so this one never changes and browsers may keep it
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


class BusinessView(generics.RetrieveUpdateAPIView):
    serializer_class = BusinessSerializer
    permission_classes = [HasBusiness, IsOwnerOrReadOnly]

    def get_object(self):
        return self.request.user.business


class BusinessLogoView(APIView):
    """PUT a new business logo as {"image": "data:image/png;base64,..."}, or DELETE it. Owner only."""

    permission_classes = [HasBusiness, IsOwner]

    def put(self, request):
        serializer = PhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photos.set_logo(request.user.business, *serializer.validated_data['image'])
        return Response(BusinessSerializer(request.user.business).data)

    def delete(self, request):
        photos.remove_logo(request.user.business)
        return Response(BusinessSerializer(request.user.business).data)


@require_GET
def logo_image(request, key):
    """A business logo. Public like profile photos, for the same reason."""
    logo = get_object_or_404(Logo.objects.only('image', 'content_type'), key=key)
    response = HttpResponse(bytes(logo.image), content_type=logo.content_type)
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        return Response({'detail': 'Password changed.'})


class PasswordResetRequestView(APIView):
    """Forgot password, step 1: send a 6-digit code to the user's email, or by SMS to the phone number."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            simulated_code = password_reset.request_code(serializer.validated_data['phone'])
        except (SMSError, EmailError):
            logger.exception('Password reset code could not be sent')
            return Response(
                {'detail': 'We could not send the code right now. Please try again later, '
                           'or ask the SAVIOR team to reset your password.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        # The same answer whether or not the number has an account
        answer = {'detail': 'If this number has an account, a code has been sent by SMS or email.'}
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


class StaffDetailView(generics.UpdateAPIView, generics.DestroyAPIView):
    """PATCH {"permissions": [...]} to choose what a staff member may do, or DELETE to remove them."""

    serializer_class = StaffAccessSerializer
    permission_classes = [HasBusiness, IsOwner]
    http_method_names = ['patch', 'delete']

    def get_queryset(self):
        # Owners can remove staff, but never themselves
        return User.objects.filter(business=self.request.user.business, role=User.Role.STAFF)
