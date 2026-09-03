from django.urls import path
from django.views.generic import RedirectView
from fin2.dashboard import views
from fin2.dashboard.catalog_views import catalog
from fin2.dashboard.catalog_images import catalog_image

urlpatterns = [
    path('fin2/imagens/<str:identifier>/', catalog_image, name='catalog-image'),
    path('fin2/cadastros/', catalog, name='catalog'),
    path('fin2/cadastros/<str:kind>/', catalog, name='catalog-kind'),
    path("", RedirectView.as_view(pattern_name="overview", permanent=False)),
    path("fin2/", views.overview, name="overview"),
    path("fin2/posicoes/", views.positions, name="positions"),
    path("fin2/posicoes/<str:identifier>/", views.quantity_detail, name="quantity-detail"),
    path("fin2/caixa/", views.cash, name="cash"),
    path("fin2/lancamentos/", views.manual_events, name="manual-events"),
    path("fin2/lancamentos/transferir/", views.manual_transfer, name="manual-transfer"),
    path("fin2/lancamentos/transferencias/<str:identifier>/reverter/", views.reverse_manual_transfer, name="manual-transfer-reverse"),
    path("fin2/importar/", views.file_imports, name="file-imports"),
    path("fin2/importar/<str:identifier>/confirmar/", views.commit_file_import, name="file-import-commit"),
    path("fin2/importar/<str:identifier>/rejeitar/", views.reject_file_import, name="file-import-reject"),
    path("fin2/importar/<str:identifier>/arquivo/", views.file_import_file, name="file-import-file"),
    path("fin2/lancamentos/<str:identifier>/reverter/", views.reverse_manual_event, name="manual-event-reverse"),
    path("fin2/alocacao/", views.allocation, name="allocation"),
    path("fin2/historico/", views.history, name="history"),
    path("fin2/relatorios/", views.reports, name="reports"),
    path("fin2/conciliacao/", views.reconciliation, name="reconciliation"),
    path("fin2/relatorios/fluxos/<str:identifier>/classificar/", views.classify_cash_flow, name="cash-flow-classify"),
    path("fin2/cotacoes/", views.prices, name="prices"),
    path("fin2/cotacoes/atualizar/", views.start_price_update, name="price-update-start"),
    path("fin2/cotacoes/atualizacao/", views.price_update_status, name="price-update-status"),
    path("fin2/cotacoes/<str:identifier>/resposta/", views.quote_response, name="quote-response"),
    path("fin2/registros/", views.records, name="records"),
    path("fin2/registros/<str:identifier>/", views.record, name="record"),
    path("fin2/documentos/", views.documents, name="documents"),
    path("fin2/documentos/<str:identifier>/", views.document, name="document"),
    path("fin2/documentos/<str:identifier>/arquivo/", views.document_file, name="document-file"),
    path("fin2/revisao/", views.issues, name="issues"),
]
