from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Frame, Photo


@login_required
def frame_detail(request, frame_id):
    """
    Acts as the File Manager for a specific frame.
    """
    frame = get_object_or_404(Frame, id=frame_id, owner=request.user)
    photos = frame.photos.all()  # Ordered by newest first (defined in Meta)

    # Check for 'new' param in URL to highlight specific photos
    new_ids = request.GET.get('new', '').split(',')

    return render(request, 'frame_detail.html', {
        'frame': frame,
        'photos': photos,
        'new_ids': new_ids
    })


@login_required
def upload_view(request, frame_id):
    frame = get_object_or_404(Frame, id=frame_id, owner=request.user)

    if request.method == 'POST':
        images = request.FILES.getlist('images')
        new_photo_ids = []

        for image in images:
            photo = Photo.objects.create(
                frame=frame,
                image=image,
                caption=""
            )
            # Collect the ID (converted to string)
            new_photo_ids.append(str(photo.id))

        # Add a nice banner message
        messages.success(request, f"Successfully uploaded {len(images)} photos.")

        # Create a comma-separated string of IDs: "uuid1,uuid2,uuid3"
        id_string = ",".join(new_photo_ids)

        # Redirect to detail view with the query param
        return redirect(f"/p/frame/{frame.id}/?new={id_string}")

    return render(request, 'upload.html', {'frame': frame})


def home_view(request):
    context = {}

    if request.user.is_authenticated:
        # Fetch frames owned by this user
        # 'related_name="frames"' in your model allows user.frames.all()
        frames = request.user.frames.all().order_by('-created_at')
        context['frames'] = frames

    return render(request, 'home.html', context)
