from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from django.urls import reverse
from django.views.generic.edit import DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Frame, Photo
from .api import normalized_image


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

        try:
            normalized = [normalized_image(image) for image in images]
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, 'upload.html', {'frame': frame}, status=400)
        for image in normalized:
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

def frame_kiosk(request, token):
    """
    Public view for the physical frame.
    Access is controlled ONLY by the secret token.
    """
    # 1. Look up frame by the secret token
    frame = get_object_or_404(Frame, access_token=token)

    return render(request, 'kiosk.html', {
        'frame': frame,
    })


def frame_photos_json(request, token):
    """
    API: Returns a JSON list of all photo URLs for this frame.
    Used by the Kiosk JS to sync its local cache.
    """
    frame = get_object_or_404(Frame, access_token=token)
    photos = frame.photos.filter(is_active=True)

    data = {
        "name": frame.name,
        "photos": [reverse("viewer_photo", args=[frame.access_token, p.id]) for p in photos]
    }
    response = JsonResponse(data)
    response["Cache-Control"] = "no-store"
    return response

def home_view(request):
    context = {}

    if request.user.is_authenticated:
        # Fetch frames owned by this user
        # 'related_name="frames"' in your model allows user.frames.all()
        frames = request.user.frames.all().order_by('-created_at')
        context['frames'] = frames

    return render(request, 'home.html', context)


class PhotoDeleteView(LoginRequiredMixin, DeleteView):
    model = Photo
    template_name = 'delete_photo.html'
    context_object_name = 'photo'

    def get_queryset(self):
        """
        Security: Only allow finding/deleting photos that belong
        to frames owned by the current logged-in user.
        """
        return Photo.objects.filter(frame__owner=self.request.user)

    def get_success_url(self):
        """
        After deleting, go back to the Frame Detail page.
        """
        # self.object is the photo that was just deleted (Django keeps a reference)
        return reverse('frame_detail', kwargs={'frame_id': self.object.frame.id})

