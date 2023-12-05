from django.urls import path
from .views import process_data, index

urlpatterns = [
    path('', index, name='index'),
    path('process/', process_data, name='process_data'),
]
