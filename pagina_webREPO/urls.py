from django.urls import path
from . import views

urlpatterns = [
    # Autenticación y Perfil
    path('registro/', views.registro_usuario, name='registro'),
    path('login/', views.iniciar_sesion, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Gestión de Inventario (Ropa)
    path('productos/', views.listar_productos, name='listar_productos'),
    path('productos/nuevo/', views.agregar_producto, name='agregar_producto'),
    path('productos/eliminar/<str:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('productos/editar/<str:producto_id>/', views.editar_producto, name='editar_producto'),
]