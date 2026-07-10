send_message_async(user_prompt)
        
        increment_usage(user_id)
        return AIResult(True, response.text)

    except Exception as e:
        return AIResult(False, f"⚠️ عذراً، حدث خطأ أثناء الاتصال بالذكاء الاصطناعي: {str(e)}")


async def extract_document_text(file_path: str, file_name: str | None = None) -> str:
    """استخراج النص من الملفات (TXT, MD, CSV, PDF)"""
    path = Path(file_path)
    suffix = path.suffix.lower() or Path(file_name or "").suffix.lower()
    
    if suffix in {".txt", ".md", ".csv"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:AI_MAX_FILE_CHARS]
        except Exception:
            return ""
            
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            chunks: list[str] = []
            for page in reader.pages[:25]:
                chunks.append(page.extract_text() or "")
                if sum(len(c) for c in chunks) >= AI_MAX_FILE_CHARS:
                    break
            return "\n".join(chunks)[:AI_MAX_FILE_CHARS]
        except Exception as e:
            return f"[تعذر استخراج PDF تلقائياً: {e}]"
    return ""


async def download_telegram_file(bot, file_id: str, file_name: str | None = None) -> str:
    """تنزيل الملف من تليجرام إلى ملف مؤقت"""
    tg_file = await bot.get_file(file_id)
    suffix = Path(file_name or "").suffix if file_name else ""
    
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{file_id}{suffix}")
    
    await tg_file.download_to_drive(custom_path=file_path)
    return file_path
