import os
import asyncio
import re
from urllib.parse import urlparse, unquote, quote_plus
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import asyncpg
from telegram import Bot
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut
from telegram import Update
from telegram.ext import filters, MessageHandler
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler, # ဤနေရာတွင် ထည့်ပါ
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from google import genai
from telegram.error import RetryAfter, TelegramError, Forbidden
import uuid
from zoneinfo import ZoneInfo
MM_TZ = ZoneInfo("Asia/Yangon")


load_dotenv()

TEACHER_BOT_TOKEN = os.getenv("TEACHER_BOT_TOKEN")
STUDENT_BOT_TOKEN = os.getenv("STUDENT_BOT_TOKEN")
TEACHER_CHAT_ID = int(os.getenv("TEACHER_CHAT_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Supabase Credentials
DB_USER = "postgres.vqcoaukndkspyddpnvhd"
DB_PASSWORD = "F2%e.b6ed4/96y!"
DB_HOST = "aws-0-ap-northeast-1.pooler.supabase.com"
DB_PORT = 5432
DB_NAME = "postgres"

MM_TZ = timezone(timedelta(hours=6, minutes=30))
db_pool = None

# Gemini Client စတင်ခြင်း
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# ================= Database Helpers =================

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        min_size=1,
        max_size=5,
    )
    print("✅ Connected to Supabase Pooler.")

async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()
# ----------------- Gemini AI Analysis Function -----------------

async def analyze_weekly_data_with_gemini(student_records_text: str) -> str:
    """တပည့်များ၏ တစ်ပတ်တာ ဒေတာနှင့် မေးခွန်းများကို Gemini AI ဖြင့် သုံးသပ်ချက် ရေးသားခြင်း"""
    if not ai_client:
        return "⚠️ Gemini API Key မရှိသဖြင့် AI သုံးသပ်ချက် မထုတ်နိုင်ပါ။"

    prompt = f"""
    သင်သည် သတိပဋ္ဌာန်နှင့် စိတ်လေ့ကျင့်ရေး (Mindfulness Routine) သင်တန်းမှ ဆရာကြီးအတွက် အကူလက်ထောက် AI ဖြစ်ပါသည်။
    အောက်ပါတို့သည် ပြီးခဲ့သည့် (၇) ရက်အတွင်း တပည့်များ၏ လေ့ကျင့်မှု ပြီးစီးမှု မှတ်တမ်းများနှင့် ၎င်းတို့ မေးမြန်း/ဆွေးနွေးထားသော အတွေ့အကြုံများ ဖြစ်ပါသည်:
    ဆရာကြီး အလွယ်တကူ သုံးသပ်နိုင်ရန်အတွက် အောက်ပါအတိုင်း မြန်မာလို အနှစ်ချုပ် ရေးသားပေးပါ:
    ၁။ တပည့်တစ်ဦးချင်းစီ၏ လေ့ကျင့်မှု အားသာချက်/အားနည်းချက် (ဥပမာ- မနက်ပိုင်း ပုံမှန်လုပ်နိုင်သော်လည်း ညနေပိုင်း အားနည်းခြင်း စသည်)
    ၂။ တပည့်များ၏ စိတ်ပိုင်းဆိုင်ရာ အတွေ့အကြုံ သို့မဟုတ် အခက်အခဲများအပေါ် ဆရာကြီး အဓိက သတိပြု လမ်းညွှန်ပေးသင့်သည့် အချက် (Actionable Insight)
    ၃။ စာဖတ်ရ လွယ်ကူစေရန် Bullet points များနှင့် သပ်ရပ်စွာ ရေးပေးပါ။
    """

    try:
        def call_gemini():
            return ai_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )

        response = await asyncio.to_thread(call_gemini)
        return response.text
    except Exception as e:
        print(f"❌ Gemini Analysis Error: {e}")
        return f"⚠️ AI သုံးသပ်ချက် ရယူရာတွင် အမှားဖြစ်ပေါ်ပါသည်: {e}"
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TEACHER_CHAT_ID:
        await update.message.reply_text("⛔️ ဤ Bot သည် ဆရာအတွက် သီးသန့် Admin Bot ဖြစ်ပါသည်။")
        return

    text = (
        "မင်္ဂလာပါ ဆရာ 🙏\n\n"
        "တပည့်များ၏ တရားလေ့ကျင့်မှု စောင့်ကြည့်စစ်ဆေးနိုင်သော Command များ:\n\n"
        "• `/today` - ယနေ့ တပည့်များ၏ Routine ပြီးစီးမှု ရာခိုင်နှုန်း စစ်ဆေးရန်\n"
        "• `/questions` - တပည့်များ မေးထားသော မေးခွန်း/အတွေ့အကြုံများ ဖတ်ရှုရန်\n"
        "• `/reply  ` - တပည့်ထံ တိုက်ရိုက် စာပြန်ရန်\n"
        "• `/weekly_report` - တစ်ပတ်တာ အစီရင်ခံစာနှင့် AI သုံးသပ်ချက် ထုတ်ယူရန်"
    )
    await update.message.reply_text(text)
