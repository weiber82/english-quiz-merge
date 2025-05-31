from django.db import models
from django.db.models import Min
from django.utils import timezone
import random

class User(models.Model):
    ROLE_CHOICES = (
        ('student', '學生'),
        ('admin', '管理員'),
    )

    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')

    def __str__(self):
        return f"{self.username} ({self.role})"

    @classmethod
    def find_by_username(cls, username):
        try:
            return cls.objects.get(username=username)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create(cls, username, password):
        return cls.objects.create(username=username, password=password)

    @classmethod
    def get_by_id(cls, user_id):
        try:
            return cls.objects.get(id=user_id)
        except cls.DoesNotExist:
            return None
        
    @classmethod
    def get_all(cls):
        return cls.objects.all()


class Question(models.Model):
    content = models.TextField()
    options = models.JSONField()
    answer = models.CharField(max_length=1)
    topic = models.CharField(max_length=50)
    is_gpt_generated = models.BooleanField(default=False)
    created_dt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.content[:30]

    
    #  依指定排序取得全部題目清單
    @classmethod
    def get_all(cls, order_field='created_dt', order_direction='desc'):
        # :param order_field: 欄位名稱（如 'created_dt', 'topic'）
        # :param order_direction: 'asc' 升冪（預設），'desc' 降冪
        if order_direction == 'desc':
            order_field = f'-{order_field}'
        return list(cls.objects.all().order_by(order_field))
    
    #  依據 ID 取得單題（物件導向封裝）
    @classmethod
    def get_by_id(cls, qid):
        try:
            return cls.objects.get(id=qid)
        except cls.DoesNotExist:
            return None
    
    #  依據主題與是否包含 GPT 題目取得題目清單
    @classmethod
    def get_by_topic(cls, topic, include_gpt):
        qs = cls.objects.filter(topic=topic)
        if include_gpt == 'no':
            qs = qs.filter(is_gpt_generated=False)
        return list(qs)

    #  依 ID 清單取得多筆題目（例如考卷題目）
    @classmethod
    def get_bulk_by_ids(cls, id_list):
        return cls.objects.filter(id__in=id_list) 
        
    
    #  從 EXCEL 新增多筆題目
    @classmethod
    def create_from_excel(cls, qdict, include_gpt=False):
        return cls.objects.create(
            content=qdict['content'],
            options=qdict['options'],
            answer=qdict['answer'],
            topic=qdict['topic'],
            is_gpt_generated=include_gpt
        )
        
    
class TestRecord(models.Model):
    test_result_id = models.CharField(max_length=64) 

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1)
    is_correct = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Q{self.question.id} - Ans: {self.selected_option}"

    # 自行封裝方法：判斷是否已作答
    @classmethod
    def save_answer(cls, user_id, question, selected_option, test_result_id):       
        if not cls.has_answered(user_id, question.id, test_result_id):
            cls.objects.create(
                user_id=user_id,
                question=question,
                selected_option=selected_option,
                is_correct=(selected_option == question.answer),
                test_result_id=test_result_id
            )

    @classmethod
    def has_answered(cls, user_id, question_id, test_result_id):
        return cls.objects.filter(user_id=user_id, question_id=question_id, test_result_id=test_result_id).exists()

    # 計算使用者答題正確率
    @classmethod
    def get_accuracy(cls, user_id):
        records = cls.objects.filter(user_id=user_id)
        total = records.count()
        correct = records.filter(is_correct=True).count()
        return (correct / total * 100) if total else 0
    

    # 新增封裝方法：取得這次測驗的所有紀錄
    @classmethod
    def get_test_records(cls, user_id, test_result_id):
        return cls.objects.filter(user_id=user_id, test_result_id=test_result_id)

    # 新增封裝方法：取得正確筆數
    @classmethod
    def get_correct_count(cls, user_id, test_result_id):
        return cls.get_test_records(user_id, test_result_id).filter(is_correct=True).count()

    # 新增封裝方法：取得錯題紀錄
    @classmethod
    def get_wrong_records(cls, user_id, test_result_id):
        return cls.get_test_records(user_id, test_result_id).filter(is_correct=False)
    

    @classmethod
    def get_recent_test_session_summaries(cls, user, limit=10):
        """
        獲取指定使用者最近的測驗摘要列表。
        每筆摘要包含：測驗日期、主題、總題數、答對題數、正確率、測驗結果ID。
        """
        test_sessions_query = cls.objects.filter(user=user) \
                                         .values('test_result_id') \
                                         .annotate(test_date=Min('timestamp')) \
                                         .order_by('-test_date')[:limit]

        test_history_details = []
        for session_data in test_sessions_query:
            session_id = session_data['test_result_id']
            session_date = session_data['test_date']

            records_for_session = cls.objects.filter(user=user, test_result_id=session_id)

            total_questions = records_for_session.count()
            if total_questions == 0:
                continue

            correct_questions = records_for_session.filter(is_correct=True).count()
            accuracy = round((correct_questions / total_questions) * 100, 2)

            first_record = records_for_session.select_related('question').first()
            test_topic = "未知主題"
            if first_record and first_record.question:
                test_topic = first_record.question.topic

            test_history_details.append({
                'test_date': session_date,
                'test_topic': test_topic,
                'total_questions': total_questions,
                'correct_questions': correct_questions,
                'accuracy': accuracy,
                'test_result_id': session_id,
            })

        return test_history_details
    

