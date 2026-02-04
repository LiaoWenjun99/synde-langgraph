"""Authentication views."""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from synde_web.models import User


@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'index')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'synde_web/auth/login.html')


@csrf_protect
@require_http_methods(["GET", "POST"])
def signup_view(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        # Validation
        errors = []

        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')

        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')

        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')

        if password != password_confirm:
            errors.append('Passwords do not match.')

        if User.objects.filter(username=username).exists():
            errors.append('Username already taken.')

        if User.objects.filter(email=email).exists():
            errors.append('Email already registered.')

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('index')

    return render(request, 'synde_web/auth/signup.html')


@login_required
def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def profile_view(request):
    """User profile view."""
    user = request.user

    if request.method == 'POST':
        # Update profile
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.bio = request.POST.get('bio', '')
        user.organization = request.POST.get('organization', '')
        user.theme = request.POST.get('theme', 'system')

        # Handle avatar upload
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']

        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')

    context = {
        'user': user,
        'usage_percent': (user.current_usage / user.monthly_quota * 100) if user.monthly_quota > 0 else 0,
    }

    return render(request, 'synde_web/auth/profile.html', context)
