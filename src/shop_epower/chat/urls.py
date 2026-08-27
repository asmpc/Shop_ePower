from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/create/', views.room_create, name='room_create'),
    path('rooms/<int:pk>/', views.room_detail, name='room_detail'),
    path('rooms/<int:pk>/take/', views.room_take, name='room_take'),
    path('rooms/<int:pk>/close/', views.room_close, name='room_close'),
    path('rooms/<int:pk>/send/', views.room_send, name='room_send'),
]