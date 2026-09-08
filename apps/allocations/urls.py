from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.allocations.views import AllocationViewSet, OrderHistoryViewSet, OrderRateViewSet, TitleIndexingSessionViewSet

app_name = "allocations"

router = DefaultRouter()
router.register("history", OrderHistoryViewSet, basename="order-history")
router.register("rates", OrderRateViewSet, basename="rates")
router.register("indexing", TitleIndexingSessionViewSet, basename="indexing")
router.register("", AllocationViewSet, basename="allocation")

urlpatterns = [path("", include(router.urls))]
