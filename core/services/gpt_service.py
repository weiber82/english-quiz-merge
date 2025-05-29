# --- 這是你定義的核心弱點分類和相關關鍵字 (你需要擴充和調整關鍵字) ---
CORE_WEAKNESS_CATEGORIES_KEYWORDS = {
    "動詞時態": ["時態", "tense", "過去式", "完成式", "現在式", "未來式", "verb form", "動詞變化"],
    "名詞與冠詞": ["名詞", "noun", "冠詞", "article", "a/an/the", "可數", "不可數"],
    "代名詞": ["代名詞", "pronoun", "he/she/it", "they/them"],
    "形容詞與副詞": ["形容詞", "adjective", "副詞", "adverb", "比較級", "最高級"],
    "介係詞與片語": ["介係詞", "介詞", "preposition", "片語", "phrase", "in/on/at"],
    "連接詞與子句": ["連接詞", "conjunction", "子句", "clause", "because", "although", "but"],
    "句型結構": ["句型", "句子結構", "sentence structure", "語序", "倒裝"],
    "單字理解與混淆": ["單字", "詞彙", "vocabulary", "meaning", "混淆字", "synonym", "antonym", "用字"],
    "假設語氣": ["假設", "subjunctive", "if clause", "條件句"],
    "被動語態": ["被動", "passive voice"],
    "間接引語": ["間接引語", "reported speech", "indirect speech"],
    "閱讀理解技巧": ["閱讀", "reading comprehension", "主旨", "細節"],
    # "聽力理解技巧": ["聽力", "listening"], # 如果有聽力題
    # 你可以再新增一個 "其他" 分類來接住無法匹配的主題
    "其他弱點": [] 
}

def map_gpt_topics_to_core_categories(gpt_generated_topics):
    """
    將 GPT 生成的自由主題映射到預定義的核心弱點分類。
    """
    mapped_core_topics = set()
    if not gpt_generated_topics: # 如果 GPT 沒給主題，就回傳空列表
        return []

    for gpt_topic in gpt_generated_topics:
        gpt_topic_lower = gpt_topic.lower()
        matched_category = None
        for core_category, keywords in CORE_WEAKNESS_CATEGORIES_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in gpt_topic_lower:
                    mapped_core_topics.add(core_category)
                    matched_category = core_category # 標記已找到
                    break 
            if matched_category:
                break # 如果這個 gpt_topic 已被映射，就處理下一個 gpt_topic
        
        if not matched_category and gpt_topic: # 如果都沒匹配到，且 gpt_topic 不是空的
            mapped_core_topics.add("其他弱點") # 將其歸類到 "其他弱點"

    return list(mapped_core_topics)


