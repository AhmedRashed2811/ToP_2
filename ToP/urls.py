from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='home'),  # Home Page
    path('units-catalog/', views.unit_catalog_view, name='units_catalog'),  # Home Page
    path('upload-csv/', views.upload_csv, name='upload_csv'),  # CSV Upload Feature
    path('get-upload-progress/', views.get_upload_progress, name='get_upload_progress'),
    path('create-project/', views.create_project, name='create_project'),
    path('create-company/', views.create_company, name='create_company'),
    path('submit-data/', views.submit_data, name='submit_data'),
    path('login/', views.login, name = "login"),
    path('logout/', views.logout, name = "logout"),
    path('change-password/', views.change_password, name='change_password'),
    path("units/", views.units_data, name="units_data"),
    path("units_list/", views.units_list, name="units_list"),
    path('update_unit/', views.update_unit, name='update_unit'),  # New URL for updates
    path('create-user/', views.create_user, name='create_user'),
    path("project-dashboard/", views.project_dashboard, name="project_dashboard"),
    path("update-project/<int:project_id>/", views.update_project, name="update_project"),  # ✅ Fixing the issue
    path('remove_masterplan/<int:project_id>/', views.remove_masterplan, name='remove_masterplan'),
    path('unit-layouts/', views.unit_layout_manager, name='unit_layout_manager'),
    path('unit-layouts/delete/<int:layout_id>/', views.delete_unit_layout, name='delete_unit_layout'),
    path("delete-project/<int:project_id>/", views.delete_project, name="delete_project"),
    path('manage-companies/', views.manage_companies, name='manage_companies'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path("delete-npv/<int:npv_id>/", views.delete_npv, name="delete_npv"),
    path("delete-gas-fee/<int:fee_id>/", views.delete_gas_fee, name="delete_gas_fee"),
    path("delete-gas-offset/<int:offset_id>/", views.delete_gas_offset, name="delete_gas_offset"),
    path("delete-maintenance-offset/<int:offset_id>/", views.delete_maintenance_offset, name="delete_maintenance_offset"),
    path("delete-ctd/<int:ctd_id>/", views.delete_ctd, name="delete_ctd"),
    path("delete-maintenance-schedule/<int:schedule_id>/", views.delete_maintenance_schedule, name="delete_maintenance_schedule"),
    path("send-hold/", views.send_hold_to_erp, name="send_hold_to_erp"),
    path('companies/<int:company_id>/upload-logo/', views.upload_company_logo, name='upload_company_logo'),
    path('send-support-email/', views.send_support_email, name='send_support_email'),
    path("save-unit/", views.save_unit_to_session, name="save_unit_to_session"),
    path("download-units-pdf/", views.download_all_units_pdf, name="download_all_units_pdf"),
    path('clear-units/', views.clear_saved_units, name='clear_saved_units'),
    path('sales-requests-demo/', views.sales_requests_demo, name='sales_requests_demo'),
    path('sales-requests/', views.sales_requests_list, name='sales_requests_list'),
    path('delete-sales-request/', views.delete_sales_request, name='delete_sales_request'),
    # path('give-overseas/', views.give_overseas, name='give_overseas'),
    path('apply-discount/', views.apply_discount, name='apply_discount'), 
    path('approve-sales-request/', views.approve_sales_request, name='approve_sales_request'),
    path('extend-sales-request/', views.extend_sales_request, name='extend_sales_request'),
    path('get-timer-status/', views.get_timer_status, name='get_timer_status'),
    path('modifications/', views.modification_records_view, name='modification_records'),
    path('project-web-config/', views.project_web_config, name='project_web_config'),
    path('api/project-config/<int:project_id>/', views.get_project_web_config, name='get_project_web_config'),
    path('api/project-config/save/', views.save_project_web_config, name='save_project_web_config'),
    path('login-as-user/', views.login_as_user, name='login_as_user'),
    path('revert-impersonation/', views.revert_impersonation, name='revert_impersonation'),

    path('dual-payments/', views.dual_payments_input, name='dual_payments_input'),

    # Extended AJAX
    path('extended-payments/ajax/save/', views.save_extended_payment_ajax, name='save_extended_payment_ajax'),
    path('extended-payments/ajax/fetch/', views.fetch_extended_payment_ajax, name='fetch_extended_payment_ajax'),
    path('delete_extended_payment_ajax/', views.delete_extended_payment_ajax, name='delete_extended_payment_ajax'),

    # Standard AJAX

    path('sales-dashboard/', views.sales_dashboard, name='sales_dashboard'),
    path('api/sales-data/', views.sales_data_api, name='api_sales_data'),
    path('api/get-projects-salesmen/', views.get_projects_salesmen, name='api_get_projects_salesmen'),
    
    path('import-company-users/', views.import_company_users, name='import_company_users'),

    path('download_sales_pdf/', views.download_sales_pdf, name='download_sales_pdf'),


    path('inventory-model/', views.inventory_model, name='inventory_model'), 
    path('ajax/get_company_units/', views.get_company_units, name='get_company_units'),

    path('market-research-model-master-data/', views.market_research_model_master_data_view, name='market_research_model_master_data'),
    path('save-market-research-entry/', views.save_market_research_entry, name='save_market_research_entry'),
    path('delete-market-entry/', views.delete_market_research_entry, name='delete_market_research_entry'),
    path('import-csv/', views.import_csv_for_model, name='import_csv_for_model'),
    
    
    path('market-units/', views.market_unit_data_list, name='market_unit_data_list'),
    path('market-units/update/', views.update_market_unit_field, name='update_market_unit_field'),
    path('market-units/create/', views.create_market_unit, name='create_market_unit'),
    path('delete_market_unit/', views.delete_market_unit, name='delete_market_unit'),    
    path('import-market-units/', views.import_market_units, name='import_market_units'),
    
    
    
    
    path('market-research/', views.market_research_report, name='market_research_report'),
    path('market-data/', views.get_market_data, name='get_market_data'),
    path('save-project-location/', views.save_project_location, name='save_project_location'),
    path('market-explorer/', views.market_projects_explorer, name='market_explorer'),
    path('filter-projects/', views.filter_projects, name='filter_projects'),

    path('market-dashboard/', views.market_dashboard, name='market_dashboard'),
    
    # API endpoints for dashboard data
    path('market-dashboard/kpis/', views.dashboard_kpis, name='dashboard_kpis'),
    path('market-dashboard/charts/', views.dashboard_charts_data, name='dashboard_charts_data'),
    path('market-dashboard/filters/', views.dashboard_filter_data, name='dashboard_filter_data'),
    path('market-dashboard/export/', views.dashboard_export_data, name='dashboard_export_data'),
    

    path('special-offers/', views.special_offers_input, name='special_offers_input'),
    path('save_special_offer_payment_ajax/', views.save_special_offer_payment_ajax, name='save_special_offer_payment_ajax'),
    path('fetch_special_offer_payment_ajax/', views.fetch_special_offer_payment_ajax, name='fetch_special_offer_payment_ajax'),
    path('delete_special_offer_payment_ajax/', views.delete_special_offer_payment_ajax, name='delete_special_offer_payment_ajax'),
 


    path('market-analysis/', views.market_charts_view, name='market_charts_view'),

    # --- Sync (DELETE + IMPORT) ---
    path("companies/<int:company_id>/sheet-sync/", views.sync_company_units_from_sheet, name="company_sheet_sync"),

    path('pricing-model/', views.pricing_model, name='pricing_model'),
    path('get-company-projects/', views.get_company_projects, name='get_company_projects'),
    
    path('get-project-units-simple/', views.get_project_units_simple, name='get_project_units_simple'),
    path('get-premium-groups/', views.get_premium_groups, name='get_premium_groups'),
    path('add-premium-group/', views.add_premium_group, name='add_premium_group'),
    path('delete-premium-group/', views.delete_premium_group, name='delete_premium_group'),
    path('add-premium-subgroup/', views.add_premium_subgroup, name='add_premium_subgroup'),
    path('delete-premium-subgroup/', views.delete_premium_subgroup, name='delete_premium_subgroup'),
    path('get-project-premium-groups/', views.get_project_premium_groups, name='get_project_premium_groups'),
    path('get-project-subgroups-data/', views.get_project_subgroups_data, name='get_project_subgroups_data'), 
    path('save-unit-premium-view/', views.save_unit_premium_view, name='save_unit_premium_view'),
    path('save-pricing-criteria/', views.save_pricing_criteria_view, name='save_pricing_criteria'),
    path('save_unit_base_price/', views.save_unit_base_price, name='save_unit_base_price'),
    path('save_unit_base_psm/', views.save_unit_base_psm, name='save_unit_base_psm'),
    path('save_unit_premium_totals/', views.save_unit_premium_totals, name='save_unit_premium_totals'),
    
    
    path('sales-performance-analysis/', views.sales_performance_analysis, name='sales_performance_analysis'),
    path('get-company-projects-for-sales/', views.get_company_projects_for_sales, name='get_company_projects_for_sales'),
    path('get-sales-analysis-data/', views.get_sales_analysis_data, name='get_sales_analysis_data'),
    path('get-sales-analysis-by-unit-model/', views.get_sales_analysis_by_unit_model, name='get_sales_analysis_by_unit_model'),
    path('get-premium-analysis-data/', views.get_premium_analysis_data, name='get_premium_analysis_data'),


    path('google-service-accounts/', views.manage_google_service_accounts, name='manage_google_service_accounts'),
    path('google-service-accounts/create/', views.create_google_service_account, name='create_google_service_account'),
    path('google-service-accounts/<int:account_id>/test/', views.test_google_service_account, name='test_google_service_account'),
    path('google-service-accounts/<int:account_id>/toggle/', views.toggle_google_service_account, name='toggle_google_service_account'),
    

    path('unit-mapping/', views.unit_mapping, name='unit_mapping'),
    path('get_project_masterplan/<int:project_id>/', views.get_project_masterplan, name='get_project_masterplan'),
    path('save_unit_position/', views.save_unit_position, name='save_unit_position'),
    path('delete_unit_position/<int:position_id>/', views.delete_unit_position, name='delete_unit_position'),
    path('get_unit_details_for_masterplan/<str:unit_code>/', views.get_unit_details_for_masterplan, name='get_unit_details_for_masterplan'),
    path('delete_child_unit/<int:child_id>/', views.delete_child_unit, name='delete_child_unit'),
    path('sale-unit-masterplan', views.unit_mapping_read_only, name='unit_mapping_read_only'),
    path('get_unit_pin_data/<str:unit_code>/', views.get_unit_pin_data, name='get_unit_pin_data'),
    
     # --- Professional Dashboard ---
    path('dashboard/', views.dashboard_home, name='dashboard_home'), # Renamed to avoid conflict if any, but user asked for dashboard
    path('dashboard/<str:model_name>/', views.dynamic_model_list, name='dynamic_model_list'),
    path('dashboard/<str:model_name>/create/', views.dynamic_model_create, name='dynamic_model_create'),
    path('dashboard/<str:model_name>/<str:pk>/update/', views.dynamic_model_update, name='dynamic_model_update'),
    path('dashboard/<str:model_name>/<str:pk>/delete/', views.dynamic_model_delete, name='dynamic_model_delete'),
    
    path('employees-attendance/', views.attendance_capture_view, name='attendance_capture_view'),
    
    path('employees-attendance-management/', views.management_dashboard_view, name='management_dashboard_view'),
    path('employees-attendance/delete/', views.delete_attendance_log, name='delete_attendance_log'),
    path('employees-attendance-management/cleanup/', views.cleanup_images_view, name='cleanup_images_view'),
    
    
    path("historical-sales-requests-analysis/",views.historical_sales_requests_analysis_page,name="historical_sales_requests_analysis_page"),
    path("historical-sales-requests-analysis/data/",views.historical_sales_requests_analysis_data,name="historical_sales_requests_analysis_data"),
    
    path('import-hub/', views.import_hub, name='import_hub'),
    path('import-hub/trigger/', views.trigger_unified_import, name='trigger_unified_import'),
    path('import-hub/delete-units/', views.delete_hub_units, name='delete_hub_units'),
    path("sales-teams/", views.sales_teams, name="sales_teams"),
    
    
    path("sales-team-report/", views.sales_team_report, name="sales_team_report"),
    path("ajax/sales-teams/", views.ajax_sales_teams, name="ajax_sales_teams"),
    path("ajax/sales-team-report/", views.ajax_sales_team_report, name="ajax_sales_team_report"),



] 
 
  
  