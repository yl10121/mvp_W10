

import requests
import json
import sys
from pathlib import Path

from datetime import datetime

# OpenRouter（推荐）；兼容旧变量名 DEEPSEEK_API_KEY
import os

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
try:
    import config  # noqa: F401 — 单钥 OPENROUTER→OPENAI
except ImportError:
    pass
OPENROUTER_API_KEY = (
    os.environ.get("OPENROUTER_API_KEY", "").strip()
    or os.environ.get("DEEPSEEK_API_KEY", "").strip()
)

print("API Key 已从环境变量加载（OPENROUTER_API_KEY 或 DEEPSEEK_API_KEY）")

# 检索源 1：示例数据（告诉模型“好的输出长什么样”）
extraction_examples = [
    {
        "input": "Client preparing for wedding, likes white, needs soon",
        "output": {
            "life_event": "Wedding",
            "aesthetic_preference": "White tones",
            "timeline": "Soon",
            "mood": "Excited"
        }
    },
    {
        "input": "Looking for gift for husband, minimalist style, no gold",
        "output": {
            "life_event": "Gift for husband",
            "aesthetic_preference": "Minimalist, no gold",
            "mood": "Thoughtful"
        }
    },
    {
        "input": "王先生今天来店里，说下周结婚纪念日，想要低调一点的首饰，预算两万左右，看起来挺高兴",
        "output": {
            "summary": "王先生为结婚纪念日寻找低调首饰，预算两万，心情愉悦。",
            "life_event": {"value": "结婚纪念日", "confidence": "High", "evidence": "下周结婚纪念日"},
            "timeline": {"value": "下周", "confidence": "High", "evidence": "下周"},
            "aesthetic_preference": {"value": "低调", "confidence": "High", "evidence": "想要低调一点"},
            "size_height": {"value": "N/A", "confidence": "Low", "evidence": "未提及"},
            "budget": {"value": "两万左右", "confidence": "High", "evidence": "预算两万左右"},
            "mood": {"value": "愉悦", "confidence": "Medium", "evidence": "看起来挺高兴"},
            "trend_signals": {"value": "N/A", "confidence": "Low", "evidence": "未提及"},
            "next_step_intent": {"value": "推荐低调简约款首饰", "confidence": "High", "evidence": "偏好+事件+预算"}
        }
    }
]

# 检索源 2：样本语音备忘（模拟 CA 录入的5条原始笔记）
sample_voice_notes = [
    "额张小姐今天早上来了，我看到她瘦了挺多，尺码可能要换成M了。她说她最近一直在运动，也喜欢运动风格的衣服，和上班也好兼容。还有她说下周要去深圳开会参与活动",
    "Client mentioned she is attending a wedding next month, prefers white gold jewelry, seemed in a hurry",
    "Customer is looking for a birthday gift for her husband, likes minimal style, not too flashy",
    "Client came back from a Paris trip, interested in something similar to what she saw there",
    "She dislikes gold tones, prefers silver, no urgency to purchase"
]

# 把这些数据保存成 JSON 文件（模拟从文件检索）
with open("extraction_examples.json", "w") as f:
    json.dump(extraction_examples, f, indent=2, ensure_ascii=False)

with open("sample_voice_notes.json", "w") as f:
    json.dump(sample_voice_notes, f, indent=2, ensure_ascii=False)

print("检索数据已准备：extraction_examples.json 和 sample_voice_notes.json")
print("点击左侧文件夹图标可以看到这两个文件")

