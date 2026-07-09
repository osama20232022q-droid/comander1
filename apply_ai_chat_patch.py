from pathlib import Path

ROOT = Path.cwd()

def read(p): return p.read_text(encoding='utf-8')
def write(p, s): p.write_text(s, encoding='utf-8')

def ensure_contains(path, marker, insert, before=None, after=None):
    p = ROOT / path
    s = read(p)
    if marker in s:
        return False
    if before and before in s:
        s = s.replace(before, insert + before, 1)
    elif after and after in s:
        s = s.replace(after, after + insert, 1)
    else:
        raise RuntimeError(f'Could not patch {path}: anchor not found')
    write(p, s)
    return True

# 1) requirements
req = ROOT / 'requirements.txt'
if req.exists():
    s = read(req)
    if 'pypdf' not in s:
        write(req, s.rstrip() + '\npypdf==5.1.0\n')

# 2) buttons.py add default button
bp = ROOT / 'app/services/buttons.py'
s = read(bp)
item = '    {"action_key": "ai_chat", "label": "🤖 دردشة AI", "scope": "main", "button_type": "reply", "row_order": 6, "col_order": 1, "style": "primary"},\n'
if '"action_key": "ai_chat"' not in s:
    anchor = '    {"action_key": "help",'
    if anchor in s:
        s = s.replace(anchor, item + anchor, 1)
    else:
        anchor = '    {"action_key": "admin_panel"'
        s = s.replace(anchor, item + anchor, 1)
    write(bp, s)

# 3) bot.py imports and handlers
botp = ROOT / 'app/bot.py'
s = read(botp)
if 'from app.handlers.ai_chat import' not in s:
    anchor = 'from app.handlers.admin import show_admin_panel, handle_admin_callback, is_admin_tg, handle_restore_file, handle_admin_text\n'
    s = s.replace(anchor, anchor + 'from app.handlers.ai_chat import show_ai_chat, handle_ai_chat_text, handle_ai_chat_file\n', 1)

if 'if await handle_ai_chat_text(update, context, text):' not in s:
    anchor = '    # Admin flows and admin menu are processed first but only for admin.\n'
    insert = '    if await handle_ai_chat_text(update, context, text):\n        return\n\n'
    s = s.replace(anchor, insert + anchor, 1)

if 'if flow == "ai_chat":' not in s:
    anchor = '    if flow == "restore_backup":\n'
    insert = '    if flow == "ai_chat":\n        if not await _require_ready(update, context):\n            return\n        if await handle_ai_chat_file(update, context):\n            return\n\n'
    s = s.replace(anchor, insert + anchor, 1)

if 'BotCommand("ai", "دردشة AI للفهم والشرح")' not in s:
    anchor = '        BotCommand("help", "ماذا يفعل هذا البوت؟"),\n'
    s = s.replace(anchor, anchor + '        BotCommand("ai", "دردشة AI للفهم والشرح"),\n', 1)

if 'CommandHandler("ai", show_ai_chat)' not in s:
    anchor = '    app.add_handler(CommandHandler("help", cmd_help))\n'
    s = s.replace(anchor, anchor + '    app.add_handler(CommandHandler("ai", show_ai_chat))\n', 1)

write(botp, s)
print('AI chat patch applied successfully.')
