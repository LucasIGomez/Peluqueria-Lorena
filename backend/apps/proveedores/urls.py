from django.urls import path
from . import views

app_name = 'proveedores'

urlpatterns = [
    path('', views.lista_proveedores, name='lista_proveedores'),
    path('generar-orden/', views.generar_orden, name='generar_orden'),
    path('descargar-orden/', views.descargar_orden_compra, name='descargar_orden_compra'),
    path('crear-producto-ajax/', views.crear_producto_ajax, name='crear_producto_ajax'),
    path('crear/', views.crear_proveedor, name='crear_proveedor'),
    path('editar/<int:pk>/', views.editar_proveedor, name='editar_proveedor'),
    path('eliminar/<int:pk>/', views.eliminar_proveedor, name='eliminar_proveedor'),
]
