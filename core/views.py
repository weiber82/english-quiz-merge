from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import login_required
from .services.gpt_service import GPTExplanationService
from .services.openai_client import OpenAIClient
from .services.auth_service import AuthService
from .models import User, Favorite, Question, TestRecord, WrongQuestion, WeakTopic
from .forms import QuestionForm
from dotenv import load_dotenv
import json
import random
import os
import uuid


load_dotenv()  # 讀取 .env 檔案

auth_service = AuthService()

def home(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    explanation = None
    if request.method == 'POST':
        question = request.POST.get('question')
        answer = request.POST.get('answer')

        import os
        client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
        service = GPTExplanationService(gpt_client=client)
        explanation = service.explain(question, answer)

    return render(request, 'home.html', {'explanation': explanation})


def register_view(request):
    message = ""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        success, message = auth_service.register(username, password)
        if success:
            return redirect('login')  # 註冊成功就跳回登入頁
    return render(request, 'register.html', {'message': message})


def login_view(request):
    user_id = request.session.get('user_id')
    if user_id:
        return redirect('dashboard') 

    message = ""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        success, message = auth_service.login(request, username, password)
        if success:
            return redirect('dashboard')  # 登入成功導向主頁
    return render(request, 'login.html', {'message': message})


def logout_view(request):
    auth_service.logout(request)
    return redirect('login')  # 登出後導回首頁登入


def dashboard_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    return render(request, 'dashboard.html')


class TestConfig:
    def __init__(self, topic, count, include_gpt):
        self.topic = topic
        self.count = count
        self.include_gpt = include_gpt

    @classmethod
    def from_request(cls, request):
        return cls(
            topic=request.POST.get("topic"),
            count=int(request.POST.get("count")),
            include_gpt=request.POST.get("include_gpt")
        )
    

    def to_session_data(self):
        return {
            'test_config': {
                'topic': self.topic,
                'count': self.count,
                'include_gpt': self.include_gpt
            }
    }


class PracticeSession:
    def __init__(self, config):
        self.config = config
        self.test_result_id = str(uuid.uuid4())
        self.selected_questions = []

    def initialize(self):
        self.selected_questions = random.sample(
            Question.get_by_topic(self.config.topic, self.config.include_gpt),
            k=self.config.count
        )

    def to_session_data(self):
        return {
            'test_result_id': self.test_result_id,
            'test_config': {
                'topic': self.config.topic,
                'count': self.config.count,
                'include_gpt': self.config.include_gpt,
            },
            'test_questions': [q.id for q in self.selected_questions],
            'answers': {}
        }


def start_test_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    if request.method == 'POST':
        # 清除舊紀錄
        request.session.pop('test_questions', None)
        request.session.pop('answers', None)

        config = TestConfig.from_request(request)
        session = PracticeSession(config)
        session.initialize()

        request.session.update(session.to_session_data())
        return redirect('test_question', question_index=0)

    return render(request, 'start_test.html')


def test_question_view(request, question_index):
    config = request.session.get('test_config')
    if not config:
        return redirect('start_test')

    if 'test_questions' not in request.session:
        topic = config['topic']
        count = config['count']
        include_gpt = config['include_gpt']

        all_questions = Question.get_by_topic(topic, include_gpt)
        selected = random.sample(all_questions, min(count, len(all_questions)))
        request.session['test_questions'] = [q.id for q in selected]
        request.session['answers'] = {}

    question_ids = request.session['test_questions']
    if question_index >= len(question_ids):
        return redirect('dashboard')

    selected_answer = None
    if request.method == 'POST':        
        selected_answer = request.POST.get('answer')
        question = Question.get_by_id(question_ids[question_index])

        answers = request.session.get('answers', {})
        answers[str(question.id)] = selected_answer
        request.session['answers'] = answers
        request.session.modified = True  # ⭐⭐ ←← 這行是關鍵！加上它才能真的寫進 session！

        user_id = request.session.get('user_id')
        test_result_id = request.session.get('test_result_id')

        print("✅ 寫入 session['answers']:", answers)

        if user_id and test_result_id:
            TestRecord.save_answer(user_id, question, selected_answer, test_result_id)

    else:
        question = Question.get_by_id(question_ids[question_index])

    return render(request, 'test_question.html', {
        'question': question,
        'index': question_index,
        'total': len(question_ids),
        'selected': selected_answer
    })


def test_result_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    test_result_id = request.session.get('test_result_id')
    if not test_result_id:
        return redirect('start_test')

    records = TestRecord.get_test_records(user_id, test_result_id)
    correct_count = TestRecord.get_correct_count(user_id, test_result_id)
    wrong_records = TestRecord.get_wrong_records(user_id, test_result_id)

    total = records.count()
    accuracy = round((correct_count / total) * 100, 2) if total else 0

    question_order = request.session.get('test_questions', [])

    indexed_wrong_records = []
    for record in wrong_records:
        try:
            seq = question_order.index(record.question.id) + 1
        except ValueError:
            seq = "?"
        is_starred = Favorite.is_starred(user_id, record.question.id)
        indexed_wrong_records.append({
            'record': record,
            'seq': seq,
            'is_starred': is_starred
        })

    # 移到最後頁面真正顯示完再清除
    response = render(request, 'test_result.html', {
        'correct_count': correct_count,
        'total': total,
        'accuracy': accuracy,
        'wrong_records': indexed_wrong_records
    })
    request.session.pop('test_result_id', None)
    return response


def gpt_detail_view(request):
    user_id = request.session.get('user_id')
    qid = int(request.GET.get('qid'))
    question = Question.get_by_id(qid)
    if not question:
        return HttpResponseNotFound("題目不存在")

    # 查詢是否已收藏
    # is_starred = Favorite.objects.filter(user_id=user_id, question=question).exists()
    is_starred = Favorite.is_starred(user_id=user_id, question_id=question.id)


    # 找下一題編號（如果有）
    test_questions = request.session.get('test_questions', [])
    next_index = None
    if qid in test_questions:
        index = test_questions.index(qid)
        if index + 1 < len(test_questions):
            next_index = index + 1

    # 取得回答記錄
    answers = request.session.get('answers', {})
    selected = answers.get(str(qid))

    # GPT 解釋
    client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
    service = GPTExplanationService(gpt_client=client)
    explanation = service.explain(
        question.content,
        question.answer,
        question.options
    )

    return render(request, 'gpt_detail.html', {
        'question': question,
        'selected': selected,
        'explanation': explanation,
        'is_starred': is_starred,
        'next_index': next_index,
    })


def user_management_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    # current_user = User.objects.get(id=user_id)
    current_user = User.get_by_id(user_id)
    if current_user.role != 'admin':
        return HttpResponseForbidden("你沒有權限瀏覽此頁面")

    if request.method == 'POST':
        target_id = request.POST.get('user_id')
        new_role = request.POST.get('role')

        if str(current_user.id) == target_id:
            messages.error(request, "無法修改自己的權限。")
            return redirect('user_management')

        # target_user = User.objects.get(id=target_id)
        target_user = User.get_by_id(target_id)
        target_user.role = new_role
        target_user.save()
        messages.success(request, f"使用者 {target_user.username} 已更新為 {new_role}。")
        return redirect('user_management')

    # users = User.objects.all()
    users = User.get_all()
    return render(request, 'user_management.html', {'users': users})


@csrf_exempt
def save_answer_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        qid = str(data.get('qid'))
        ans = data.get('answer')

        user_id = request.session.get('user_id')
        test_result_id = request.session.get('test_result_id')

        if user_id and test_result_id:
            question = Question.get_by_id(qid)
            TestRecord.save_answer(user_id, question, ans, test_result_id)

            # ✅ 如果答錯，就寫入 WrongQuestion
            if ans != question.answer:
                try:
                    # current_user = User.objects.get(id=user_id)
                    current_user = User.get_by_id(user_id)
                    WrongQuestion.get_or_create(
                        user=current_user,
                        question=question,
                        defaults={'confirmed': False}
                    )
                except User.DoesNotExist:
                    print(f"❌ 無法寫入錯題，找不到 user_id={user_id} 的使用者")

        answers = request.session.get('answers', {})
        answers[qid] = ans
        request.session['answers'] = answers

        return JsonResponse({'status': 'ok'})

    return JsonResponse({'error': 'invalid request'}, status=400)
    

def update_note_view(request, fav_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        note_text = request.POST.get('note', '')
        Favorite.update_note(fav_id, user_id, note_text)  # 封裝在 model 內
        return redirect('favorite_questions')


def favorite_questions_view(request):
    user_id = request.session.get('user_id')
    favorites = Favorite.get_user_favorites(user_id)
    return render(request, 'favorite_questions.html', {'favorites': favorites})


@csrf_protect
def toggle_favorite_view(request, question_id):
    user_id = request.session.get('user_id')
    if not user_id:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'unauthorized'}, status=403)
        return redirect('login')

    is_starred = Favorite.toggle_star(user_id=user_id, question_id=question_id)

    # ✅ 如果是 AJAX 請求（例如 GPT 詳解頁），回傳 JSON，不刷新頁面
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'starred': is_starred})

    # ✅ 否則仍支援表單 redirect（例如其他頁用 form POST）
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('favorite_questions')


