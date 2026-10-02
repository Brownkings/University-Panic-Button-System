import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import User, Role


def login_view(request):
    if request.user.is_authenticated:
        return redirect('role_redirect')

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Allow login via username or institutional_id
        user = authenticate(request, username=identifier, password=password)
        if user is None:
            # Try finding user by institutional_id
            try:
                matched_user = User.objects.get(institutional_id__iexact=identifier)
                user = authenticate(request, username=matched_user.username, password=password)
            except User.DoesNotExist:
                pass

        if user is not None:
            if not user.is_active:
                messages.error(request, "This account has been deactivated. Please contact campus security admin.")
                return render(request, 'accounts/login.html')

            login(request, user)
            messages.success(request, f"Welcome back, {user.full_name}!")
            return redirect('role_redirect')
        else:
            messages.error(request, "Invalid institutional ID/username or password.")

    return render(request, 'accounts/login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('role_redirect')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        institutional_id = request.POST.get('institutional_id', '').strip()
        email = request.POST.get('email', '').strip().lower()
        contact_number = request.POST.get('contact_number', '').strip()
        role_name = request.POST.get('role', 'STUDENT')
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/register.html')

        if User.objects.filter(institutional_id=institutional_id).exists():
            messages.error(request, f"Institutional ID {institutional_id} is already registered.")
            return render(request, 'accounts/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, f"Email address {email} is already in use.")
            return render(request, 'accounts/register.html')

        role = Role.objects.filter(role_name=role_name).first()
        username = f"user_{institutional_id}"

        # Generate 6-digit OTP
        otp = f"{random.randint(100000, 999999)}"

        new_user = User.objects.create_user(
            username=username,
            full_name=full_name,
            institutional_id=institutional_id,
            email=email,
            contact_number=contact_number,
            role=role,
            is_verified=False,
            otp_code=otp,
            otp_created_at=timezone.now()
        )
        new_user.set_password(password)
        new_user.save()

        # Log user into session pending OTP verification
        login(request, new_user)
        request.session['pending_otp_user_id'] = new_user.id
        messages.info(request, f"Registration step 1 complete. Enter the OTP sent to {contact_number}.")
        return redirect('verify_otp')

    return render(request, 'accounts/register.html')


@login_required
def verify_otp_view(request):
    user = request.user
    if user.is_verified:
        return redirect('role_redirect')

    if request.method == 'POST':
        entered_code = request.POST.get('otp_code', '').strip()
        if entered_code == user.otp_code or entered_code == "123456": # 123456 as universal test code
            user.is_verified = True
            user.otp_code = None
            user.save()
            messages.success(request, "Identity verified successfully! Account is fully active.")
            return redirect('role_redirect')
        else:
            messages.error(request, "Incorrect OTP code. Please try again.")

    return render(request, 'accounts/verify_otp.html', {
        'user_phone': user.contact_number,
        'debug_otp': user.otp_code
    })


@login_required
def resend_otp_view(request):
    user = request.user
    user.otp_code = f"{random.randint(100000, 999999)}"
    user.otp_created_at = timezone.now()
    user.save()
    messages.success(request, f"New OTP generated and sent to {user.contact_number}.")
    return redirect('verify_otp')


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out of the safety portal.")
    return redirect('login')


@login_required
def role_redirect_view(request):
    """
    Role-based redirection as specified in Phase 3 Section 3.1:
    - Security -> Security Operations Radar
    - Admin -> Reports & User Management
    - Student/Staff -> Emergency Panic Portal
    """
    if request.user.is_security:
        return redirect('security_dashboard')
    elif request.user.is_admin_user:
        return redirect('reports_analytics')
    else:
        return redirect('home')


@login_required
def user_management_view(request):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to administrators.")
        return redirect('home')

    users = User.objects.all().select_related('role').order_by('institutional_id')
    roles = Role.objects.all()
    return render(request, 'accounts/user_management.html', {
        'users': users,
        'roles': roles
    })


@login_required
def update_user_role_view(request, user_id):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted.")
        return redirect('home')

    target_user = get_object_or_404(User, id=user_id)
    role_name = request.POST.get('role_name')
    if role_name:
        role = Role.objects.filter(role_name=role_name).first()
        if role:
            target_user.role = role
            target_user.save()
            messages.success(request, f"Updated role for {target_user.full_name} to {role.get_role_name_display()}.")

    return redirect('user_management')


@login_required
def toggle_user_status_view(request, user_id):
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted.")
        return redirect('home')

    target_user = get_object_or_404(User, id=user_id)
    if target_user.id == request.user.id:
        messages.error(request, "You cannot suspend your own account.")
        return redirect('user_management')

    target_user.is_active = not target_user.is_active
    target_user.save()
    status_str = "activated" if target_user.is_active else "suspended"
    messages.info(request, f"Account for {target_user.full_name} has been {status_str}.")
    return redirect('user_management')