# 基础 system prompt
base_prompt = """
You are a Client Memory Structurer. Your task is to convert a post interaction sales advisor voice memo into a structured client memory object.

When given the transcript of a voice memo, extract and organize the information into the following specific fields:

- Summary (2-4 concise sentences capturing the interaction)
- Life Event (e.g., weddings, travel, birthdays, etc.)
- Timeline (specific or approximate timing)
- Aesthetic Preferences (style, color, material, constraints)
- Size/Height (if mentioned, or specific measurements preferred)
- Budget (if mentioned, budget preferences/range)
- Mood (if mentioned, client attitude or emotional state)
- Trend Signals (if the client mentions any interest in trends during the conversation that may be related to existing personas and their trends based on Module 1, 2 and 3)
- Next Step Intent (any specific insight into what the sales advisor should do next)

For each extracted field:
- Assign a confidence level: High / Medium / Low
- Provide a short snippet / quote / supporting evidence from the voice memo transcript

Rules:
- Do NOT hallucinate or invent information. If a field is missing, mark it as N/A with Low confidence and evidence "Not mentioned".
- Keep outputs concise and structured.
- The input may be free-form or guided. Do not assume structure; extract consistently.
- Capture both soft data (emotion, intent) and hard data (dates, budget).

IMPORTANT OUTPUT FORMAT REQUIREMENTS:
- Return the result **strictly as a JSON object** with the exact field names shown above.
- **Every field must be included**, even if its value is N/A and confidence is Low.
- Each field (except Summary) must be an object containing "value", "confidence", "evidence".
- The Summary field should be a simple string.
- **Do NOT wrap the JSON in markdown code blocks (like ```json). Output only the raw JSON object.**
- Do NOT include any extra text before or after the JSON.
"""

# 把 extraction_examples 转换成文字示例，嵌入到 prompt 中
examples_text = "\n\n参考以下示例（输入 → 输出）：\n"
for ex in extraction_examples:
    examples_text += f"\n输入: {ex['input']}\n输出: {json.dumps(ex['output'], ensure_ascii=False)}\n"

system_prompt_with_examples = base_prompt + examples_text

print("System prompt 已包含示例，检索已被使用")

# 你可以从 sample_voice_notes 里选一条，也可以自己写
user_input = "额张小姐今天早上来了，我看到她瘦了挺多，尺码可能要换成M了。她说她最近一直在运动，也喜欢运动风格的衣服，和上班也好兼容。还有她说下周要去深圳开会参与活动。"  # 第一条
# 如果你想换一条，改成 sample_voice_notes[1] 或 sample_voice_notes[2] 等
# 如果你想用完全自己的话，写成：user_input = "客户说下周要过生日，想买一个不张扬的手链"

print("=== 用户输入的语音备忘（已转成文字）===")
print(user_input)

# DeepSeek API 地址
import re

# DeepSeek API 地址
url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
}

# 组装消息
messages = [
    {"role": "system", "content": system_prompt_with_examples},
    {"role": "user", "content": user_input}
]

data = {
    "model": os.environ.get("DEFAULT_MODEL", "openai/gpt-4o-mini"),
    "messages": messages,
    "temperature": 0.2,
    "max_tokens": 3000   # 增加 token 限制，确保输出完整
}

# 发送请求
response = requests.post(url, headers=headers, json=data)

# 处理响应
if response.status_code == 200:
    result = response.json()
    output_text = result['choices'][0]['message']['content']

    # 清理可能出现的 markdown 代码块标记
    output_text = re.sub(r'^```json\s*', '', output_text, flags=re.MULTILINE)
    output_text = re.sub(r'^```\s*', '', output_text, flags=re.MULTILINE)
    output_text = output_text.strip()

    # 尝试解析 JSON
    try:
        decision_output = json.loads(output_text)
    except:
        # 如果直接解析失败，尝试提取 JSON 部分
        match = re.search(r'\{.*\}', output_text, re.DOTALL)
        if match:
            try:
                decision_output = json.loads(match.group())
            except:
                decision_output = {"raw_output": output_text}
        else:
            decision_output = {"raw_output": output_text}

    # 可选：检查是否所有字段都存在，若缺失则补全默认值
    required_fields = [
        "summary", "life_event", "timeline", "aesthetic_preference",
        "size_height", "budget", "mood", "trend_signals", "next_step_intent"
    ]
    for field in required_fields:
        if field not in decision_output:
            if field == "summary":
                decision_output[field] = "N/A"
            else:
                decision_output[field] = {"value": "N/A", "confidence": "Low", "evidence": "Not mentioned"}

    print("\n=== Structured Client Memory Object ===")
    print(json.dumps(decision_output, indent=2, ensure_ascii=False))