async def today_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ယနေ့ တပည့်တစ်ဦးချင်းစီ၏ ပြီးစီးမှုအခြေအနေကို စစ်ဆေးခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    today = datetime.now(MM_TZ).date()
    query = """
        SELECT s.student_name,
               COUNT(log.id) FILTER (WHERE log.is_done = TRUE) as completed_tasks,
               (SELECT COUNT(*) FROM routine_templates) as total_tasks
        FROM students s
        LEFT JOIN student_daily_logs log 
            ON s.student_id = log.student_id AND log.log_date = $1
        GROUP BY s.student_id, s.student_name;
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, today)

    if not rows:
        await update.message.reply_text("ယနေ့အတွက် တပည့်များဘက်မှ မှတ်တမ်း မရှိသေးပါခင်ဗျာ။")
        return

    lines = [f"📊 *ယနေ့ ({today.strftime('%d/%m/%Y')}) တပည့်များ လေ့ကျင့်မှု အခြေအနေ -*\n"]
    for r in rows:
        done = r["completed_tasks"]
        total = r["total_tasks"]
        pct = int((done / total * 100)) if total > 0 else 0
        lines.append(f"• *{r['student_name']}*: `{done}/{total}` ပုဒ် ပြီးစီး ({pct}%)")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
async def view_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """တပည့်များ မေးထားသော နောက်ဆုံးမေးခွန်းများကို ဖတ်ရှုခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    query = """
        SELECT id, student_id, student_name, reflection_text, created_at, teacher_reply
        FROM student_reflections
        ORDER BY created_at DESC
        LIMIT 10;
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query)

    if not rows:
        await update.message.reply_text("မေးခွန်းနှင့် ဆွေးနွေးချက်များ မရှိသေးပါခင်ဗျာ။")
        return

    lines = ["📝 *နောက်ဆုံး လက်ခံရရှိထားသော မေးခွန်း/အတွေ့အကြုံများ -*\n"]
    for r in rows:
        created = r["created_at"].astimezone(MM_TZ).strftime("%d/%m %I:%M %p")
        status = "✅ ဖြေပြီး" if r["teacher_reply"] else "⏳ မဖြေရသေး"
        lines.append(
            f"👤 *{r['student_name']}* (ID: `{r['student_id']}`) - `{created}` [{status}]\n"
            f"❓ \"_{r['reflection_text']}_\"\n"
        )

    lines.append("အကြောင်းပြန်ရန်: `/reply  `")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
async def reply_to_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ဆရာက တပည့်ထံ Student Bot မှတစ်ဆင့် စာတိုက်ရိုက် ပြန်ပို့ပေးခြင်း"""
    user_id = update.effective_user.id
    
    # ၁။ Teacher ID ဟုတ်မဟုတ် စစ်ဆေးခြင်း
    if user_id != TEACHER_CHAT_ID:
        await update.message.reply_text(f"⛔️ သင့် Telegram ID ({user_id}) သည် ဆရာအဖြစ် သတ်မှတ်ထားသော ID ({TEACHER_CHAT_ID}) နှင့် မကိုက်ညီပါ။")
        return

    # ၂။ Arguments စစ်ဆေးခြင်း
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ အသုံးပြုပုံ: `/reply <student_id> <စာသား>`\nဥပမာ: `/reply 8999991129 great! keep up`")
        return

    try:
        student_id = int(context.args[0])
        reply_message = " ".join(context.args[1:])

        # ၃။ Student Bot Token ဖြင့် တပည့်ဆီ စာပို့ခြင်း (Context Session အသုံးပြုခြင်း)
        from telegram import Bot
        async with Bot(token=STUDENT_BOT_TOKEN) as student_bot:
            await student_bot.send_message(
                chat_id=student_id,
                text=f"💌 *ဆရာ့ထံမှ အကြောင်းပြန်ကြားချက် ရောက်ရှိပါသည် -*\n\n{reply_message}",
               # parse_mode="Markdown"
            )

        # ၄။ Database တွင် update လုပ်ခြင်း
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE student_reflections 
                SET teacher_reply = $1 
                WHERE id = (
                    SELECT id FROM student_reflections 
                    WHERE student_id = $2 
                    ORDER BY created_at DESC LIMIT 1
                );
                """,
                reply_message, student_id
            )

        await update.message.reply_text(f"✅ တပည့် ID `{student_id}` ထံသို့ စာအောင်မြင်စွာ ပို့ဆောင်ပြီးပါပြီ။", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ ပို့ဆောင်၍ မရပါ Error: `{e}`", parse_mode="Markdown")
        
import re

async def handle_telegram_direct_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ဆရာက Telegram Message ကို Reply လုပ်ပြီး စာရိုက်ပါက တပည့်ဆီ အလိုအလျောက် ပို့ပေးခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    # ဆရာ့ဆီ ရောက်လာသော မက်ဆေ့ခ်ျကို Reply လုပ်ထားခြင်း ဟုတ်/မဟုတ် စစ်ဆေးခြင်း
    replied_msg = update.message.reply_to_message
    if not replied_msg or not replied_msg.text:
        return

    # မူလရောက်လာသော notification စာသားထဲမှ (ID: 12345678) ကို ရှာဖွေထုတ်ယူခြင်း
    match = re.search(r"\(ID:\s*`?(\d+)`?\)", replied_msg.text)
    if not match:
        return

    student_id = int(match.group(1))
    reply_text = update.message.text

    try:
       
        async with Bot(token=STUDENT_BOT_TOKEN) as student_bot:
            await student_bot.send_message(
                chat_id=student_id,
                text=f"💌 *ဆရာ့ထံမှ အကြောင်းပြန်ကြားချက် ရောက်ရှိပါသည် -*\n\n{reply_text}",
                parse_mode="Markdown"
            )

        # Database တွင် မှတ်တမ်းတင်ခြင်း
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE student_reflections 
                SET teacher_reply = $1 
                WHERE id = (
                    SELECT id FROM student_reflections 
                    WHERE student_id = $2 
                    ORDER BY created_at DESC LIMIT 1
                );
                """,
                reply_text, student_id
            )

        await update.message.reply_text(f"✅ တပည့် ID `{student_id}` ထံသို့ စာအောင်မြင်စွာ ပို့ဆောင်ပြီးပါပြီ။", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ ပို့ဆောင်၍ မရပါ: {e}")
        
async def send_safe_message(bot, chat_id: int, text: str):
    """Telegram Markdown Error မတက်စေရန်နှင့် စာရှည်ပါက အပိုင်းခွဲပို့ပေးသော Helper"""
    max_len = 4000
    chunks = [text[i:i + max_len] for i in range(0, len(text), max_len)]

    for chunk in chunks:
        try:
            await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
        except Exception:
            # Markdown parse မရပါက သာမန် Plain Text ဖြင့် ပို့ခြင်း
            await bot.send_message(chat_id=chat_id, text=chunk)
            
        
async def send_weekly_report(app, manual_chat_id=None):
    """အပတ်စဉ် အစီရင်ခံစာနှင့် Gemini AI သုံးသပ်ချက် ပို့ဆောင်ခြင်း"""
    target_chat_id = manual_chat_id or TEACHER_CHAT_ID

    # ၁။ ပြီးခဲ့သည့် (၇) ရက်အတွင်း ပြီးစီးမှု ဒေတာဆွဲထုတ်ခြင်း
    perf_query = """
        SELECT s.student_name,
               COUNT(log.id) FILTER (WHERE log.is_done = TRUE) as total_done,
               COUNT(DISTINCT log.log_date) as active_days
        FROM students s
        LEFT JOIN student_daily_logs log 
            ON s.student_id = log.student_id 
            AND log.log_date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY s.student_id, s.student_name;
    """

    # ၂။ ပြီးခဲ့သည့် (၇) ရက်အတွင်း တပည့်များ၏ မေးခွန်း/အတွေ့အကြုံများ ဆွဲထုတ်ခြင်း
    qa_query = """
        SELECT student_name, reflection_text, log_date
        FROM student_reflections
        WHERE log_date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY log_date ASC;
    """

    async with db_pool.acquire() as conn:
        perf_rows = await conn.fetch(perf_query)
        qa_rows = await conn.fetch(qa_query)

    if not perf_rows:
        if manual_chat_id:
            await app.bot.send_message(chat_id=target_chat_id, text="ပြီးခဲ့သည့် ၇ ရက်အတွက် ဒေတာမှတ်တမ်း မရှိသေးပါခင်ဗျာ။")
        return

    # တပည့်များ စာရင်း summary ပြုစုခြင်း
    raw_data_lines = []
    report_lines = ["📈 *အပတ်စဉ် တပည့်များ၏ လေ့ကျင့်မှု အစီရင်ခံစာ (Weekly Report)*\n"]
    for r in perf_rows:
        line = f"• *{r['student_name']}*: စုစုပေါင်း ({r['total_done']}) ကြိမ်ပြီးစီး၊ တက်ရောက်မှု ({r['active_days']}/7) ရက်"
        report_lines.append(line)
        raw_data_lines.append(line)

    raw_data_lines.append("\n[တပည့်များ၏ မေးခွန်းများနှင့် အတွေ့အကြုံများ]")
    if qa_rows:
        for q in qa_rows:
            raw_data_lines.append(f"- {q['student_name']} ({q['log_date']}): \"{q['reflection_text']}\"")
    else:
        raw_data_lines.append("- (မေးခွန်းများ မရှိပါ)")

    # ၁။ အခြေခံ ကိန်းဂဏန်း အရင်ပို့ခြင်း
    await app.bot.send_message(
        chat_id=target_chat_id,
        text="\n".join(report_lines),
        parse_mode="Markdown"
    )

    # ၂။ Gemini AI ဖြင့် သုံးသပ်ချက် ရေးခိုင်းခြင်း
    loading_msg = await app.bot.send_message(
        chat_id=target_chat_id,
        text="🤖 _Gemini AI မှ တပည့်များ၏ တစ်ပတ်တာ အခြေအနေကို သုံးသပ်ချက် ပြုစုနေပါသည်..._",
        parse_mode="Markdown"
    )

    student_records_text = "\n".join(raw_data_lines)
    ai_summary = await analyze_weekly_data_with_gemini(student_records_text)

    # ၃။ AI သုံးသပ်ချက် ပို့ခြင်း (လုံခြုံစိတ်ချရသော send_safe_message သို့ ပြောင်းလဲထားပါသည်)
    try:
        await loading_msg.delete()  # Loading စာတန်းကို ဖျက်လိုက်ခြင်း
    except Exception:
        pass

    final_ai_msg = f"🧠 *Gemini AI ၏ အပတ်စဉ် သုံးသပ်ချက် အနှစ်ချုပ် -*\n\n{ai_summary}"
    await send_safe_message(app.bot, target_chat_id, final_ai_msg)
    
async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ဆရာက Bot မှတစ်ဆင့် Routine Task အသစ် လွယ်ကူစွာ ထည့်သွင်းခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    # User ရိုက်ပို့လိုက်သော စာသားကို ယူခြင်း
    raw_text = update.message.text.partition(' ')[2].strip()
    
    if not raw_text or "|" not in raw_text:
        await update.message.reply_text(
            "⚠️ *အသုံးပြုပုံ မှားယွင်းနေပါသည်*\n\n"
            "ပုံစံ: `/add_task <အချိန်ပိုင်း> | <ခေါင်းစဉ်> | <ရှင်းလင်းချက်>`\n\n"
            "ဥပမာ:\n"
            "`/add_task morning | မနက်ခင်း အကြောလျှော့ခြင်း | ခန္ဓာကိုယ်ကို သတိဖြင့် ဖြေလျှော့ပါ`\n\n"
            "*(အချိန်ပိုင်း နေရာတွင် morning, afternoon သို့မဟုတ် evening ဟု ရေးပေးပါ)*",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in raw_text.split("|")]
    section = parts[0].lower()
    title = parts[1]
    description = parts[2] if len(parts) > 2 else ""

    if section not in ["morning", "afternoon", "evening"]:
        await update.message.reply_text("❌ အချိန်ပိုင်းသည် `morning`, `afternoon` သို့မဟုတ် `evening` သာ ဖြစ်ရပါမည်။")
        return

    async with db_pool.acquire() as conn:
        # လက်ရှိ section ရဲ့ နောက်ဆုံး order နံပါတ်ကို ရှာခြင်း
        last_order = await conn.fetchval(
            "SELECT COALESCE(MAX(task_order), 0) FROM routine_templates WHERE section = $1;",
            section
        )
        new_order = last_order + 1

        # Database ထဲသို့ Task အသစ် ထည့်သွင်းခြင်း
        await conn.execute(
            """
            INSERT INTO routine_templates (section, task_order, title, description)
            VALUES ($1, $2, $3, $4);
            """,
            section, new_order, title, description
        )

    await update.message.reply_text(
        f"✅ *Task အသစ် အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ!*\n\n"
        f"⏰ အချိန်ပိုင်း: *{section.capitalize()}* (အမှတ်စဉ်: {new_order})\n"
        f"📌 ခေါင်းစဉ်: *{title}*\n"
        f"📝 ရှင်းလင်းချက်: _{description}_",
        parse_mode="Markdown"
    )


async def delete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """မလိုလားအပ်သော Task ကို ID ဖြင့် ဖျက်ခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ အသုံးပြုပုံ: `/delete_task <task_id>`\n(ID ကို `/list_tasks` တွင် ကြည့်နိုင်ပါသည်)")
        return

    task_id = int(context.args[0])
    async with db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM routine_templates WHERE id = $1;", task_id)

    if "DELETE 1" in result:
        await update.message.reply_text(f"✅ Task ID `{task_id}` ကို အောင်မြင်စွာ ဖျက်ပြီးပါပြီ။", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Task ID `{task_id}` ကို ရှာမတွေ့ပါခင်ဗျာ။")
        
async def add_next_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """နောက်အပတ်အတွက် Task ထည့်သွင်းခြင်း"""
    user_id = update.effective_user.id
    if user_id != TEACHER_CHAT_ID:
        return

    raw_text = update.message.text.partition(' ')[2].strip()
    if not raw_text or "|" not in raw_text:
        await update.message.reply_text(
            "⚠️ အသုံးပြုပုံ:\n/add_next <အချိန်ပိုင်း> | <ခေါင်းစဉ်> | <ရှင်းလင်းချက်>\n\n"
            "ဥပမာ:\n/add_next morning | မနက်ခင်း စင်္ကြံလျှောက်ခြင်း | ၁၅ မိနစ် သတိကပ်ပါ"
        )
        return

    parts = [p.strip() for p in raw_text.split("|")]
    section = parts[0].lower()
    title = parts[1]
    description = parts[2] if len(parts) > 2 else ""

    if section not in ["morning", "afternoon", "evening"]:
        await update.message.reply_text("❌ အချိန်ပိုင်းသည် morning, afternoon သို့မဟုတ် evening သာ ဖြစ်ရပါမည်။")
        return

    try:
        async with db_pool.acquire() as conn:
            last_order = await conn.fetchval(
                "SELECT COALESCE(MAX(task_order), 0) FROM routine_templates WHERE section = $1 AND status = 'next';",
                section
            )
            new_order = (last_order or 0) + 1

            await conn.execute(
                """
                INSERT INTO routine_templates (section, task_order, title, description, status)
                VALUES ($1, $2, $3, $4, 'next');
                """,
                section, new_order, title, description
            )

        reply_msg = (
            f"📝 နောက်အပတ်အတွက် Task အသစ် မှတ်သားပြီးပါပြီ (Pending)\n\n"
            f"⏰ အချိန်ပိုင်း: {section.capitalize()} (အမှတ်စဉ်: {new_order})\n"
            f"📌 ခေါင်းစဉ်: {title}\n"
            f"💡 အပတ်သစ်စတင်ရန် အသင့်ဖြစ်ပါက /switch_week ကို နှိပ်ပါ"
        )
        await update.message.reply_text(reply_msg)

    except Exception as e:
        print(f"❌ Error in add_next_task: {e}")
        await update.message.reply_text(f"Database Error: {e}")
        
async def list_archived_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Archived ဖြစ်နေသော Task အဟောင်းများ စာရင်းကို ကြည့်ရှုခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    async with db_pool.acquire() as conn:
        archived_tasks = await conn.fetch(
            "SELECT id, section, title FROM routine_templates WHERE status = 'archived' ORDER BY updated_at DESC, id DESC LIMIT 20;"
        )

    if not archived_tasks:
        await update.message.reply_text("📦 သိမ်းဆည်းထားသော (Archived) Task အဟောင်းများ မရှိသေးပါခင်ဗျာ။")
        return

    msg = ["📦 သိမ်းဆည်းထားသော Task အဟောင်းများ (Archived) -\n"]
    for t in archived_tasks:
        sec = t['section'][:1].upper()
        clean_title = t['title'].replace("*", "").replace("_", " ")
        msg.append(f"• ID: {t['id']} [{sec}] - {clean_title}")

    msg.append("\n👉 Next စာရင်းထဲ ပြန်ယူသုံးရန်: /reuse_task <ID>")
    await update.message.reply_text("\n".join(msg))


async def reuse_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Archived ဖြစ်နေသော Task တစ်ခုကို နောက်အပတ် (Next) စာရင်းထဲသို့ ပြန်လည်ကူးယူထည့်သွင်းခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "⚠️ အသုံးပြုပုံ: /reuse_task <Task_ID>\n\n"
            "ဥပမာ: /reuse_task 4\n"
            "(ID များကို /list_archived တွင် ကြည့်နိုင်ပါသည်)"
        )
        return

    task_id = int(context.args[0])

    async with db_pool.acquire() as conn:
        # ၁။ မူလ task ရှိမရှိ စစ်ဆေးခြင်း
        task = await conn.fetchrow(
            "SELECT section, title, description FROM routine_templates WHERE id = $1;", 
            task_id
        )

        if not task:
            await update.message.reply_text(f"❌ Task ID {task_id} ကို ရှာမတွေ့ပါခင်ဗျာ။")
            return

        # ၂။ Next စာရင်းထဲက အမြင့်ဆုံး task_order ကို ယူခြင်း
        last_order = await conn.fetchval(
            "SELECT COALESCE(MAX(task_order), 0) FROM routine_templates WHERE section = $1 AND status = 'next';",
            task["section"]
        )
        new_order = (last_order or 0) + 1

        # ၃။ Next task အသစ်အဖြစ် duplicate ကူးထည့်ခြင်း
        await conn.execute(
            """
            INSERT INTO routine_templates (section, task_order, title, description, status, updated_at)
            VALUES ($1, $2, $3, $4, 'next', NOW());
            """,
            task["section"], new_order, task["title"], task["description"]
        )

    await update.message.reply_text(
        f"♻️ Task ကို Next စာရင်းထဲသို့ ပြန်လည်ထည့်သွင်းပြီးပါပြီ!\n\n"
        f"⏰ အချိန်ပိုင်း: {task['section'].capitalize()}\n"
        f"📌 ခေါင်းစဉ်: {task['title']}\n\n"
        f"💡 /list_tasks ဖြင့် စစ်ဆေးနိုင်ပါသည်"
    )


async def restore_last_week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """အရင်အပတ်က သုံးခဲ့သော Tasks များကို လက်ရှိ Active အဖြစ် ပြန်လည် Rollback ပြုလုပ်ခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    try:
        async with db_pool.acquire() as conn:
            # ၁။ Active တွေကို မထိခင် အရင်အပတ်က တကယ် archived ဖြစ်ခဲ့တဲ့ အချိန်မှတ်တမ်းကို အရင်ဆွဲထုတ်ထားခြင်း
            target_time = await conn.fetchval(
                "SELECT MAX(updated_at) FROM routine_templates WHERE status = 'archived';"
            )

            if not target_time:
                await update.message.reply_text("⚠️ ပြန်လည်ဖော်ယူရန် Archived Task မှတ်တမ်း မရှိသေးပါခင်ဗျာ။")
                return

            async with conn.transaction():
                # ၂။ လက်ရှိ Active များကို archived ပြောင်းခြင်း
                await conn.execute(
                    "UPDATE routine_templates SET status = 'archived', updated_at = NOW() WHERE status = 'active';"
                )

                # ၃။ target_time ကို explicit cast ပြုလုပ်ပြီး ၎င်းအချိန်နှင့် ကိုက်ညီသော tasks များကို Active ပြန်တင်ပေးခြင်း
                await conn.execute(
                    """
                    UPDATE routine_templates 
                    SET status = 'active', updated_at = NOW() 
                    WHERE status = 'archived' 
                      AND updated_at >= ($1::timestamptz - INTERVAL '1 minute')
                      AND updated_at <= ($1::timestamptz + INTERVAL '1 minute');
                    """,
                    target_time
                )

        await update.message.reply_text(
            "⏪ အရင်အပတ် Task စာရင်းများကို လက်ရှိ Active အဖြစ် အောင်မြင်စွာ ပြန်လည်သတ်မှတ်ပြီးပါပြီ!\n\n"
            "💡 /list_tasks ဖြင့် ပြန်လည်စစ်ဆေးနိုင်ပါသည်ခင်ဗျာ။"
        )
    except Exception as e:
        print(f"❌ Error in restore_last_week: {e}")
        await update.message.reply_text(f"Error ဖြစ်ပေါ်ပါသည်: {e}")

async def switch_week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """အပတ်သစ်သို့ ကူးပြောင်းခြင်း (Next များကို Active လုပ်ပြီး၊ Active အဟောင်းများကို Archived ပြုလုပ်ခြင်း)"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    async with db_pool.acquire() as conn:
        next_count = await conn.fetchval("SELECT COUNT(*) FROM routine_templates WHERE status = 'next';")

        if next_count == 0:
            await update.message.reply_text("⚠️ နောက်အပတ်အတွက် ကြိုတင်ထည့်ထားသော Task (Next) မရှိသေးပါခင်ဗျာ။\n`/add_next` ဖြင့် အရင်ထည့်သွင်းပေးပါ။")
            return

        async with conn.transaction():
            # ၁။ လက်ရှိ active task များကို archived ပြောင်းခြင်း
            await conn.execute("UPDATE routine_templates SET status = 'archived', is_active = FALSE WHERE status = 'active';")
            # ၂။ next task များကို active ပြောင်းခြင်း
            await conn.execute("UPDATE routine_templates SET status = 'active', is_active = TRUE WHERE status = 'next';")

    await update.message.reply_text(
        f"🚀 *အပတ်သစ်သို့ အောင်မြင်စွာ ကူးပြောင်းပြီးပါပြီ!*\n\n"
        f"• Task အသစ် ({next_count}) ခုကို Active စာရင်းသို့ ထည့်သွင်းလိုက်ပါပြီ။\n"
        f"• ယခင်အပတ် Task အဟောင်းများကို သိမ်းဆည်း (Archived) ထားလိုက်ပါပြီ။\n\n"
        f"ယနေ့နောက်ပိုင်း ပို့ဆောင်မည့် Schedule အားလုံးသည် Task အသစ်များဖြင့်သာ ပို့ဆောင်ပါတော့မည်ခင်ဗျာ။",
        parse_mode="Markdown"
    )
    
async def toggle_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Task တစ်ခုချင်းစီကို Active (ဖွင့်) / Inactive (ပိတ်) အခြေအနေ ပြောင်းလဲခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ အသုံးပြုပုံ: `/toggle_task <Task_ID>`\n(ဥပမာ - `/toggle_task 3`)", parse_mode="Markdown")
        return

    task_id = int(context.args[0])

    async with db_pool.acquire() as conn:
        # လက်ရှိ status ကို စစ်ဆေးပြီး ဆန့်ကျင်ဘက်သို့ ပြောင်းလဲခြင်း
        task = await conn.fetchrow("SELECT id, title, is_active FROM routine_templates WHERE id = $1;", task_id)
        if not task:
            await update.message.reply_text(f"❌ Task ID `{task_id}` ကို ရှာမတွေ့ပါခင်ဗျာ။", parse_mode="Markdown")
            return

        new_status = not task["is_active"]
        await conn.execute("UPDATE routine_templates SET is_active = $1 WHERE id = $2;", new_status, task_id)

    status_str = "🟢 ဖွင့်လှစ်ထားပါသည် (ACTIVE)" if new_status else "🔴 ပိတ်ထားပါသည် (INACTIVE)"
    await update.message.reply_text(
        f"✅ Task ID `{task_id}` (*{task['title']}*) ၏ အခြေအနေကို\n👉 *{status_str}* သို့ ပြောင်းလဲလိုက်ပါပြီ။",
        parse_mode="Markdown"
    )


async def clear_section_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """အချိန်ပိုင်းတစ်ခုလုံးရှိ Task အားလုံးကို Inactive (ပိတ်) အဖြစ် သတ်မှတ်ခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    if not context.args or context.args[0].lower() not in ["morning", "afternoon", "evening"]:
        await update.message.reply_text(
            "⚠️ အသုံးပြုပုံ: `/clear_section <morning/afternoon/evening>`\n(ဥပမာ - `/clear_section morning`)",
            parse_mode="Markdown"
        )
        return

    section = context.args[0].lower()

    async with db_pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE routine_templates SET is_active = FALSE WHERE section = $1;",
            section
        )

    await update.message.reply_text(
        f"✅ *{section.capitalize()}* အချိန်ပိုင်းရှိ Task အားလုံးကို 🔴 *INACTIVE (ပိတ်)* ထားလိုက်ပါပြီ။\n"
        f"ယခုအခါ `/add_task` ဖြင့် အပတ်သစ်အတွက် Task အသစ်များ စိတ်ကြိုက် ထည့်သွင်းနိုင်ပါပြီခင်ဗျာ။",
        parse_mode="Markdown"
    )


