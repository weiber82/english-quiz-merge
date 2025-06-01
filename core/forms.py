from django import forms
from .models import Question

TOPIC_CHOICES = [
    ('vocab', '字彙'),
    ('grammar', '文法'),
    ('cloze', '克漏字'),
    ('reading', '閱讀'),
]
ANSWER_CHOICES = [
    ('A', 'A'),
    ('B', 'B'),
    ('C', 'C'),
    ('D', 'D'),
]
class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['content', 'options', 'answer', 'topic']  # 不含 is_gpt_generated
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'options': forms.HiddenInput(),
            'answer': forms.Select(choices=ANSWER_CHOICES, attrs={'class': 'form-control'}),
            'topic': forms.Select(choices=TOPIC_CHOICES, attrs={'class': 'form-control'}),  # ✅ 下拉式選單
        }