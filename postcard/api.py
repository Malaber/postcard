"""Owner-scoped native API. Browser sessions cannot authorize API mutations."""
import io
import mimetypes
import warnings
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.views.decorators.http import require_http_methods
from PIL import Image, ImageOps, UnidentifiedImageError
from accounts.mobile import bearer_required
from accounts.views import json_endpoint
from .models import Frame, Photo, generate_frame_token


def photo_json(request, photo):
    return {'id': str(photo.id), 'caption': photo.caption, 'is_active': photo.is_active,
            'image_url': request.build_absolute_uri(reverse('viewer_photo', args=[photo.frame.access_token, photo.id]))}


def frame_json(request, frame):
    return {'id': str(frame.id), 'name': frame.name,
            'viewer_url': request.build_absolute_uri(frame.get_viewer_url()),
            'photos': [photo_json(request, p) for p in frame.photos.all()]}


def name(data):
    value = data.get('name', '')
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
        raise ValueError('Viewer name must contain 1–100 characters')
    return value.strip()


@require_http_methods(['GET', 'POST'])
@bearer_required
@json_endpoint
def frames(request, data):
    if request.method == 'POST':
        frame = Frame.objects.create(owner=request.user, name=name(data))
        return JsonResponse(frame_json(request, frame), status=201)
    return JsonResponse({'frames': [frame_json(request, f) for f in
        request.user.frames.prefetch_related('photos').order_by('-created_at')]})


@require_http_methods(['PATCH', 'DELETE'])
@bearer_required
@json_endpoint
def frame_detail(request, data, frame_id):
    frame = get_object_or_404(Frame, id=frame_id, owner=request.user)
    if request.method == 'DELETE':
        frame.delete()
        return HttpResponse(status=204)
    frame.name = name(data)
    frame.save(update_fields=['name'])
    return JsonResponse(frame_json(request, frame))


@require_http_methods(['POST'])
@bearer_required
def rotate(request, frame_id):
    frame = get_object_or_404(Frame, id=frame_id, owner=request.user)
    frame.access_token = generate_frame_token()
    frame.save(update_fields=['access_token'])
    return JsonResponse(frame_json(request, frame))


def normalized_image(upload):
    if upload.size > 25 * 1024 * 1024:
        raise ValueError('Each photo must be under 25 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as image:
                if image.width * image.height > 40_000_000:
                    raise ValueError('Photo exceeds 40 megapixels.')
                image = ImageOps.exif_transpose(image)
                image.thumbnail((3840, 3840))
                output = io.BytesIO()
                image.convert('RGB').save(output, format='JPEG', quality=88)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Choose a valid JPEG, PNG or WebP image.') from exc
    # Re-encoding strips GPS/EXIF and rejects executable or mislabeled content.
    return ContentFile(output.getvalue(), name='photo.jpg')


@require_http_methods(['POST'])
@bearer_required
def upload(request, frame_id):
    frame = get_object_or_404(Frame, id=frame_id, owner=request.user)
    image = request.FILES.get('image')
    caption = request.POST.get('caption', '')
    if image is None or len(caption) > 255:
        return JsonResponse({'detail': 'Choose a photo and a caption up to 255 characters.'}, status=400)
    try:
        content = normalized_image(image)
    except ValueError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    photo = Photo.objects.create(frame=frame, image=content, caption=caption)
    return JsonResponse(photo_json(request, photo), status=201)


@require_http_methods(['PATCH', 'DELETE'])
@bearer_required
@json_endpoint
def photo_detail(request, data, photo_id):
    photo = get_object_or_404(Photo, id=photo_id, frame__owner=request.user)
    if request.method == 'DELETE':
        photo.delete()
        return HttpResponse(status=204)
    if 'caption' in data:
        if not isinstance(data['caption'], str) or len(data['caption']) > 255:
            raise ValueError('Invalid caption')
        photo.caption = data['caption']
    if 'is_active' in data:
        if not isinstance(data['is_active'], bool):
            raise ValueError('Invalid visibility')
        photo.is_active = data['is_active']
    if 'frame_id' in data:
        photo.frame = get_object_or_404(Frame, id=data['frame_id'], owner=request.user)
    photo.save()
    return JsonResponse(photo_json(request, photo))


def viewer_photo(request, token, photo_id):
    photo = get_object_or_404(Photo, id=photo_id, frame__access_token=token, is_active=True)
    response = FileResponse(photo.image.open('rb'), content_type=mimetypes.guess_type(photo.image.name)[0] or 'application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


urlpatterns = [
    path('frames/', frames),
    path('frames/<uuid:frame_id>/', frame_detail),
    path('frames/<uuid:frame_id>/rotate/', rotate),
    path('frames/<uuid:frame_id>/photos/', upload),
    path('photos/<uuid:photo_id>/', photo_detail),
]
