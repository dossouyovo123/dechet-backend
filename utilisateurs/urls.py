from django.urls import path, include
from .views import PlanificationCountView
from .views import NotificationViewSet
from .views import PlanificationCollecteViewSet
from .views import CollectorViewSet
from .views import CitizenRegistrationView, LoginView, CollectorRegistrationView
from . import views
from rest_framework import routers
from . import api_sacCitoyenView as api 
from rest_framework.routers import DefaultRouter
from .views import CollecteViewSet,SacTriViewSet,CustomUserViewSet

router = routers.DefaultRouter()
router.register(r'citoyens', api.CitoyenViewSet, basename='citoyens')
router.register(r'attribution_sacs', api.AttributionSacsViewSet, basename='attribution_sacs') 
router.register(r'collectes',api.CollecteViewSet, basename='collecte')
router.register(r'sacs', SacTriViewSet, basename='sac') 
router.register(r'admin/collectes', views.AdminCollecteViewSet, basename='admin-collectes') 
router.register(r'collector', CollectorViewSet, basename='collector')
router.register(r'planifications', PlanificationCollecteViewSet) 
router.register(r'notifications', NotificationViewSet)
router.register(r'users', CustomUserViewSet) 

urlpatterns = [
    path('planifications/count/', PlanificationCountView.as_view(), name='planification-count'),
    path('retraits/collecteur/', views.create_withdrawal_collector, name='create_withdrawal_collector'),
    path('retraits/citoyen/', views.create_withdrawal_citizen, name='create_withdrawal_citizen'),
    path('collectes/by_citoyen/', CollecteViewSet.as_view({'get': 'get_collecte_by_citoyen'}),name='get_collecte_by_citoyen'), 
    path('register/citizen/', CitizenRegistrationView.as_view(), name='register_citizen'),
    path('login/', LoginView.as_view(), name='login'),
    path('register/collector/', CollectorRegistrationView.as_view(), name='register_collector'),
    path('users/count/', views.total_users_count, name='total_users_count'),
    path('ajouter_sacs/', views.ajouter_sacs, name='ajouter_sacs'),
    path('modifier_sac/<str:id_sac>/', views.modifier_sac, name='modifier_sac'),
    path('supprimer_sac/<str:id_sac>/', views.supprimer_sac, name='supprimer_sac'),
    path('sacs/', views.liste_sacs, name='liste_sacs'),
    path('sacs/count/', views.get_sac_count, name='get_sac_count'),
    path('', include(router.urls)),
    path('sacs/marquer-sac-utilise/', SacTriViewSet.as_view({'post': 'marquer_sac_utilise'}), name='marquer_sac_utilise'),
    path('collectes/<int:pk>/incrementer-points/', CollecteViewSet.as_view({'patch': 'incrementer_points'}), name='incrementer_points'),
    path('collecteurs/<int:pk>/', views.get_collecteur, name='get_collecteur'), 
    path('collectes/total-collectes-par-citoyen/', CollecteViewSet.as_view({'get': 'get_total_collectes_par_citoyen'}), name='total-collectes-par-citoyen'),
    path('collectes/total-collectes-collecteur/', CollecteViewSet.as_view({'get': 'get_total_collectes_collecteur'}), name='total_collectes_collecteur'),
    path('collectes/count-all/', CollecteViewSet.as_view({'get': 'count_all'}), name='count_all_collectes'),
    path('collectes/total-points/', CollecteViewSet.as_view({'get': 'total_points'}), name='total_points_collectes'),
    path('collectes/points-citoyen/<int:citizen_id>/', CollecteViewSet.as_view({'get': 'get_points_citoyen'}), name='points_citoyen'),

]


 
