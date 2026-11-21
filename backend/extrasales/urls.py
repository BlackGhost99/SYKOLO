from django.urls import path
from . import views, documents, inventory, returns

urlpatterns = [
    path("schools/<uuid:school_id>/finance/extras/sales/<uuid:sale_id>/returns", returns.return_product),
    path("schools/<uuid:school_id>/finance/extras/stock", inventory.inventory),
    path("schools/<uuid:school_id>/finance/extras/sales/<uuid:sale_id>/invoice", documents.invoice),
    path("schools/<uuid:school_id>/finance/extras/sales/<uuid:sale_id>/payments/<uuid:payment_id>/receipt", documents.manual_receipt),
    path("schools/<uuid:school_id>/finance/extras/sales", views.sales),
    path("schools/<uuid:school_id>/finance/extras/sales/<uuid:sale_id>/payments",
         views.receive_manual),
]
