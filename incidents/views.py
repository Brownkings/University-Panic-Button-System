import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import IncidentReport


ALLOWED_EVIDENCE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov', '.pdf', '.webp', '.doc', '.docx'}


@login_required
def incident_create_view(request):
    """
    Data Entry Forms Interface (Phase 3 Section 3.1 & Iteration 2):
    Features green save button (#10b981) positioned top-right, media uploads, and form validation.
    """
    if request.method == 'POST':
        category = request.POST.get('category', IncidentReport.CATEGORY_OTHER)
        location_name = request.POST.get('location_name', '').strip()
        description = request.POST.get('description', '').strip()
        media_file = request.FILES.get('media_file')

        if not location_name or not description:
            messages.error(request, "Please fill in all required fields (location and description).")
            return render(request, 'incidents/report_form.html', {
                'user_reports': IncidentReport.objects.filter(user=request.user).order_by('-created_at')
            })

        # File validation: Size (Max 10MB) and extension safety
        if media_file:
            if media_file.size > 10 * 1024 * 1024:
                messages.error(request, "Uploaded file exceeds the maximum limit of 10 MB.")
                return render(request, 'incidents/report_form.html', {
                    'user_reports': IncidentReport.objects.filter(user=request.user).order_by('-created_at')
                })
            ext = os.path.splitext(media_file.name)[1].lower()
            if ext not in ALLOWED_EVIDENCE_EXTENSIONS:
                messages.error(request, f"Unsupported file type ({ext}). Allowed formats: images (JPG, PNG, GIF, WEBP), videos (MP4, MOV), and documents (PDF, DOC).")
                return render(request, 'incidents/report_form.html', {
                    'user_reports': IncidentReport.objects.filter(user=request.user).order_by('-created_at')
                })

        report = IncidentReport.objects.create(
            user=request.user,
            category=category,
            location_name=location_name,
            description=description,
            media_file=media_file
        )

        messages.success(request, f"Incident Report #{report.id} successfully recorded! Campus security has been notified.")
        return redirect('incident_create')

    user_reports = IncidentReport.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'incidents/report_form.html', {
        'user_reports': user_reports
    })


@login_required
def incident_detail_view(request, report_id):
    report = get_object_or_404(IncidentReport, id=report_id)
    if report.user != request.user and not (request.user.is_security or request.user.is_admin_user):
        messages.error(request, "Access unauthorized.")
        return redirect('incident_create')

    return render(request, 'incidents/report_detail.html', {'report': report})
