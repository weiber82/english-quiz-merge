from django.db import models
from django.db.models import Min, Count, Q, F
from django.utils import timezone
from django.conf import settings
from django.db.models import Avg
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
    
    @classmethod
    def delete_by_id(cls, user_id):
        try:
            user = cls.objects.get(id=user_id)
            user.delete()
            return True
        except cls.DoesNotExist:
            return False


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
    def get_by_topic(cls, topic, include_gpt=None):
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

    # 依 ID 刪除題目
    @classmethod
    def delete_by_id(cls, qid):
        try:
            q = cls.objects.get(id=qid)
            q.delete()
            return True
        except cls.DoesNotExist:
            return False


    @classmethod
    def create_from_gpt(cls, content, options, answer, topic):
        """
        封裝 GPT 題目的建立邏輯
        """
        return cls.objects.create(
            content=content,
            options=options,
            answer=answer,
            topic=topic,
            is_gpt_generated=True
        )

    
    # 統計每個題型的題目數量
    @classmethod
    def get_topic_distribution(cls):
        all_topics = ['vocab', 'grammar', 'cloze', 'reading']

        data = (
            cls.objects
            .values('topic')
            .annotate(count=Count('id'))
        )
        count_map = {}
        for item in data:
            topic = item.get('topic')
            if topic:
                count_map[topic] = item['count']

        return [{'topic': topic, 'count': count_map.get(topic, 0)} for topic in all_topics]
    
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
    def get_latest_by_user_and_question(cls, user, question):
        return cls.objects.filter(user=user, question=question, is_correct=False).order_by('-timestamp').first()


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
    
    # 計算各個題型的平均正確率
    @classmethod
    def get_topic_accuracy(cls):
        data = (
            cls.objects
            .values(topic=F('question__topic'))
            .annotate(
                total=Count('id'),
                correct=Count('id', filter=Q(is_correct=True))
            )
            .order_by('topic')
        )
        return [
            {
                'topic': item['topic'],
                'accuracy': round(item['correct'] / item['total'] * 100, 2) if item['total'] else 0
            }
            for item in data
        ]

    # 根據 Question.id 取得所有作答記錄
    @classmethod
    def get_records_by_question_id(cls, qid):
        return cls.objects.filter(question_id=qid)
    
    # 根據 Question.id 取得選項分析數據(被選次數、被選比率、通過率、該題測驗總數)
    @classmethod
    def get_question_stats(cls, question_id):
        records = cls.objects.filter(question_id=question_id)
        total_records = records.count()
        correct_count = records.filter(is_correct=True).count()

        # 各選項被選次數
        option_stats = {opt: 0 for opt in ['A', 'B', 'C', 'D']}
        for r in records:
            if r.selected_option in option_stats:
                option_stats[r.selected_option] += 1

        # 各選項被選機率 (%)
        option_ratio = {}
        for opt, count in option_stats.items():
            option_ratio[opt] = round((count / total_records) * 100, 1) if total_records > 0 else 0.0

        # 通過率 (%)
        pass_rate = round((correct_count / total_records) * 100, 1) if total_records > 0 else 0.0

        return {
            'stats': option_stats,
            'ratio': option_ratio,
            'pass_rate': pass_rate,
            'total': total_records
        }
    

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


# class Explanation(models.Model):
#     question = models.OneToOneField(Question, on_delete=models.CASCADE)
#     explanation_text = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     source = models.CharField(max_length=50, default='gpt')

#     def __str__(self):
#         return f"詳解 - Q{self.question.id}"


class Explanation(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1)  # 使用者當時選錯的選項
    explanation_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50, default='gpt')

    class Meta:
        unique_together = ('question', 'selected_option')

    def __str__(self):
        return f"詳解 - Q{self.question.id} (選 {self.selected_option})"

    @classmethod
    def create_from_gpt(cls, question, selected_option, explanation_text):
        """
        封裝 GPT 詳解建立邏輯，避免在 service 中操作 ORM 細節。
        """
        return cls.objects.create(
            question=question,
            selected_option=selected_option,
            explanation_text=explanation_text,
            source='gpt'
        )
    

    @classmethod
    def get_cached(cls, question, selected_option):
        return cls.objects.filter(
            question=question,
            selected_option=selected_option
        ).first()


