from .models import CompanySetting

def site_settings(request):
    try:
        settings = CompanySetting.get_settings()
    except Exception:
        settings = None
    
    profile = None
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
        except Exception:
            from .models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=request.user)

    return {
        'site_settings': settings,
        'user_profile': profile,
    }
