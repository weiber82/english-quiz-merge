from django.urls import path
from django.contrib import admin
from . import views
from .views import test_result_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('admin/users/', views.user_management_view, name='user_management'),
    path('start-test/', views.start_test_view, name='start_test'),
    path('test/<int:question_index>/', views.test_question_view, name='test_question'),
    path('test/result/', test_result_view, name='test_result'),
    path('api/save-answer/', views.save_answer_view, name='save_answer'),
    path('gpt/', views.gpt_detail_view, name='gpt_detail'),
    path('gpt/manual/', views.home, name='gpt_manual'),
    path('toggle-favorite/<int:question_id>/', views.toggle_favorite_view, name='toggle_favorite'),
    path('wrong-note/<int:fav_id>/', views.update_note_view, name='update_note'),
    path('favorites/', views.favorite_questions_view, name='favorite_questions'),
    path('wrong-questions/', views.wrong_questions_view, name='my_wrong_questions'),
    
    #--S5功能新增
    path('wrong-question/mark-fixed/<int:wrong_question_id>/', views.mark_wrong_question_fixed_view, name='mark_wrong_question_fixed'),
    
    path('diagnose-weakness/', views.diagnose_weakness_view, name='diagnose_weakness'),
    path('grade-history/', views.grade_history_view, name='grade_history'),
    path('manage-questions/index/', views.manage_questions_index_view, name='manage_questions_index'),
    path('manage-questions/create/', views.manage_questions_create_view, name='manage_questions_create'),
    path('manage-questions/edit/<int:question_id>/', views.manage_questions_edit_view, name='manage_questions_edit'),
    path('manage-questions/delete/<int:question_id>/', views.manage_questions_delete_view, name='manage_questions_delete'),
    path('import_excel/index/', views.import_excel_index_view, name='import_excel_index'),
    path('import-excel/download_template/', views.import_excel_download_template_view, name='import_excel_download_template'),
    path('import-excel/upload_file/', views.import_excel_upload_file_view, name='import_excel_upload_file'),
    path('import-excel/cancel_preview/', views.import_excel_cancel_preview_view, name='import_excel_cancel_preview'),
    path('import-excel/confirm/', views.import_excel_confirm_save_view, name='import_excel_confirm'),
    path('wrong-challenge/', views.start_wrong_challenge, name='wrong_challenge'),
    path('wrong-challenge/submit/', views.submit_wrong_challenge, name='submit_wrong_challenge'),
    path('wrong-challenge/', views.start_wrong_challenge, name='wrong_challenge'),
    path('wrong-challenge/submit/', views.submit_wrong_challenge, name='submit_wrong_challenge'),
    # --- S8 新增的 URL ---
    path('feedback/submit/', views.submit_feedback_view, name='submit_feedback'),
    path('my-feedback/', views.my_feedback_view, name='my_feedback'),
    path('feedback/update/<int:feedback_id>/', views.update_feedback_view, name='update_feedback'),
]
