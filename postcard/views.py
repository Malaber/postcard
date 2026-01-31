from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .models import Frame, Photo


@login_required
def upload_view(request, frame_id):
    # 1. Get the frame, but ONLY if the current user owns it
    # This is a crucial security check!
    frame = get_object_or_404(Frame, id=frame_id, owner=request.user)

    if request.method == 'POST':
        # 2. Get the list of files
        images = request.FILES.getlist('images')

        # 3. Save each one
        for image in images:
            Photo.objects.create(
                frame=frame,
                image=image,
                caption=""  # We can add caption logic later if needed
            )

        # 4. Success message or redirect
        return redirect('home')

    return render(request, 'upload.html', {'frame': frame})


def home_view(request):
    context = {}

    if request.user.is_authenticated:
        # Fetch frames owned by this user
        # 'related_name="frames"' in your model allows user.frames.all()
        frames = request.user.frames.all().order_by('-created_at')
        context['frames'] = frames

    return render(request, 'home.html', context)
