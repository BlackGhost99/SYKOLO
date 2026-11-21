from django.urls import path
from . import views

urlpatterns = [
    path("schools/<uuid:school_id>/finance/extras/sales", views.sales),
    path("schools/<uuid:school_id>/finance/extras/sales/<uuid:sale_id>/payments",
         views.receive_manual),
]
