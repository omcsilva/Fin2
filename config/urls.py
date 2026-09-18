from django.urls import path
from django.views.generic import RedirectView
from fin2.dashboard import views
from fin2.dashboard.manual_price_views import manual_prices
from fin2.dashboard.ledger_views import cash, historical, product_detail
from fin2.dashboard.catalog_views import catalog
from fin2.dashboard.catalog_images import catalog_image

from fin2.dashboard.xp_statement_views import update as xp_statement_update

urlpatterns = [
    path('fin2/importar/<str:identifier>/revisar-xp/', xp_statement_update, name='xp-statement-update'),
    path('fin2/cotacoes/manuais/', manual_prices, name='manual-prices'),
    path('fin2/historico/fin1/cotacoes/', historical(views.prices), name='legacy-prices'),
    path('fin2/historico/fin1/', historical(views.overview), name='legacy-overview'),
    path('fin2/historico/fin1/posicoes/', historical(views.positions), name='legacy-positions'),
    path('fin2/historico/fin1/posicoes/<str:identifier>/', historical(views.quantity_detail), name='legacy-quantity-detail'),
    path('fin2/historico/fin1/caixa/', historical(views.legacy_cash), name='legacy-cash'),
    path('fin2/historico/fin1/alocacao/', historical(views.allocation), name='legacy-allocation'),
    path('fin2/historico/fin1/relatorios/', historical(views.reports), name='legacy-reports'),

    path('fin2/imagens/<str:identifier>/', catalog_image, name='catalog-image'),
    path('fin2/cadastros/', catalog, name='catalog'),
    path('fin2/cadastros/<str:kind>/', catalog, name='catalog-kind'),
    path("", RedirectView.as_view(pattern_name="overview", permanent=False)),
    path("fin2/", views.overview, name="overview"),
    path("fin2/posicoes/", views.positions, name="positions"),
    path("fin2/posicoes/<str:identifier>/", views.quantity_detail, name="quantity-detail"),
    path("fin2/classes/<int:class_id>/", product_detail, name="class-detail"),
    path("fin2/produtos/<int:product_id>/", product_detail, name="product-detail"),
    path("fin2/titulares/<int:investor_id>/", cash, name="investor-detail"),
    path("fin2/instituicoes/<int:institution_id>/", cash, name="institution-detail"),
    path("fin2/contas/<int:account_id>/", cash, name="account-detail"),
    path("fin2/caixa/", cash, name="cash"),
    path("fin2/lancamentos/", views.manual_events, name="manual-events"),
    path("fin2/lancamentos/transferir/", views.manual_transfer, name="manual-transfer"),
    path("fin2/lancamentos/transferencias/<str:identifier>/reverter/", views.reverse_manual_transfer, name="manual-transfer-reverse"),
    path("fin2/importar/<str:identifier>/revisao/", views.xp_statement_review, name="xp-statement-review"),
    path("fin2/importar/<str:identifier>/notas/",
         views.xp_statement_notes, name="xp-statement-notes"),
    path("fin2/importar/", views.file_imports, name="file-imports"),
    path("fin2/importar/<str:identifier>/confirmar/", views.commit_file_import, name="file-import-commit"),
    path("fin2/importar/<str:identifier>/rejeitar/", views.reject_file_import, name="file-import-reject"),
    path("fin2/importar/<str:identifier>/arquivo/", views.file_import_file, name="file-import-file"),
    path("fin2/lancamentos/<str:identifier>/reverter/", views.reverse_manual_event, name="manual-event-reverse"),
    path("fin2/alocacao/", views.allocation, name="allocation"),
    path("fin2/historico/", views.history, name="history"),
    path("fin2/relatorios/", views.reports, name="reports"),
    path("fin2/conciliacao/", historical(views.reconciliation), name="reconciliation"),
    path("fin2/relatorios/fluxos/<str:identifier>/classificar/", views.classify_cash_flow, name="cash-flow-classify"),
    path("fin2/cotacoes/", views.prices, name="prices"),
    path("fin2/cotacoes/capturas/", views.quote_captures, name="quote-captures"),
    path("fin2/cotacoes/atualizar/", views.start_price_update, name="price-update-start"),
    path("fin2/cotacoes/atualizar/cancelar/", views.cancel_price_update, name="price-update-cancel"),
    path("fin2/cotacoes/<str:identifier>/mecanismo/", views.price_update_method, name="price-update-method"),
    path("fin2/cotacoes/atualizacao/", views.price_update_status, name="price-update-status"),
    path("fin2/cotacoes/<str:identifier>/resposta/", views.quote_response, name="quote-response"),
    path("fin2/registros/", historical(views.records), name="records"),
    path("fin2/registros/<str:identifier>/", historical(views.record), name="record"),
    path("fin2/documentos/", views.documents, name="documents"),
    path("fin2/documentos/<str:identifier>/", views.document, name="document"),
    path("fin2/documentos/<str:identifier>/arquivo/", views.document_file, name="document-file"),
    path("fin2/revisao/", historical(views.issues), name="issues"),
]