async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """လက်ရှိသုံးနေသော Tasks (Active) နှင့် နောက်အပတ်အတွက် ပြင်ထားသော Tasks (Next) များကို စစ်ဆေးခြင်း"""
    if update.effective_user.id != TEACHER_CHAT_ID:
        return

    async with db_pool.acquire() as conn:
        active_tasks = await conn.fetch(
            "SELECT id, section, task_order, title FROM routine_templates WHERE status = 'active' ORDER BY section, task_order ASC;"
        )
        next_tasks = await conn.fetch(
            "SELECT id, section, task_order, title FROM routine_templates WHERE status = 'next' ORDER BY section, task_order ASC;"
        )

    msg = ["📋 *Routine စီမံခန့်ခွဲမှု အခြေအနေ*\n"]

    msg.append("🟢 *လက်ရှိ သုံးနေသော Tasks (Active):*")
    if active_tasks:
        for t in active_tasks:
            # Markdown parse error မဖြစ်စေရန် special characters များ ရှင်းထုတ်ခြင်း
            clean_title = t['title'].replace("*", "").replace("_", " ")
            sec_code = t['section'][:1].upper()
            msg.append(f"  • [{sec_code}] {clean_title} (ID: `{t['id']}`)")
    else:
        msg.append("  _(မရှိသေးပါ)_")

    msg.append("\n🟡 *နောက်အပတ်အတွက် ကြိုထည့်ထားသော Tasks (Next):*")
    if next_tasks:
        for t in next_tasks:
            clean_title = t['title'].replace("*", "").replace("_", " ")
            sec_code = t['section'][:1].upper()
            msg.append(f"  • [{sec_code}] {clean_title} (ID: `{t['id']}`)")
        msg.append("\n👉 အပတ်သစ်သို့ ပြောင်းလဲအသုံးပြုရန်: `/switch_week`")
    else:
        msg.append("  _(ကြိုတင်ထည့်ထားသော Task မရှိပါ - ထည့်ရန်: `/add_next`)_")

    final_text = "\n".join(msg)

    # Markdown ပျက်နေပါက Plain Text ဖြင့် ပို့ပေးမည့် Try-Except
    try:
        await update.message.reply_text(final_text, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(final_text)
    


async def broadcast_routine_to_students(section_name: str, header_text: str, target_student_id: int = None) -> int:
    today = datetime.now(MM_TZ).date()
    
    async with db_pool.acquire() as conn:
        if target_student_id:
            students = [{"student_id": target_student_id}]
        else:
            students = await conn.fetch("SELECT student_id FROM students;")

        tasks = await conn.fetch(
            "SELECT id, title, description FROM routine_templates WHERE section = $1 AND status = 'active' ORDER BY task_order ASC;",
            section_name
        )

    if not tasks or not students:
        return 0

    count = 0
    async with Bot(token=STUDENT_BOT_TOKEN) as student_bot:
        for stu in students:
            chat_id = stu["student_id"]
            batch_id = str(uuid.uuid4())[:8]  # Batch ID အတိုတစ်ခု ဖန်တီးခြင်း
            batch_message_ids = []

            try:
                # ၁။ Header စာသားနှင့် [🗑️ ထပ်နေပါက ဤစာရင်းကို ဖျက်မည်] ခလုတ်တွဲပို့ခြင်း
                header_keyboard = [
                    [InlineKeyboardButton("🗑️ ထပ်နေပါက ဤစာရင်းကို ဖျက်မည်", callback_data=f"dismiss_batch:{batch_id}")]
                ]
                
                h_msg = await student_bot.send_message(
                    chat_id=chat_id,
                    text=f"{header_text}\n\nအောက်ပါ လေ့ကျင့်မှုများကို ပြုလုပ်ပြီးပါက သက်ဆိုင်ရာခလုတ်ကို နှိပ်ပေးပါခင်ဗျာ -",
                    reply_markup=InlineKeyboardMarkup(header_keyboard),
                    parse_mode="Markdown"
                )
                batch_message_ids.append(h_msg.message_id)
                await asyncio.sleep(0.05)

                # ၂။ Task တစ်ခုချင်းစီ ပို့ခြင်း
                for idx, t in enumerate(tasks, start=1):
                    t_id = t["id"]
                    task_text = f"📌 *{idx}။ {t['title']}*"
                    if t["description"]:
                        task_text += f"\n_{t['description']}_"

                    task_keyboard = [
                        [InlineKeyboardButton("လုပ်ဆောင်ပြီး (Done)", callback_data=f"done:{t_id}")]
                    ]

                    t_msg = await student_bot.send_message(
                        chat_id=chat_id,
                        text=task_text,
                        reply_markup=InlineKeyboardMarkup(task_keyboard),
                        parse_mode="Markdown"
                    )
                    batch_message_ids.append(t_msg.message_id)
                    await asyncio.sleep(0.05)

                # ၃။ ဤ Batch ထဲရှိ Message IDs အားလုံးကို DB တွင် သိမ်းဆည်းခြင်း
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO routine_batch_logs (batch_id, student_id, message_ids)
                        VALUES ($1, $2, $3);
                        """,
                        batch_id, chat_id, batch_message_ids
                    )

                count += 1
            except Exception as e:
                print(f"Error sending to {chat_id}: {e}")

            await asyncio.sleep(0.05)

    return count
    
async def handle_teacher_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ဆရာက ခလုတ်နှိပ်သည့်အခါ တပည့်ထံ သက်ဆိုင်ရာ Checklist ပို့ပေးခြင်း"""
    query = update.callback_query
    await query.answer()

    data = query.data
    # data format: "send_routine:<section>:<student_id>"
    if not data.startswith("send_routine:"):
        return

    _, section, student_id_str = data.split(":")
    student_id = int(student_id_str)

    section_titles = {
        "morning": "🌅 *(က) မနက်ပိုင်း လေ့ကျင့်မှု (5:00 AM - 12:00 PM)*",
        "afternoon": "☀️ *(ခ) နေ့လည်ပိုင်း လေ့ကျင့်မှု (12:00 PM - 5:00 PM)*",
        "evening": "🌙 *(ဂ) ညနေပိုင်း လေ့ကျင့်မှု (5:00 PM - 12:00 AM)*"
    }
    header_text = section_titles.get(section, "သတိပဋ္ဌာန် လေ့ကျင့်မှု")

    # အဆိုပါ ကျောင်းသားတစ်ဦးတည်းထံသို့ Checklist ပို့ပေးခြင်း
    sent = await broadcast_routine_to_students(section, header_text, target_student_id=student_id)

    if sent > 0:
        await query.message.reply_text(f"✅ တပည့် (ID: `{student_id}`) ထံသို့ *{section.capitalize()}* Checklist ကို အောင်မြင်စွာ ပို့ဆောင်ပြီးပါပြီ။", parse_mode="Markdown")
    else:
        await query.message.reply_text(f"❌ ပို့ဆောင်၍ မရပါ (Database တွင် Routine မရှိသေးပါ သို့မဟုတ် တပည့်အား မတွေ့ပါ)။")


# ----------------- Main Runner -----------------



async def post_init(application):
    """Bot မစတင်မီ Database Pool ချိတ်ဆက်ခြင်းနှင့် Scheduler စတင်ခြင်း"""
    # ၁။ Database ချိတ်ဆက်ခြင်း
    await init_db()

    # ၂။ Scheduler စတင်ခြင်း
    scheduler = AsyncIOScheduler(timezone=MM_TZ)

    # (က) နေ့စဉ် မနက်ပိုင်း Routine Checklist ပို့ရန် (ဥပမာ - မနက် ၆:၃၀)
    scheduler.add_job(
        broadcast_routine_to_students,
        CronTrigger(hour=6, minute=30, timezone=MM_TZ),
        args=["morning", "🌅 မင်္ဂလာနံနက်ခင်းပါခင်ဗျာ၊ ယနေ့ နံနက်ပိုင်း လေ့ကျင့်မှုများ ဖြစ်ပါသည် -"],
        id="morning_routine",
        name="Morning Routine Checklist"
    )

    # (ခ) နေ့စဉ် နေ့လယ်ပိုင်း Routine Checklist ပို့ရန် (ဥပမာ - နေ့လယ် ၁၂:၀၀)
    scheduler.add_job(
        broadcast_routine_to_students,
        CronTrigger(hour=12, minute=0, timezone=MM_TZ),
        args=["afternoon", "☀️ မင်္ဂလာနေ့လယ်ခင်းပါခင်ဗျာ၊ နေ့လယ်ပိုင်း လေ့ကျင့်မှုများ ဖြစ်ပါသည် -"],
        id="afternoon_routine",
        name="Afternoon Routine Checklist"
    )

    # (ဂ) နေ့စဉ် ညပိုင်း Routine Checklist ပို့ရန် (ဥပမာ - ည ၈:၀၀)
    scheduler.add_job(
        broadcast_routine_to_students,
        CronTrigger(hour=22, minute=40, timezone=MM_TZ),
        args=["evening", "🌙 မင်္ဂလာညချမ်းပါခင်ဗျာ၊ ညပိုင်း လေ့ကျင့်မှုများ ဖြစ်ပါသည် -"],
        id="evening_routine",
        name="Evening Routine Checklist"
    )

    # (ဃ) တနင်္ဂနွေနေ့တိုင်း ည ၉:၀၀ နာရီတွင် အပတ်စဉ် သုံးသပ်ချက် ပို့ရန်
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="sun", hour=21, minute=0, timezone=MM_TZ),
        args=[application],
        id="weekly_report",
        name="Weekly Report"
    )

    scheduler.start()
    print("⏰ Routine & Report Schedulers started successfully...")

    # သတ်မှတ်ထားသော Job စာရင်းနှင့် နောက်တစ်ကြိမ် run မည့်အချိန်များကို Log ထုတ်ကြည့်ခြင်း
    print("⏰ Registered Scheduled Jobs:")
    for job in scheduler.get_jobs():
        print(f"👉 Job: {job.name} | Next Run: {job.next_run_time}")