class WeakTopic(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=50)  # 與 Question.topic 對應
    last_diagnosed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} 的弱項：{self.topic}"

    @classmethod
    def update_or_create_weak_topic(cls, user, topic_name):
        weak_topic, created = cls.objects.update_or_create(
            user=user,
            topic=topic_name,
            defaults={'last_diagnosed': timezone.now()}
        )
        return weak_topic, created

    @classmethod
    def get_weak_topics_for_user(cls, user):
        return cls.objects.filter(user=user).order_by('-last_diagnosed')


class Explanation(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE)
    explanation_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50, default='gpt')

    def __str__(self):
        return f"詳解 - Q{self.question.id}"


class GptLog(models.Model):
    original_question = models.ForeignKey(Question, related_name='origin', on_delete=models.CASCADE)
    generated_question = models.ForeignKey(Question, related_name='generated', on_delete=models.CASCADE)
    topic = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"GPT 出題記錄：{self.topic}"


class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} 對 Q{self.question.id} 的回饋"


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    note = models.TextField(blank=True)  # S10 筆記內容
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'question')  # 每人每題一筆錯題記錄

    def __str__(self):
        return f"{self.user.username} 的錯題 Q{self.question.id}"

    @classmethod
    def get_user_favorites(cls, user_id):
        """取得指定使用者所有收藏紀錄"""
        return cls.objects.filter(user_id=user_id)

    @classmethod
    def is_starred(cls, user_id, question_id):
        """判斷該使用者是否已收藏某題"""
        return cls.objects.filter(user_id=user_id, question_id=question_id).exists()

    @classmethod
    def toggle_star(cls, user_id, question_id):
        """若已收藏則取消，否則新增"""
        favorite, created = cls.objects.get_or_create(user_id=user_id, question_id=question_id)
        if not created:
            favorite.delete()
            return False
        return True

    @classmethod
    def update_note(cls, fav_id, user_id, note_text):
        """更新筆記內容"""
        try:
            favorite = cls.objects.get(id=fav_id, user_id=user_id)
            favorite.note = note_text
            favorite.save()
        except cls.DoesNotExist:
            pass


class WrongQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE) 
    question = models.ForeignKey(Question, on_delete=models.CASCADE) 
    confirmed = models.BooleanField(default=False)
    last_wrong_time = models.DateTimeField(auto_now=True)
    note = models.TextField(blank=True, null=True)

    is_fixed = models.BooleanField(default=False)
    created_dt = models.DateTimeField(auto_now_add=True)
    fixed_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'question')

    def __str__(self):
        return f"{self.user.username} - {self.question.content[:50]}..."

    # 原本的 get_or_create
    @classmethod
    def get_or_create(cls, user, question, defaults=None):
        return cls.objects.get_or_create(user=user, question=question, defaults=defaults)

    # 原本的 save_wrong_question
    def save_wrong_question(self):
        self.save()

    # 原本的 update_wrong_question_fields
    def update_wrong_question_fields(self, fields_to_update=None):
        self.save(update_fields=fields_to_update)

    # 原本的 get_unconfirmed_by_user_and_topic
    @classmethod
    def get_unconfirmed_by_user_and_topic(cls, user, topic=None):
        query = cls.objects.filter(user=user, confirmed=False)
        if topic and topic != 'all':
            query = query.filter(question__topic=topic)
        return query.order_by('-last_wrong_time')

    # 原本的 get_distinct_topics_for_unconfirmed_by_user
    @classmethod
    def get_distinct_topics_for_unconfirmed_by_user(cls, user):
        return cls.objects.filter(user=user, confirmed=False) \
                          .values_list('question__topic', flat=True) \
                          .distinct() \
                          .order_by('question__topic')

    # 原本的 get_sample_for_weakness_analysis
    @classmethod
    def get_sample_for_weakness_analysis(cls, user, sample_count):
        all_user_wrong_questions = cls.objects.filter(user=user, confirmed=False)
        actual_sample_count = min(len(all_user_wrong_questions), sample_count)
        if actual_sample_count > 0:
            return random.sample(list(all_user_wrong_questions), actual_sample_count)
        return []
    
    @classmethod
    def get_unfixed_by_user(cls, user):
        return cls.objects.filter(user=user, confirmed=False).select_related('question')

    @classmethod
    def mark_as_wrong(cls, user, question):
        obj, _ = cls.objects.get_or_create(user=user, question=question)
        obj.last_wrong_time = timezone.now()
        obj.save()