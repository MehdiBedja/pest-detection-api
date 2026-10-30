from django.urls import re_path
from . import views

urlpatterns = [
    #add
    re_path(r'^fetch/$', views.get_detections_by_ids),
    re_path(r'^upload/$', views.upload_detections_batch),

    # delete
    re_path(r'^(?P<detection_id>[0-9a-f-]+)/delete/$', views.soft_delete_detection),
    re_path(r'^deleted/$', views.get_soft_deleted_detections),
    re_path(r'^delete/batch/$', views.soft_delete_detections),  # 

    # update
    re_path(r'^notes/$', views.get_updated_notes),
    re_path(r'^notes/update/$', views.update_notes),
    re_path(r'^sync/notes/', views.sync_detection_notes,),


    
    re_path(r'^testcloudinary/',views.debug_cloudinary),





]