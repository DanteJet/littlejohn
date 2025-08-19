from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # Админ
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('sessions/week/', views.sessions_week, name='sessions_week'),
    path('sessions/month/', views.sessions_month, name='sessions_month'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/add-child/<int:child_id>/', views.session_add_child, name='session_add_child'),
    path('sessions/<int:pk>/edit/', views.session_edit, name='session_edit'),
    path('sessions/<int:pk>/delete/', views.session_delete, name='session_delete'),

    path('children/', views.children_list, name='children_list'),
    path('children/create/', views.child_create, name='child_create'),
    path('children/<int:pk>/', views.child_detail, name='child_detail'),
    path('children/<int:pk>/edit/', views.child_edit, name='child_edit'),
    path('children/<int:pk>/issue-subscription/', views.issue_subscription, name='issue_subscription'),
    path('children/<int:pk>/subscription/edit/', views.subscription_edit, name='subscription_edit'),


    path('subscriptions/', views.subscriptions_list, name='subscriptions_list'),
    path('subscription-types/', views.subscription_types, name='subscription_types'),
    path('subscription-types/<int:pk>/edit/', views.subscription_type_edit, name='subscription_type_edit'),

    path('parents/create/', views.parent_create, name='parent_create'),

    path('visit/add/', views.add_visit, name='add_visit'),
    path('payment/mark/', views.mark_payment, name='mark_payment'),

    # Родитель
    path('my/schedule/', views.my_schedule, name='my_schedule'),
    path('my/children/', views.my_children, name='my_children'),

    path('children/<int:pk>/delete/', views.child_delete, name='child_delete'),
    path('parents/<int:user_id>/delete/', views.parent_delete, name='parent_delete'),

]