# class GptLog(models.Model):
#     original_question = models.ForeignKey(Question, related_name='origin', on_delete=models.CASCADE)
#     generated_question = models.ForeignKey(Question, related_name='generated', on_delete=models.CASCADE)
#     topic = models.CharField(max_length=50)
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"GPT 出題記錄：{self.topic}"


class GptLog(models.Model):
    original_question = models.ForeignKey(Question, related_name='origin', on_delete=models.CASCADE)
    generated_question = models.ForeignKey(Question, related_name='generated', on_delete=models.CASCADE)
    topic = models.CharField(max_length=50)
    wrong_option = models.CharField(max_length=1, default="")
    explanation = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('original_question', 'wrong_option')

    def __str__(self):
        return f"Q{self.original_question.id} 錯選 {self.wrong_option} → 精練題 Q{self.generated_question.id}"

    # 查詢：這題某選項是否已經生成過精練題
    @classmethod
    def get_cached_similar_question(cls, original_question, wrong_option):
        return cls.objects.filter(
            original_question=original_question,
            wrong_option=wrong_option
        ).select_related('generated_question').first()

    # 建立一筆新的 GPT 精練題快取記錄
    @classmethod
    def create_log_entry(cls, original_question, generated_question, wrong_option, explanation=None):
        return cls.objects.create(
            original_question=original_question,
            generated_question=generated_question,
            topic=original_question.topic,
            wrong_option=wrong_option,
            explanation=explanation            
        )



