from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.openapi import AutoSchema

from apps.users.serializers import (
    RegisterSerializer,
    CustomTokenObtainPairSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        summary="Register a new user",
        description="Create a new user account with email and password.",
        request=RegisterSerializer,
        responses={201: UserSerializer},
        examples=[
            OpenApiExample(
                'Register Example',
                value={
                    'email': 'user@example.com',
                    'username': 'myusername',
                    'password': 'StrongPass123!',
                    'password2': 'StrongPass123!',
                },
                request_only=True,
            )
        ],
        tags=['Auth'],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'success': True, 'data': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="Login",
        description="Login with email and password. Returns access and refresh JWT tokens.",
        request=CustomTokenObtainPairSerializer,
        examples=[
            OpenApiExample(
                'Login Example',
                value={
                    'email': 'user@example.com',
                    'password': 'StrongPass123!',
                },
                request_only=True,
            )
        ],
        tags=['Auth'],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {'success': True, 'data': serializer.validated_data},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Logout",
        description="Blacklist the refresh token to log the user out.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'refresh': {
                        'type': 'string',
                        'description': 'The refresh token to blacklist',
                    }
                },
                'required': ['refresh'],
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'message': {'type': 'string'}
                        }
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Logout Example',
                value={'refresh': 'your-refresh-token-here'},
                request_only=True,
            )
        ],
        tags=['Auth'],
    )
    def post(self, request):
        try:
            refresh_token = request.data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {'success': True, 'data': {'message': 'Logged out successfully.'}},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {'success': False, 'error': {'code': 400, 'message': 'Invalid token.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )