import os
from openai import OpenAI
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from e2b_code_interpreter import Sandbox
import tempfile

async def call_ai(prompt, file):
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get('OPENROUTER_API_KEY'),
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.file_path.split('.')[-1]}") as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name
        sandbox = Sandbox.create()
        sandboxFilePath = f"/tmp/{os.path.basename(tmp_path)}"
        with open(tmp_path, "rb") as f:
            sandbox.files.write(sandboxFilePath, f)
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-super-120b-a12b:free",
            messages=[
                {
                    "role": "user",
                    "content": f"""
                    У тебя есть файл с данными, доступный по пути "{sandboxFilePath}".
                    Верни только работающий python скрипт, не оборачивая его в ```, который можно сразу выполнить
                    и он обязательно выводит через print выводы для следующей задачи:
                    {prompt}
                    """
                }
            ]
        )
        code = response.choices[0].message.content
        execution = sandbox.run_code(code)
        codeResult = execution.logs
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-super-120b-a12b:free",
            messages=[
                {
                    "role": "user",
                    "content": f"""
                    {prompt}
                    Результат анализа кодом:
                    {codeResult}
                    """
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка при запросе в LLM: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(rf"Начните работать с ботом, отправив .csv или .xlsx файл или текст, который вам надо проанализировать")

def isPromptInjection(userMessage):
    if len(userMessage) > 1000:
        return True
    patterns = ["предыдущие инструкции", "игнорируй", "промпт"]
    for pattern in patterns:
        if pattern.lower() in userMessage.lower():
            return True
    return False

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    userMessage = update.message.caption or ""
    if not isPromptInjection(userMessage):
        await update.message.reply_text("Файл обрабатывается (это займет некоторое время)...")
        file = await update.message.document.get_file()
        file_extension = file.file_path.split('.')[-1]
        if file_extension != 'csv' and file_extension != 'xlsx':
            await update.message.reply_text("Неверный формат файла, доступны только .csv и .xlsx")
            return
        prompt = f"""
        Ты эксперт по анализу данных с доступом к Python интерпретатору.
        Проанализируй данный Pandas DataFrame и верни аналитическое саммари и ключевые метрики в виде обычного
        текста на русском, не Markdown, в формате одного сообщения - пользователь больше ничего не отправит.
        """
        if userMessage != "":
            prompt += f"""
            Заметка от пользователя:
            {userMessage}
            """
        await update.message.reply_text(await call_ai(prompt, file))
    else:
        await update.message.reply_text("Замечена подозрительная инструкция, анализ отклонен")
        return

def main():
    try:
        load_dotenv()
        application = Application.builder().token(os.environ.get('TELEGRAM_TOKEN')).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_file))

        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == '__main__':
    main()
