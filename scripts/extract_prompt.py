import json

with open(r'C:\Users\aamir\.gemini\antigravity-ide\brain\db97d69f-81f9-4ab9-9ace-199d4e308384\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('step_index') == 12329:
            with open('scripts/full_phase2c6e_prompt.txt', 'w', encoding='utf-8') as out:
                out.write(obj.get('content', ''))
            print("Extracted prompt, length:", len(obj.get('content', '')))
            break