class GPTExplanationService:
    def __init__(self, gpt_client):
        self.gpt_client = gpt_client

    def explain(self, question, answer, options):
        prompt = self._build_prompt(question, answer, options)
        return self.gpt_client.get_response(prompt)


    def _build_prompt(self, q, a, options):
        options_text = "\n".join([f"{key}. {value}" for key, value in options.items()])
        return f"""請說明為什麼下面的英文選擇題中，選項「{a}」是正確或錯誤的，盡可能在100字以內說明每個選項，要在選項前面備註。
                題目：{q}
                選項：
                {options_text}
                正確答案：{a}
                請用中文母語的觀點解釋，評斷學生可能錯誤的原因，幫助學生學習。"""
                
    def _build_s6_prompt(self, sampled_wrong_questions_data, predefined_weak_topics=None):
        # sampled_wrong_questions_data: 一個列表，每項包含一道錯題的資訊
        # (例如：題目內容, 選項, 正確答案, 學生選擇的錯誤答案(如果有的話))
        # predefined_weak_topics: 一個可選的預定義弱點主題列表
        
        prompt_parts = ["請分析以下學生答錯的題目，找出學生最主要的學習弱點主題，並提供一段綜合的文字摘要。"]
        
        for i, data in enumerate(sampled_wrong_questions_data):
            # data 應包含 'content', 'options_text', 'correct_answer', 'student_selected_answer' (如果適用)
            options_str = "\n".join([f"  {key}. {value}" for key, value in data.get('options', {}).items()])
            prompt_parts.append(f"\n錯題 {i+1}:")
            prompt_parts.append(f"  題目：{data.get('content', '')}")
            prompt_parts.append(f"  選項：\n{options_str}")
            prompt_parts.append(f"  正確答案：{data.get('correct_answer', '')}")
            if 'student_selected_answer' in data and data['student_selected_answer']: # 確保有此欄位且不為空
                 prompt_parts.append(f"  學生選擇的錯誤答案：{data.get('student_selected_answer')}")
            else:
                 prompt_parts.append(f"  (學生選擇的答案未提供，請根據題目和選項分析可能的錯誤原因)")


        if predefined_weak_topics:
            topics_str = ", ".join(predefined_weak_topics)
            prompt_parts.append(f"\n請從以下弱點主題中選擇（如果適用，也可提出不在列表中的其他主題）：{topics_str}")
        else:
            prompt_parts.append("\n請自由歸納弱點主題。")
            
        prompt_parts.append("\n請將你的分析結果以下列格式呈現：")
        prompt_parts.append("弱點主題：[主題1, 主題2, ...]")
        prompt_parts.append("文字摘要：[一段綜合的文字摘要，說明學生的主要學習問題和建議]")
        
        return "\n".join(prompt_parts)

    def analyze_weaknesses(self, wrong_questions_data_list, predefined_weak_topics=None): # predefined_weak_topics 這裡可以先不用
        if not wrong_questions_data_list:
            return {"weak_topics": [], "summary": "沒有足夠的錯題進行分析。"}

        prepared_data_for_prompt = []
        for wq_data in wrong_questions_data_list:
            question_obj = wq_data.get('question_obj')
            # student_choice_key = wq_data.get('selected_option_key') # 先假設只分析題目本身
            # student_selected_answer_text = ""
            # if question_obj and student_choice_key and student_choice_key in question_obj.options:
            #      student_selected_answer_text = f"{student_choice_key}. {question_obj.options[student_choice_key]}"

            prepared_data_for_prompt.append({
                'content': question_obj.content if question_obj else "",
                'options': question_obj.options if question_obj else {},
                'correct_answer': question_obj.answer if question_obj else "",
                # 'student_selected_answer': student_selected_answer_text # 先不傳學生答案，讓GPT從題目分析
            })

        # 注意：這裡的 _build_s6_prompt 的第二個參數 predefined_weak_topics 我們先不傳，讓它使用 else 裡的自由歸納
        prompt = self._build_s6_prompt(prepared_data_for_prompt) 
        raw_response = self.gpt_client.get_response(prompt)
        
        print(f"GPT Raw Response: {raw_response}")
        
        gpt_generated_topics_list = []
        summary_text = "GPT未能提供有效的分析結果。"

        lines = raw_response.split('\n')
        for line in lines:
            if line.startswith("弱點主題："):
                topics_str = line.replace("弱點主題：", "").strip()
                if topics_str.startswith('[') and topics_str.endswith(']'):
                    topics_str = topics_str[1:-1]
                gpt_generated_topics_list = [topic.strip() for topic in topics_str.split('、') if topic.strip()] 
            elif line.startswith("文字摘要："):
                summary_text = line.replace("文字摘要：", "").strip()
        
        print(f"GPT Generated Topics List (raw): {gpt_generated_topics_list}") # <--- 在這裡看解析出的GPT主題
        
        # 在獲取到 gpt_generated_topics_list 之後，呼叫映射函式
        core_weakness_topics = map_gpt_topics_to_core_categories(gpt_generated_topics_list)
        
        print(f"Mapped Core Weakness Topics: {core_weakness_topics}") # <--- 在這裡看映射後的核心主題

        return {"weak_topics": core_weakness_topics, "summary": summary_text}