class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} 對 Q{self.question.id} 的回饋"
    
    #S8
    class Meta:
        unique_together = ('user', 'question') # 每個使用者對同一題目只能有一筆評價

    def __str__(self):
        return f"{self.user.username} 對 Q{self.question.id} 的回饋: {self.rating} 星"

    @classmethod
    def add_or_update_feedback(cls, user_instance, question_instance, rating_value, comment_text=""):
        """
        新增或更新使用者對特定題目的評價。
        """
        if not (1 <= rating_value <= 5):
            raise ValueError("評分必須介於 1 到 5 之間。")

        feedback_obj, created = cls.objects.update_or_create(
            user=user_instance,
            question=question_instance,
            defaults={'rating': rating_value, 'comment': comment_text}
        )
        return feedback_obj, created

    @classmethod
    def get_feedbacks_for_question(cls, question_instance):
        """獲取特定題目的所有評價列表，按時間倒序"""
        return cls.objects.filter(question=question_instance).order_by('-created_at')

    @classmethod
    def get_feedbacks_by_user(cls, user_instance):
        """獲取特定使用者提交的所有評價列表，按時間倒序"""
        return cls.objects.filter(user=user_instance).order_by('-created_at')

    @classmethod
    def get_average_rating_for_question(cls, question_instance):
        """計算特定題目的平均評分"""
        # 確保 question_instance 不是 None
        if not question_instance:
            return None
        avg_rating = cls.objects.filter(question=question_instance).aggregate(Avg('rating'))['rating__avg']
        return round(avg_rating, 2) if avg_rating is not None else None

    @classmethod
    def get_average_rating_for_question_id(cls, question_id):
        """根據 question_id 計算特定題目的平均評分"""
        avg_rating = cls.objects.filter(question_id=question_id).aggregate(Avg('rating'))['rating__avg']
        return round(avg_rating, 2) if avg_rating is not None else None


    @classmethod
    def get_feedback_by_id_and_user(cls, feedback_id, user_instance):
        try:
            if not user_instance:
                return None
            return cls.objects.get(id=feedback_id, user=user_instance)
        except cls.DoesNotExist:
            return None

    def update_details(self, new_rating, new_comment=""):
        """更新此評價的評分和評論"""
        if not (1 <= new_rating <= 5):
            raise ValueError("評分必須介於 1 到 5 之間。")
        self.rating = new_rating
        self.comment = new_comment
        self.save()
        
    # ⭐ 新增：獲取某使用者提交過評價的所有不重複主題 ⭐
    @classmethod
    def get_distinct_topics_for_user_feedback(cls, user_instance):
        if not user_instance:
            return []
        return cls.objects.filter(user=user_instance)\
                          .values_list('question__topic', flat=True)\
                          .distinct()\
                          .order_by('question__topic')

    # ⭐ 修改：讓 get_feedbacks_by_user 可以接受 topic 參數 ⭐
    @classmethod
    def get_feedbacks_by_user(cls, user_instance, topic_name=None): 
        """獲取特定使用者提交的所有評價列表，可選按主題篩選，按時間倒序"""
        if not user_instance:
            return cls.objects.none() # 回傳空的 QuerySet
            
        feedbacks_query = cls.objects.filter(user=user_instance)
        if topic_name and topic_name.lower() != 'all': 
            feedbacks_query = feedbacks_query.filter(question__topic=topic_name)
        return feedbacks_query.select_related('question').order_by('-created_at') # 優化查詢
    
    # ⭐ 新增：取得主題題型平均難易度 ⭐
    @classmethod
    def get_average_rating_by_topic(cls):
        all_topics = ['vocab', 'grammar', 'cloze', 'reading']

        data = (
            cls.objects
            .values('question__topic')
            .annotate(avg_rating=Avg('rating'))
        )

        # 這裡的 key 是 question__topic，但實際上 Django 回傳的 key 是 'topic'
        rating_map = {item['question__topic']: item['avg_rating'] for item in data}

        return [
            {'topic': topic, 'avg_rating': round(float(rating_map.get(topic, 0) or 0), 2)}
            for topic in all_topics
        ]



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

    # --- 原有方法，進行必要調整以符合新需求 ---
    @classmethod
    def get_or_create(cls, user, question, defaults=None):
        if defaults is None:
            defaults = {}
        defaults.setdefault('is_fixed', False)
        
        obj, created = cls.objects.get_or_create(user=user, question=question, defaults=defaults)
        if not created:
            pass
        elif created:
             obj.last_wrong_time = timezone.now()
             obj.save(update_fields=['last_wrong_time'])
        return obj, created

    def save_wrong_question(self):
        self.save()

    def update_wrong_question_fields(self, fields_to_update=None):
        self.save(update_fields=fields_to_update)

    @classmethod
    def get_unconfirmed_by_user_and_topic(cls, user, topic=None):
        """
        獲取使用者待複習的錯題 (confirmed=False 且 is_fixed=False)，可按主題篩選。
        這是 S5 錯題本主列表將使用的方法。
        """
        query = cls.objects.filter(user=user, confirmed=False, is_fixed=False)
        if topic and topic.lower() != 'all':
            query = query.filter(question__topic=topic)
        return query.order_by('-last_wrong_time').select_related('question')

    @classmethod
    def get_distinct_topics_for_unconfirmed_by_user(cls, user):
        """獲取使用者待複習錯題中的不重複主題 (只考慮 is_fixed=False 的)"""
        return cls.objects.filter(user=user, confirmed=False, is_fixed=False) \
                          .values_list('question__topic', flat=True) \
                          .distinct() \
                          .order_by('question__topic')

    @classmethod
    def get_sample_for_weakness_analysis(cls, user, sample_count):
        all_user_wrong_questions = cls.objects.filter(user=user, confirmed=False)
        
        available_count = all_user_wrong_questions.count()
        actual_sample_count = min(available_count, sample_count)
        
        if actual_sample_count > 0:
            return random.sample(list(all_user_wrong_questions), actual_sample_count)
        return []
    
    @classmethod
    def get_unfixed_by_user(cls, user): # 這個方法名稱明確指明了 is_fixed=False
        return cls.objects.filter(user=user, confirmed=False, is_fixed=False).select_related('question')

    @classmethod
    def mark_as_wrong(cls, user, question):
        """將題目標記為答錯，並重設其「已學會」狀態。"""
        obj, created = cls.objects.get_or_create(
            user=user, 
            question=question,
            defaults={
                'last_wrong_time': timezone.now(),
                'is_fixed': False,
                'confirmed': False
            }
        )
        if not created:
            obj.last_wrong_time = timezone.now()
            obj.is_fixed = False
            obj.fixed_dt = None
            obj.confirmed = False
            obj.save(update_fields=['last_wrong_time', 'is_fixed', 'fixed_dt', 'confirmed'])
        return obj

    # 新增：將此錯題標記為「已學會」的實例方法
    def mark_as_learned(self):
        """將此 WrongQuestion 記錄標記為已學會 (is_fixed=True)，並記錄時間。"""
        if not self.is_fixed:
            self.is_fixed = True
            self.fixed_dt = timezone.now()
            self.save(update_fields=['is_fixed', 'fixed_dt', 'last_wrong_time'])
            return True
        return False
    
    @classmethod
    def get_unconfirmed_by_user_and_topic(cls, user, topic=None):
        query = cls.objects.filter(user=user, confirmed=False, is_fixed=False)
        if topic and topic.lower() != 'all':
            query = query.filter(question__topic=topic)
        return query.order_by('-last_wrong_time').select_related('question')

    @classmethod
    def get_distinct_topics_for_unconfirmed_by_user(cls, user):
        return cls.objects.filter(user=user, confirmed=False, is_fixed=False) \
                        .values_list('question__topic', flat=True) \
                        .distinct() \
                        .order_by('question__topic')
                        
    @classmethod
    def get_fixed_by_user_and_topic(cls, user, topic=None):
        query = cls.objects.filter(user=user, is_fixed=True)
        if topic and topic.lower() != 'all':
            query = query.filter(question__topic=topic)
        return query.order_by('-fixed_dt', '-last_wrong_time').select_related('question')

    @classmethod
    def get_distinct_topics_for_fixed_by_user(cls, user):
        return cls.objects.filter(user=user, is_fixed=True) \
                        .values_list('question__topic', flat=True) \
                        .distinct() \
                        .order_by('question__topic')
    

    @classmethod
    def get_by_id_and_user(cls, wqid, user):
        """
        取得指定使用者的特定錯題紀錄。
        封裝 get(id=..., user=...) 查詢，避免視圖直接操作 ORM。
        """
        try:
            return cls.objects.get(id=wqid, user=user)
        except cls.DoesNotExist:
            return None

                          