async def manual_weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command ဖြင့် အစီရင်ခံစာ လှမ်းတောင်းသည့်အခါ ခေါ်ယူရန်"""
    await send_weekly_report(context.application, update.effective_user.id)
    

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Network error များကြောင့် Bot ရပ်မသွားစေရန် ထိန်းကျောင်းခြင်း"""
    err = context.error
    if isinstance(err, (NetworkError, TimedOut)):
        print(f"⚠️ Network glitch ခေတ္တဖြစ်ပေါ်ပါသည် (အလိုအလျောက် ပြန်ချိတ်ပါမည်): {err}")
    else:
        print(f"❌ Error ဖြစ်ပေါ်ပါသည်: {err}")

def main():
    # Network timeout ကြောင့် ReadError မဖြစ်စေရန် timeout များ တိုးပေးခြင်း
    request_config = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30.0,      # default 5.0 မှ 30.0 သို့ မြှင့်ခြင်း
        write_timeout=30.0,
        connect_timeout=30.0,
        pool_timeout=30.0
    )
    app = (
        ApplicationBuilder()
        .token(TEACHER_BOT_TOKEN)
        .request(request_config)
        .post_init(post_init)
        .build()
    )

    # Handlers များ
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add_task", add_task_command))
    app.add_handler(CommandHandler("delete_task", delete_task_command))
    app.add_handler(CommandHandler("add_next", add_next_task_command))
    #app.add_handler(CommandHandler("list_tasks", list_drafts_command))
    app.add_handler(CommandHandler("list_archived", list_archived_command))
    app.add_handler(CommandHandler("reuse_task", reuse_task_command))
    app.add_handler(CommandHandler("restore_last_week", restore_last_week_command))
    app.add_handler(CommandHandler("switch_week", switch_week_command))
    app.add_handler(CommandHandler("list_tasks", list_tasks_command))
    app.add_handler(CommandHandler("toggle_task", toggle_task_command))
    app.add_handler(CommandHandler("clear_section", clear_section_command))
    app.add_handler(CommandHandler("today", today_status))
    app.add_handler(CommandHandler("questions", view_questions))
    app.add_handler(CommandHandler("reply", reply_to_student))
    app.add_handler(CommandHandler("weekly_report", manual_weekly_report))
    app.add_error_handler(error_handler)
    # main() ထဲတွင် ထည့်သွင်းပါ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.REPLY, handle_telegram_direct_reply))
    # ဆရာနှိပ်မည့် Action Button Handler
    app.add_handler(CallbackQueryHandler(handle_teacher_action))

    print("🚀 Teacher Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
