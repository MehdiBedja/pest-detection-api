import json
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from .serializers import *
from .models import *
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
# Add to your views.py
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests
from django.conf import settings
# from . import privileges


User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])  # Allow anyone to access
def signup(request):
    user_type = request.data.get('user_type')
    user_data = request.data.get('user')

    # Validate user_type
    if user_type not in ['client', 'administrator']:
        return Response({'error': 'Invalid user_type'}, status=status.HTTP_400_BAD_REQUEST)

    # Create user and related model based on user_type
    serializer = UserSerializer(data=user_data)
    if serializer.is_valid():
        user = serializer.save()

        if user_type == 'client':
            Client.objects.create(user=user)
        elif user_type == 'administrator':
            Administrator.objects.create(user=user)

        # Return success with the full user object
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if username is None or password is None:
        return Response({'error': 'Please provide both username/email and password'}, status=status.HTTP_400_BAD_REQUEST)

    user = CustomUser.objects.filter(username=username).first()

    if user is None:
        return Response({'error': 'User does not exist'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.check_password(password):
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    if user:
        token, _ = Token.objects.get_or_create(user=user)
        serializer = UserSerializer(user)  # Serialize user data
        return Response({'token': token.key, 'user': serializer.data}, status=status.HTTP_200_OK)
    else:
        return Response({'error': 'Invalid credentials'}, status=HTTP_400_BAD_REQUEST)




    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    token = request.META.get('HTTP_AUTHORIZATION').split()[1]
    user = Token.objects.get(key=token).user
    serializer = UserSerializer(user)
    return Response(serializer.data)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_user_detail(request, id):
    try:
        user = CustomUser.objects.get(pk=id)
    except CustomUser.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = CustomUserSerializer2(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change password for regular users (non-Google users)
    Requires both old and new password
    """
    try:
        data = json.loads(request.body)
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        if not old_password or not new_password:
            return Response({
                'success': False,
                'message': 'Both old and new passwords are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # Check if user is a Google user (has no password set)
        if not user.has_usable_password():
            return Response({
                'success': False,
                'message': 'Google users should use set password endpoint'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify old password
        if not user.check_password(old_password):
            return Response({
                'success': False,
                'message': 'Current password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate new password (you can add more validation here)
        if len(new_password) < 8:
            return Response({
                'success': False,
                'message': 'New password must be at least 8 characters long'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        return Response({
            'success': True,
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)
        
    except json.JSONDecodeError:
        return Response({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_password(request):
    """
    Set password for Google users who don't have a password yet
    Only requires new password
    """
    try:
        data = json.loads(request.body)
        new_password = data.get('new_password')
        
        if not new_password:
            return Response({
                'success': False,
                'message': 'New password is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # Check if user already has a password set
        if user.has_usable_password():
            return Response({
                'success': False,
                'message': 'User already has a password. Use change password endpoint instead.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate new password (you can add more validation here)
        if len(new_password) < 8:
            return Response({
                'success': False,
                'message': 'Password must be at least 8 characters long'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set password for Google user
        user.set_password(new_password)
        user.save()
        
        return Response({
            'success': True,
            'message': 'Password set successfully'
        }, status=status.HTTP_200_OK)
        
    except json.JSONDecodeError:
        return Response({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])  # Use POST method for logout
@permission_classes([IsAuthenticated])  # User must be authenticated to logout
def logout(request):
    user = request.user
    Token.objects.filter(user=user).delete()  # Delete the user's authentication token
    return Response({'message': 'Logged out successfully.'})

@api_view(['POST'])
@permission_classes([AllowAny])
def google_login(request):
    id_token_str = request.data.get('id_token')
    if not id_token_str:
        return Response({'error': 'No ID token provided.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Optionally, set audience to your Android client ID for extra security
        idinfo = id_token.verify_oauth2_token(id_token_str, google_requests.Request())
        email = idinfo.get('email')
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        picture = idinfo.get('picture', '')
    except Exception:
        return Response({'error': 'Invalid ID token.'}, status=status.HTTP_400_BAD_REQUEST)

    if not email:
        return Response({'error': 'No email found in token.'}, status=status.HTTP_400_BAD_REQUEST)

    user, created = CustomUser.objects.get_or_create(email=email, defaults={
        'username': email,
        'first_name': first_name,
        'last_name': last_name,
        'profile_picture': picture,
    })

    # If user was just created, you can set additional fields here if needed
    token, _ = Token.objects.get_or_create(user=user)
    serializer = UserSerializer(user)
    return Response({'token': token.key, 'user': serializer.data}, status=status.HTTP_200_OK)




# Add to your views.py
@api_view(['POST'])
@permission_classes([AllowAny])  # Allow anyone to access
def google_signup(request):



    """
    Google OAuth signup endpoint
    Expected payload:
    {
        "id_token": "google_id_token_from_frontend",
        "user_type": "client" or "administrator"
    }
    """
    print("Raw request body:", request.body)
    print("Parsed data:", request.data)
    id_token_str = request.data.get('id_token')
    user_type = request.data.get('user_type')
    
    # Validate required fields
    if not id_token_str:
        return Response({'error': 'Google ID token is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if user_type not in ['client', 'administrator']:
        return Response({'error': 'Invalid user_type. Must be "client" or "administrator"'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Verify the Google ID token
        idinfo = id_token.verify_oauth2_token(
            id_token_str, 
            google_requests.Request(), 
            settings.GOOGLE_CLIENT_ID
        )
        
        # Extract user info from Google
        google_user_id = idinfo['sub']
        email = idinfo.get('email')
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        profile_picture = idinfo.get('picture', '')
        
        if not email:
            return Response({'error': 'Email not provided by Google'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user already exists
        existing_user = CustomUser.objects.filter(email=email).first()
        if existing_user:
            return Response({'error': 'User with this email already exists'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate username from email (you can modify this logic)
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create new user
        user_data = {
            'username': username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'profile_picture': profile_picture,
        }
        
        # Create user without password (Google auth)
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            profile_picture=profile_picture,
        )
        
        # Set unusable password since they're using Google auth
        user.set_unusable_password()
        user.save()
        
        # Create related model based on user_type
        if user_type == 'client':
            Client.objects.create(user=user)
        elif user_type == 'administrator':
            Administrator.objects.create(user=user)
        
        # Create token for the user
        token, created = Token.objects.get_or_create(user=user)
        
        # Serialize user data
        serializer = UserSerializer(user)
        
        return Response({
            'token': token.key,
            'user': serializer.data,
            'message': 'User created successfully with Google'
        }, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        # Invalid token
        return Response({'error': 'Invalid Google ID token'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': f'Google authentication failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['POST'])
@permission_classes([AllowAny])
def test_connection(request):
    print("✅ test_connection view was called!")

    try:

        id_token_str = request.data.get('id_token')
        user_type = request.data.get('user_type')

        print("user_type:", user_type)

        # Validate required fields
        if not id_token_str:
            return Response({'error': 'Google ID token is required'}, status=status.HTTP_400_BAD_REQUEST)

        if user_type not in ['client', 'administrator']:
            return Response({'error': 'Invalid user_type. Must be "client" or "administrator"'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify the Google ID token
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        # Extract user info from Google
        google_user_id = idinfo['sub']
        email = idinfo.get('email')
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        profile_picture = idinfo.get('picture', '')

        if not email:
            return Response({'error': 'Email not provided by Google'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already exists
        existing_user = CustomUser.objects.filter(email=email).first()
        if existing_user:
            return Response({'error': 'User with this email already exists'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate username from email
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Create new user
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            profile_picture=profile_picture,
        )
        user.set_unusable_password()
        user.save()

        # Create user type
        if user_type == 'client':
            Client.objects.create(user=user)
        elif user_type == 'administrator':
            Administrator.objects.create(user=user)

        # Create token
        token, _ = Token.objects.get_or_create(user=user)

        # Serialize user
        serializer = UserSerializer(user)

        return Response({
            'token': token.key,
            'user': serializer.data,
            'message': 'User created successfully with Google'
        }, status=status.HTTP_201_CREATED)

    except ValueError:
        return Response({'error': 'Invalid Google ID token'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': f'Google authentication failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    






@api_view(['POST'])
@permission_classes([AllowAny])
def google_sign_in(request):
    #print("✅ google_sign_in view was called!")
    #print(f"Raw request body: {request.body}")
    #print(f"Request data: {request.data}")
    #print(f"id_token in data: {'idtoken' in request.data}")

    try:
        id_token_str = request.data.get('idToken')
        if not id_token_str:
            return Response({'error': 'Google ID token is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify token
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        email = idinfo.get('email')
        if not email:
            return Response({'error': 'Email not found in Google token'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        user = CustomUser.objects.filter(email=email).first()
        if not user:
            return Response({'error': 'User does not exist. Please sign up first.'}, status=status.HTTP_404_NOT_FOUND)

        # Get or create token
        token, _ = Token.objects.get_or_create(user=user)

        serializer = UserSerializer(user)
        return Response({
            'token': token.key,
            'user': serializer.data,
            'message': 'Signed in successfully'
        }, status=status.HTTP_200_OK)

    except ValueError:
        return Response({'error': 'Invalid Google ID token'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': f'Google Sign-In failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_is_google_user(request):
    """
    Check if the authenticated user is a Google user
    Returns: {'is_google_user': boolean}
    """
    try:
        user = request.user
        return Response({
            'is_google_user': user.is_google_user,
            'has_usable_password': user.has_usable_password()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': f'Failed to check user type: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)