def wrong_questions_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    selected_topic = request.GET.get('topic', None)

    current_user = User.get_by_id(user_id)
    if not current_user:
        request.session.pop('user_id', None)
        return redirect('login')

    wrong_list = WrongQuestion.get_unconfirmed_by_user_and_topic(
        user=current_user, 
        topic=selected_topic
    )

    available_topics = WrongQuestion.get_distinct_topics_for_unconfirmed_by_user(
        user=current_user
    )

    context = {
        'wrong_questions': wrong_list,
        'available_topics': available_topics,
        'current_topic': selected_topic if selected_topic else 'all'
    }
    return render(request, 'wrong_questions.html', context)


def diagnose_weakness_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    current_user = User.get_by_id(user_id)
    if not current_user:
        request.session.pop('user_id', None)
        return redirect('login')

    analysis_result = {
        "weak_topics": [],
        "summary": "點擊「開始進行弱點分析」按鈕來查看您的 AI 診斷報告。"
    }

    if request.method == 'POST':
        all_user_wrong_questions_count = WrongQuestion.get_unconfirmed_by_user_and_topic(user=current_user).count()
        sample_count = all_user_wrong_questions_count // 2
        if sample_count == 0 and all_user_wrong_questions_count > 0:
            sample_count = 1

        wrong_questions_for_analysis = WrongQuestion.get_sample_for_weakness_analysis(current_user, sample_count)

        if wrong_questions_for_analysis:
            data_for_gpt = []
            for wq_object in wrong_questions_for_analysis:
                data_for_gpt.append({
                    'question_obj': wq_object.question,
                })

            import os
            from .services.gpt_service import GPTExplanationService
            from .services.openai_client import OpenAIClient

            if os.getenv("OPENAI_API_KEY"):
                client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
                gpt_service = GPTExplanationService(gpt_client=client)

                predefined_topics = None
                current_analysis_from_service = gpt_service.analyze_weaknesses(
                    data_for_gpt, predefined_weak_topics=predefined_topics)

                analysis_result["summary"] = current_analysis_from_service.get("summary", "AI分析未能提供有效的文字摘要。")
                analysis_result["weak_topics"] = current_analysis_from_service.get("weak_topics", [])

                if analysis_result["weak_topics"]:
                    for topic_name in analysis_result["weak_topics"]:
                        if topic_name:
                            WeakTopic.update_or_create_weak_topic(current_user, topic_name)
            else:
                analysis_result["summary"] = "OpenAI API 金鑰未設定，無法進行 AI 分析。"
        else:
            analysis_result["summary"] = "沒有足夠的錯題進行分析（目前選取0題）。"

    existing_weak_topics = WeakTopic.get_weak_topics_for_user(current_user)

    context = {
        'analysis_summary': analysis_result.get("summary"),
        'existing_weak_topics': existing_weak_topics,
        'page_title': "AI 弱點診斷"
    }
    return render(request, 'weakness_analysis_result.html', context)


