import json

with open(r'C:\Users\aamir\.gemini\antigravity-ide\brain\db97d69f-81f9-4ab9-9ace-199d4e308384\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('step_index', 0) >= 12329:
            content_preview = str(obj.get('content', ''))[:120].replace('\n', ' ')
            tools = [tc.get('name') for tc in obj.get('tool_calls', [])]
            print(f"Step {obj.get('step_index')}: {obj.get('type')} | tools: {tools} | {content_preview}")