class ImproveSuggestion(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='improve_suggestions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    need_improve = models.BooleanField(default=False)
    suggestion = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "需要改善" if self.need_improve else "不需改善"
        return f"Q{self.question.id} 的建議 ({status})"

    @classmethod
    def need_improve_by_id(cls, question_id):
        """
        根據題目 ID 判斷是否標記為需要改善。
        """
        suggestion_obj = cls.objects.filter(question_id=question_id, need_improve=True).first()
        return suggestion_obj is not None

    @classmethod
    def get_suggestion_by_id(cls, question_id):
        """
        根據題目 ID 取得改善建議（若有的話）。
        """
        try:
            suggestion_obj = cls.objects.get(question_id=question_id)
            return suggestion_obj.suggestion if suggestion_obj.need_improve else None
        except cls.DoesNotExist:
            return None

    @classmethod
    def add_suggestion(cls, question_id, user_id, suggestion):
        if not suggestion.strip():
            raise ValueError("suggestion 不可為空")

        question = Question.objects.get(id=question_id)
        user = User.objects.get(id=user_id)

        suggestion_obj = cls.objects.create(
            question=question,
            user=user,
            suggestion=suggestion.strip(),
            need_improve=True
        )
        return suggestion_obj
    
    @classmethod
    def list_by_question(cls, question_id):
        return cls.objects.filter(question_id=question_id).order_by('-created_at')
    
    @classmethod
    def mark_resolved_by_id(cls, suggestion_id):
        try:
            obj = cls.objects.get(id=suggestion_id)
            obj.need_improve = False
            obj.save()
            return True
        except cls.DoesNotExist:
            return False
