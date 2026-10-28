from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape
from rest_framework.permissions import AllowAny
from rest_framework.routers import APIRootView


def home(request):
    """A friendly page at the backend's main address, instead of a 404 error."""
    app_url = escape(settings.FRONTEND_URL)
    html = f"""<!doctype html>
<html lang="sw">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SAVIOR Inventory System API</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #f6f6f3; color: #0b0b0b; margin: 0;
           display: flex; min-height: 100vh; align-items: center; justify-content: center; padding: 16px; }}
    main {{ background: #fff; border: 1px solid #e1e0d9; border-radius: 16px; padding: 28px; max-width: 420px; }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    p {{ color: #52514e; line-height: 1.5; }}
    a {{ display: block; margin-top: 10px; padding: 10px 14px; border-radius: 8px; text-decoration: none;
         border: 1px solid #c3c2b7; color: #0b0b0b; }}
    a.primary {{ background: #15803d; border-color: #15803d; color: #fff; }}
  </style>
</head>
<body>
  <main>
    <h1>SAVIOR Inventory System API iko hai &#9989;</h1>
    <p>Hii ni sehemu ya nyuma (backend) inayohifadhi taarifa. Programu yenyewe iko kwenye kiungo hapa chini.</p>
    <p>This is the backend that stores the data. The app itself is at the link below.</p>
    <a class="primary" href="{app_url}">Fungua SAVIOR Inventory System / Open the app</a>
    <a href="/admin/">Admin panel</a>
    <a href="/api/">API endpoints</a>
  </main>
</body>
</html>"""
    return HttpResponse(html)


class PublicAPIRootView(APIRootView):
    """The list of API endpoints at /api/ can be viewed without logging in. The data itself still needs login."""

    permission_classes = [AllowAny]
