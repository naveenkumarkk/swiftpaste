from fastapi_users.router.oauth import get_oauth_router
from httpx_oauth.clients.google import GoogleOAuth2
from app.core.config import settings
from app.core.auth.backend import auth_backend
from app.core.auth.oauth.user_manager import get_user_manager

google_oauth_client = GoogleOAuth2(
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET
)

google_oauth_router = get_oauth_router(
    oauth_client=google_oauth_client,
    backend=auth_backend,
    state_secret=settings.GOOGLE_CLIENT_SECRET,
    get_user_manager=get_user_manager,  
    redirect_url="http://localhost:3000/oauth/google/callback",
    associate_by_email=True,
    
)