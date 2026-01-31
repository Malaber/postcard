from django.shortcuts import render
from .models import Frame


def home_view(request):
    context = {}

    if request.user.is_authenticated:
        # Fetch frames owned by this user
        # 'related_name="frames"' in your model allows user.frames.all()
        frames = request.user.frames.all().order_by('-created_at')
        context['frames'] = frames

    return render(request, 'home.html', context)
