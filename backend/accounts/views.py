from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .permissions import HasBusiness, IsOwner, IsOwnerOrReadOnly
from .serializers import (
    BusinessSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    StaffSerializer,
    UserSerializer,
    tokens_for,
)


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
