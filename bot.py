import os
from openai import OpenAI
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from pandas import read_csv, read_excel

def call_ai(prompt):
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get('OPENROUTER_API_KEY'),
        )
        response = client.chat.completions.create(
            model="stepfun/step-3.5-flash:free",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка при запросе в LLM: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(rf"Начните работать с ботом, отправив .csv или .xlsx файл или текст, который вам надо проанализировать")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Файл обрабатывается...")
    file = await update.message.document.get_file()
    file_extension = file.file_path.split('.')[-1]
    if file_extension == 'csv':
        df = read_csv(file.file_path)
    elif file_extension == 'xlsx':
        df = read_excel(file.file_path)
    else:
        await update.message.reply_text("Неверный формат файла, доступны только .csv и .xlsx")
        return
    prompt = f"""
    Проанализируй следующий Pandas DataFrame и верни аналитическое саммари и ключевые метрики в виде обычного
    текста на русском, не Markdown, в формате одного сообщения - пользователь больше ничего не отправит:\n
    {df.to_string()}
    """
    await update.message.reply_text(call_ai(prompt))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Текст обрабатывается...")
    prompt = f"""
Проанализируй следующий текст и верни саммари и ключевые метрики в виде обычного текста на русском, 
не Markdown, в формате одного сообщения - пользователь больше ничего не отправит: "{update.message.text}"
"""
    await update.message.reply_text(call_ai(prompt))

def main():
    load_dotenv()
    application = Application.builder().token(os.environ.get('TELEGRAM_TOKEN')).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()