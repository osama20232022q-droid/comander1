allowed, _, _ = usage_available(user_id)
    if not allowed:
        return AIResult(False, "⚠️ استنفدت حد أسئلتك اليومي. راجع البوت غدًا.")

    # بناء سياق المحادثة ليطابق صيغة Gemini (user و model)
    contents = []
    for m in context_messages:
        role = "user" if m.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

    # بناء سؤال المستخدم الحالي
    sys_intro = f"[معلومات: {profile_context}]\n\n"
    if mode == "explain":
        sys_intro += "اشرح هذا الموضوع بتفصيل وتبسيط عالي:\n"
    elif mode == "mcq":
        sys_intro += "اكتب أسئلة MCQ امتحانية مع الحل عن هذا الموضوع:\n"
    elif mode == "essay":
        sys_intro += "اكتب Short essay مرتب عن هذا الموضوع:\n"
    elif mode == "medical":
        sys_intro += "بفهم طبي دقيق، اشرح أو شخّص هذا الموضوع:\n"

    final_user_text = clean_text(sys_intro + user_text, AI_MAX_INPUT_CHARS)
    contents.append({"role": "user", "parts": [{"text": final_user_text}]})

    # بناء هيكل الطلب (Payload) لجوجل جميناي
    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }

    # استدعاء دالة الاتصال بخيط منفصل (thread) كما كانت في الكود الأصلي
    result = await asyncio.to_thread(_post_gemini, payload)
    if result.ok:
        increment_usage(user_id)
    return result


async def extract_document_text(file_path: str, file_name: str | None = None) -> str:
    """Extract text from simple text/PDF files. Keeps the bot alive if extraction fails."""
    path = Path(file_path)
    suffix = path.suffix.lower() or Path(file_name or "").suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:AI_MAX_FILE_CHARS]
        except Exception:
            return ""
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # optional dependency in the patch requirements
            reader = PdfReader(str(path))
            chunks: list[str] = []
            for page in reader.pages[:25]:
                chunks.append(page.extract_text() or "")
                if sum(len(c) for c in chunks) >= AI_MAX_FILE_CHARS:
                    break
            return "\n".join(chunks)[:AI_MAX_FILE_CHARS]
        except Exception as e:
            return f"[تعذر استخراج PDF تلقائيًا: {e}]"
    return ""


async def download_telegram_file(bot, file_id: str, file_name: str | None = None) -> str:
    tg_file = await bot.get_file(file_id)
    suffix = Path(file_name or "").suffix if file_name else ""
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{file_id}{suffix}")
    await tg_file.download_to_drive(custom_path=file_path)
    return file_path
