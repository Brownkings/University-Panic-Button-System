import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from .models import User, Role
from .email_service import send_account_verification_email, send_password_reset_email


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

        # Dispatch verification email via Resend
        send_account_verification_email(new_user, otp_code=otp, request=request)

        # Log user into session pending OTP verification
        login(request, new_user)
        request.session['pending_otp_user_id'] = new_user.id
        messages.info(request, f"Registration step 1 complete. Verification code sent to {email} and {contact_number}.")
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
        'user_email': user.email,
        'debug_otp': user.otp_code
    })


@login_required
def resend_otp_view(request):
    user = request.user
    new_otp = f"{random.randint(100000, 999999)}"
    user.otp_code = new_otp
    user.otp_created_at = timezone.now()
    user.save()
    send_account_verification_email(user, otp_code=new_otp, request=request)
    messages.success(request, f"New verification code sent to {user.email} and {user.contact_number}.")
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
    Mobile APK is strictly locked to Student Portal.
    """
    ua = request.META.get('HTTP_USER_AGENT', '')
    if 'UPBSStudentPortal' in ua or request.headers.get('X-UPBS-Client') == 'StudentPortal':
        return redirect('home')

    if request.user.is_security:
        return redirect('security_dashboard')
    elif request.user.is_admin_user:
        return redirect('reports_analytics')
    else:
        return redirect('home')


@login_required
def user_management_view(request):
    ua = request.META.get('HTTP_USER_AGENT', '')
    if 'UPBSStudentPortal' in ua or request.headers.get('X-UPBS-Client') == 'StudentPortal':
        return redirect('home')

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


@login_required
def admin_create_user_view(request):
    """
    Allows campus safety administrators to directly provision student or staff accounts.
    Newly provisioned users are immediately active and verified.
    Optionally dispatches a password setup email via Resend.
    """
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to administrators.")
        return redirect('home')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        institutional_id = request.POST.get('institutional_id', '').strip()
        email = request.POST.get('email', '').strip().lower()
        contact_number = request.POST.get('contact_number', '').strip()
        role_name = request.POST.get('role', 'STUDENT')
        initial_password = request.POST.get('password', '').strip()
        send_reset = request.POST.get('send_reset') == '1'

        if not full_name or not institutional_id or not email or not contact_number:
            messages.error(request, "Please fill in all required institutional profile fields.")
            return redirect('user_management')

        if User.objects.filter(institutional_id=institutional_id).exists():
            messages.error(request, f"Institutional ID {institutional_id} already exists in directory.")
            return redirect('user_management')

        if User.objects.filter(email=email).exists():
            messages.error(request, f"Institutional email {email} already exists.")
            return redirect('user_management')

        if not initial_password:
            initial_password = f"CampusSafe@{random.randint(1000, 9999)}"

        role = Role.objects.filter(role_name=role_name).first()
        username = f"user_{institutional_id}"

        new_user = User.objects.create_user(
            username=username,
            full_name=full_name,
            institutional_id=institutional_id,
            email=email,
            contact_number=contact_number,
            role=role,
            is_verified=True,
            is_active=True
        )
        new_user.set_password(initial_password)
        new_user.save()

        if send_reset:
            send_password_reset_email(new_user, request=request)
            messages.success(request, f"Student/Staff {new_user.full_name} ({institutional_id}) provisioned successfully! Password setup email dispatched via Resend.")
        else:
            messages.success(request, f"Student/Staff {new_user.full_name} ({institutional_id}) provisioned with temporary password: {initial_password}")

        return redirect('user_management')

    return redirect('user_management')


@login_required
def admin_send_reset_email_view(request, user_id):
    """
    Enables administrators to send a password reset link to any registered student or staff member via Resend.
    """
    if not request.user.is_admin_user:
        messages.error(request, "Access restricted to administrators.")
        return redirect('home')

    target_user = get_object_or_404(User, id=user_id)
    if target_user.email:
        send_password_reset_email(target_user, request=request)
        messages.success(request, f"Password reset email dispatched to {target_user.email} via Resend.")
    else:
        messages.error(request, f"User {target_user.full_name} has no institutional email address on file.")

    return redirect('user_management')


def verify_email_link_view(request, uidb64, token):
    """
    Allows user to verify account by clicking the secure link in the email.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_verified = True
        user.otp_code = None
        user.save()
        login(request, user)
        messages.success(request, "Your email and campus identity have been verified successfully!")
        return redirect('role_redirect')
    else:
        messages.error(request, "The verification link is invalid or has expired.")
        return redirect('login')


def password_reset_view(request):
    """
    Accepts student/staff institutional ID or email to initiate password recovery.
    Sends reset link via Resend.
    """
    if request.user.is_authenticated:
        return redirect('role_redirect')

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        matched_user = None

        if '@' in identifier:
            matched_user = User.objects.filter(email__iexact=identifier).first()
        else:
            matched_user = User.objects.filter(institutional_id__iexact=identifier).first()
            if not matched_user:
                matched_user = User.objects.filter(username__iexact=identifier).first()

        target_email = ""
        if matched_user and matched_user.email:
            send_password_reset_email(matched_user, request=request)
            parts = matched_user.email.split('@')
            if len(parts) == 2 and len(parts[0]) > 2:
                target_email = f"{parts[0][0]}***{parts[0][-1]}@{parts[1]}"
            else:
                target_email = matched_user.email

        request.session['reset_target_email'] = target_email
        return redirect('password_reset_done')

    return render(request, 'accounts/password_reset.html')


def password_reset_done_view(request):
    target_email = request.session.pop('reset_target_email', None)
    return render(request, 'accounts/password_reset_done.html', {
        'target_email': target_email
    })


def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    validlink = bool(user is not None and default_token_generator.check_token(user, token))

    if not validlink:
        return render(request, 'accounts/password_reset_confirm.html', {'validlink': False})

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, 'accounts/password_reset_confirm.html', {'validlink': True, 'user': user})

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/password_reset_confirm.html', {'validlink': True, 'user': user})

        user.set_password(new_password)
        user.is_active = True
        user.save()
        messages.success(request, "Your password has been successfully reset. Please log in with your new credentials.")
        return redirect('password_reset_complete')

    return render(request, 'accounts/password_reset_confirm.html', {'validlink': True, 'user': user})


def password_reset_complete_view(request):
    return render(request, 'accounts/password_reset_complete.html')