def grade_history_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    current_user = User.get_by_id(user_id)
    if not current_user:
        request.session.pop('user_id', None)
        return redirect('login')

    test_history_details = TestRecord.get_recent_test_session_summaries(user=current_user, limit=10)

    context = {
        'test_history': test_history_details,
        'page_title': "測驗歷史記錄"
    }
    return render(request, 'grade_history.html', context)

# feature/A1
# A1 題庫管理 首頁
def manage_questions_index_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    
    selected_topic = request.GET.get('topic', None)

    current_user = User.get_by_id(user_id)
    if not current_user:
        request.session.pop('user_id', None)
        return redirect('login')

    question_list = Question.get_by_topic(
        topic=selected_topic,
        include_gpt='no'
    )

    topics = ['all', 'vocab', 'grammar', 'cloze', 'reading']

    context = {
        'all_questions': question_list,
        'topics': topics,
        'current_topic': selected_topic if selected_topic else 'all'
    }
    return render(request, 'manage_questions/index.html', context)
    
# A1 題庫管理 新增
def manage_questions_create_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('manage_questions_index')  # 你可以換成你要導向的頁面
    else:
        form = QuestionForm()

    return render(request, 'manage_questions/create.html', {'form': form})

# A1 題庫管理 編輯
def manage_questions_edit_view(request, question_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    question = get_object_or_404(Question, id=question_id)

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            return redirect('manage_questions_index')
    else:
        form = QuestionForm(instance=question)

    return render(request, 'manage_questions/edit.html', {'form': form, 'question': question})

# A1 題庫管理 刪除
def manage_questions_delete_view(request, question_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    try:
        question = Question.objects.get(id=question_id)
        question.delete()
        messages.success(request, "題目已成功刪除。")
    except Question.DoesNotExist:
        messages.warning(request, "這筆資料不存在或已被刪除。")
    return redirect('manage_questions_index')
=======

class WrongChallengeSession:
    def __init__(self, user):
        self.user = user
        self.selected_questions = []

    def initialize(self, count=5):
        wrong_questions = WrongQuestion.get_unfixed_by_user(self.user)
        self.selected_questions = random.sample(
            [wq.question for wq in wrong_questions],
            min(count, len(wrong_questions))
        )

def start_wrong_challenge(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    current_user = User.get_by_id(user_id)
    session = WrongChallengeSession(current_user)
    session.initialize(count=5)

    request.session['challenge_questions'] = [q.id for q in session.selected_questions]
    request.session.modified = True

    return render(request, 'wrong_challenge.html', {
        'questions': session.selected_questions
    })

def submit_wrong_challenge(request):
    user_id = request.session.get('user_id')
    if not user_id or request.method != 'POST':
        return redirect('login')

    current_user = User.get_by_id(user_id)
    question_ids = request.session.get('challenge_questions', [])
    correct_count = 0

    for qid in question_ids:
        selected = request.POST.get(f'question_{qid}')
        q = Question.get_by_id(qid)
        if selected == q.answer:
            correct_count += 1
        else:
            WrongQuestion.mark_as_wrong(current_user, q)

    score = round((correct_count / len(question_ids)) * 100) if question_ids else 0

    return render(request, 'challenge_result.html', {
        'score': score,
        'total': len(question_ids),
        'correct': correct_count
    })
