"""
URL configuration for veilgram project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("assets.urls")),
    path("api/v1/", include("audits.urls")),
    path("api/v1/", include("comments.urls")),
    path("api/v1/", include("feed.urls")),
    path("api/v1/", include("hashtags.urls")),
    path("api/v1/", include("moderation.urls")),
    path("api/v1/", include("notifications.urls")),
    path("api/v1/", include("polls.urls")),
    path("api/v1/", include("posts.urls")),
    path("api/v1/", include("profiles.urls")),
    path("api/v1/", include("relations.urls")),
    path("api/v1/", include("reports.urls")),
    path("api/v1/", include("search.urls")),
    path("api/v1/", include("users.urls")),
    # OpenAPI schema & docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