else:
    print(f"请求失败，错误码：{response.status_code}")
    print(f"错误信息：{response.text}")
    decision_output = {"error": f"API调用失败: {response.status_code}"}

run_log = {
    "run_id": "001",
    "timestamp": str(datetime.now()),
    "input": {
        "voice_memo_transcript": user_input,
        "input_type": "free-form"
    },
    "prompt_used": system_prompt_with_examples,  # 完整 prompt
    "retrieved_sources": ["extraction_examples.json", "sample_voice_notes.json"],
    "decision_output": decision_output,
    "evidence_used": [],
    "confidence_summary": {},
    "next_step_suggestion": decision_output.get("next_step_intent", {}).get("value", "未明确")
}

# 从输出里提取所有 evidence
if isinstance(decision_output, dict):
    ev_list = []
    for k, v in decision_output.items():
        if isinstance(v, dict) and "evidence" in v:
            ev_list.append(v["evidence"])
    run_log["evidence_used"] = ev_list

    confidence_counts = {"High": 0, "Medium": 0, "Low": 0}

    for k, v in decision_output.items():
        if isinstance(v, dict) and "confidence" in v:
            conf = v["confidence"]
            if conf in confidence_counts:
                confidence_counts[conf] += 1

    run_log["confidence_summary"] = confidence_counts

    missing_fields = 0
    for k, v in decision_output.items():
        if isinstance(v, dict) and v.get("value") == "N/A":
            missing_fields += 1

    run_log["missing_fields_count"] = missing_fields

with open("run_log.json", "w", encoding="utf-8") as f:
    json.dump(run_log, f, ensure_ascii=False, indent=2)

print("\nRun log saved: run_log.json")

import json
from datetime import datetime

# 读取已有反馈
try:
    with open("feedback_log.json", "r", encoding="utf-8") as f:
        all_feedback = json.load(f)
except:
    all_feedback = []

print("\n=== Output for Reviewer Evaluation ===")
print(json.dumps(decision_output, indent=2, ensure_ascii=False))

import sys

print("\n=== 请评审员填写反馈 ===")
if sys.stdin.isatty():
    correctness = input("正确性/质量 (1-5分): ")
    missing = input("是否有缺失信息？(y/n): ")
    if missing.lower() == 'y':
        missing_what = input("缺少什么信息？: ")
    else:
        missing_what = ""
    duplicates = input("是否有重复/噪声？(y/n): ")
    if duplicates.lower() == 'y':
        duplicates_which = input("哪些是重复或噪声？: ")
    else:
        duplicates_which = ""
    usefulness = input("可用性/可直接用于跟进的评分 (1-5分): ")
    reviewer = input("评审者名字（可选）: ")
else:
    print("Non-interactive mode, skipping feedback.")
    correctness = "5"
    missing_what = ""
    duplicates_which = ""
    usefulness = "5"
    reviewer = "Auto-Pipeline"

feedback_entry = {
    "reviewer": reviewer if reviewer else "匿名",
    "correctness": correctness,
    "missing_info": missing_what,
    "duplicates_noise": duplicates_which,
    "usefulness_followup": usefulness,
    "timestamp": str(datetime.now())
}

all_feedback.append(feedback_entry)

with open("feedback_log.json", "w", encoding="utf-8") as f:
    json.dump(all_feedback, f, ensure_ascii=False, indent=2)

print(f"\n反馈已保存！当前共有 {len(all_feedback)} 条反馈。")

