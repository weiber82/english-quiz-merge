from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import User, Question, Favorite, TestRecord, WeakTopic, Explanation, GptLog, Feedback, WrongQuestion, ImproveSuggestion

admin.site.register(User)
admin.site.register(Question)
admin.site.register(Favorite)
admin.site.register(TestRecord)
admin.site.register(WeakTopic)
admin.site.register(Explanation)
admin.site.register(GptLog)
admin.site.register(Feedback)
admin.site.register(WrongQuestion)
admin.site.register(ImproveSuggestion)