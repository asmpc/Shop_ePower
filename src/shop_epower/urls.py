from django.urls import path, re_path, include

from shop_epower.views import home
# from task_manager.views import (HomePage,TasksPage, UserPage,
#                                 UrequestPage, CreateTask, CreateComment,
#                                 CreateTag, CreateAttachment, AttachmentsPage, DeleteCommentPage)
from django.views.decorators.cache import cache_page


urlpatterns = [
    path('', home, name='home'),

    #                                                         # кэшируем на 10 минут используя redis по умолчанию
    # path('tasks', TasksPage.as_view(), name='task'),  # cache_page(60 * 10)(TasksPage.as_view())
    # path('users', UserPage.as_view(), name='user'),
    # path('users/<int:pk>/', UrequestPage.as_view(), name='urequest'),
    # path('create', CreateTask.as_view(), name='create_task'),
    # path('comment', CreateComment.as_view(), name='create_comment'),
    # path('tag', CreateTag.as_view(), name='create_tag'),
    # path('attachment', CreateAttachment.as_view(), name='create_attachment'),
    # path('attachments', AttachmentsPage.as_view(), name='attachments'),
    # path('comment_delete/<int:pk>/', DeleteCommentPage.as_view(), name='comment_delete'),

]