import os
import logging
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters,
)
from config import BOT_TOKEN, ADMIN_IDS, PHOTOS_DIR
from database import init_db, upsert_teacher, get_teacher, get_all_teachers, delete_teacher
from export import export_excel, export_photos_zip

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

os.makedirs(PHOTOS_DIR, exist_ok=True)

# ── States ────────────────────────────────────────────────────────────────────
(
    S_NAME, S_POSITION, S_DEGREE, S_EXPERIENCE,
    S_UNIVERSITY, S_SPECIALIZATION, S_SUBJECTS,
    S_HAS_IELTS, S_IELTS_SCORE,
    S_HAS_CEFR, S_CEFR_LEVEL,
    S_HAS_CERT, S_BIO, S_PHOTO, S_AWARDS, S_CONFIRM,
) = range(16)

TOTAL_STEPS = 14

# ── Keyboards ─────────────────────────────────────────────────────────────────
YES_NO = ReplyKeyboardMarkup(
    [["✅ Ha", "❌ Yo'q"]], resize_keyboard=True, one_time_keyboard=True
)
SKIP = ReplyKeyboardMarkup(
    [["⏭ O'tkazib yuborish"]], resize_keyboard=True, one_time_keyboard=True
)
DEGREE_KB = ReplyKeyboardMarkup(
    [
        ["🎓 Bakalavr", "🎓 Magistr"],
        ["🔬 Doktorantura (PhD)", "🏅 Fan doktori (DSc)"],
        ["📋 O'rta maxsus ta'lim"],
    ],
    resize_keyboard=True, one_time_keyboard=True,
)
CEFR_KB = ReplyKeyboardMarkup(
    [["A1", "A2"], ["B1", "B2"], ["C1", "C2"]],
    resize_keyboard=True, one_time_keyboard=True,
)
CONFIRM_KB = ReplyKeyboardMarkup(
    [["✅ Tasdiqlash va yuborish", "🔄 Qayta boshlash"]],
    resize_keyboard=True, one_time_keyboard=True,
)


def step(n: int, text: str) -> str:
    bar = "▰" * n + "▱" * (TOTAL_STEPS - n)
    return f"📍 *{n}/{TOTAL_STEPS}* qadm  {bar}\n\n{text}"


def skip_text(text: str) -> bool:
    return "o'tkazib" in text.lower() or text.strip() == "-"


def yn(val) -> str:
    return "✅ Ha" if val else "❌ Yo'q"


# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    user = update.effective_user
    existing = get_teacher(user.id)

    greeting = (
        f"👋 Salom, *{user.first_name}*!\n\n"
        "🏫 *Modern School* maktabiga xush kelibsiz!\n\n"
        "Bu bot orqali siz o'z *ustoz profilingizni* to'ldirasiz.\n"
        "Ma'lumotlaringiz maktab saytida chop etiladi.\n\n"
    )

    if existing:
        greeting += "⚠️ Sizda allaqachon profil mavjud. Yangilaysizmi?"
        kb = ReplyKeyboardMarkup(
            [["✏️ Profilni yangilash", "👁 Profilni ko'rish"]],
            resize_keyboard=True, one_time_keyboard=True,
        )
        await update.message.reply_text(greeting, parse_mode="Markdown", reply_markup=kb)
        return S_CONFIRM

    greeting += "▶️ Boshlash uchun — to'liq *ism-familiyangizni* yozing:"
    await update.message.reply_text(
        greeting, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )
    return S_NAME


async def start_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text or ""
    if "yangilab" in text.lower() or "yangilash" in text.lower():
        context.user_data.clear()
        await update.message.reply_text(
            "✏️ Yangilaymiz. To'liq *ism-familiyangizni* yozing:",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
        return S_NAME
    else:
        await profile_cmd(update, context)
        return ConversationHandler.END


# ── 1. Ism ────────────────────────────────────────────────────────────────────
async def s_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("❗ Iltimos, to'liq ism-familiyangizni kiriting.")
        return S_NAME
    context.user_data["full_name"] = name
    await update.message.reply_text(
        step(2, (
            "💼 *Lavozimingiz nima?*\n\n"
            "📌 Misol uchun:\n"
            "• Matematika o'qituvchisi\n"
            "• Ingliz tili o'qituvchisi\n"
            "• Boshlang'ich sinf o'qituvchisi\n"
            "• Direktor muovini\n\n"
            "✍️ Lavozimingizni yozing:"
        )),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return S_POSITION


# ── 2. Lavozim ────────────────────────────────────────────────────────────────
async def s_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["position"] = update.message.text.strip()
    await update.message.reply_text(
        step(3, (
            "🎓 *Ta'lim darajangizni tanlang:*\n\n"
            "Pastdagi tugmalardan birini bosing 👇"
        )),
        parse_mode="Markdown",
        reply_markup=DEGREE_KB,
    )
    return S_DEGREE


# ── 3. Daraja ─────────────────────────────────────────────────────────────────
async def s_degree(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    degree = text.replace("🎓 ", "").replace("🔬 ", "").replace("🏅 ", "").replace("📋 ", "")
    context.user_data["degree"] = degree
    await update.message.reply_text(
        step(4, (
            "📅 *Necha yillik pedagogik tajribangiz bor?*\n\n"
            "📌 Misol: `5` yoki `12`\n\n"
            "✍️ Faqat raqam kiriting:"
        )),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return S_EXPERIENCE


# ── 4. Tajriba ────────────────────────────────────────────────────────────────
async def s_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 0:
        await update.message.reply_text("❗ Iltimos, faqat musbat raqam kiriting. Masalan: `7`",
                                        parse_mode="Markdown")
        return S_EXPERIENCE
    context.user_data["experience_years"] = int(text)
    await update.message.reply_text(
        step(5, (
            "🏛 *Qaysi oliy ta'lim muassasasini tamomlagansiz?*\n\n"
            "📌 Misol:\n"
            "• Toshkent davlat pedagogika universiteti\n"
            "• O'zbekiston Milliy universiteti\n"
            "• Nizomiy nomidagi TDPU\n\n"
            "✍️ Universitetingizni yozing yoki o'tkazib yuboring:"
        )),
        parse_mode="Markdown",
        reply_markup=SKIP,
    )
    return S_UNIVERSITY


# ── 5. Universitet ────────────────────────────────────────────────────────────
async def s_university(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not skip_text(update.message.text):
        context.user_data["university"] = update.message.text.strip()
    await update.message.reply_text(
        step(6, (
            "📚 *Mutaxassisligingiz?*\n\n"
            "📌 Misol:\n"
            "• Matematika\n"
            "• Ingliz tili va adabiyoti\n"
            "• Boshlang'ich ta'lim\n\n"
            "✍️ Mutaxassisligingizni yozing yoki o'tkazib yuboring:"
        )),
        parse_mode="Markdown",
        reply_markup=SKIP,
    )
    return S_SPECIALIZATION


# ── 6. Mutaxassislik ─────────────────────────────────────────────────────────
async def s_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not skip_text(update.message.text):
        context.user_data["specialization"] = update.message.text.strip()
    await update.message.reply_text(
        step(7, (
            "📖 *Qaysi fanlarni o'qitasiz?*\n\n"
            "📌 Misol:\n"
            "• Algebra, Geometriya\n"
            "• Ingliz tili, Rus tili\n"
            "• Fizika, Kimyo\n\n"
            "✍️ Fanlarni vergul bilan yozing yoki o'tkazib yuboring:"
        )),
        parse_mode="Markdown",
        reply_markup=SKIP,
    )
    return S_SUBJECTS


# ── 7. Fanlar ─────────────────────────────────────────────────────────────────
async def s_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not skip_text(update.message.text):
        context.user_data["subjects"] = update.message.text.strip()
    await update.message.reply_text(
        step(8, "🇬🇧 *IELTS sertifikatingiz bormi?*"),
        parse_mode="Markdown",
        reply_markup=YES_NO,
    )
    return S_HAS_IELTS


# ── 8. IELTS ──────────────────────────────────────────────────────────────────
async def s_has_ielts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    has = "ha" in update.message.text.lower()
    context.user_data["has_ielts"] = 1 if has else 0
    if has:
        await update.message.reply_text(
            step(8, (
                "🇬🇧 *IELTS ballingizni kiriting:*\n\n"
                "📌 Misol: `6.0` yoki `7.5`\n\n"
                "✍️ Ballingizni yozing:"
            )),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return S_IELTS_SCORE
    await update.message.reply_text(
        step(9, "🌍 *CEFR sertifikatingiz bormi?*"),
        parse_mode="Markdown",
        reply_markup=YES_NO,
    )
    return S_HAS_CEFR


async def s_ielts_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ielts_score"] = update.message.text.strip()
    await update.message.reply_text(
        step(9, "🌍 *CEFR sertifikatingiz bormi?*"),
        parse_mode="Markdown",
        reply_markup=YES_NO,
    )
    return S_HAS_CEFR


# ── 9. CEFR ───────────────────────────────────────────────────────────────────
async def s_has_cefr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    has = "ha" in update.message.text.lower()
    context.user_data["has_cefr"] = 1 if has else 0
    if has:
        await update.message.reply_text(
            step(9, "🌍 *CEFR darajangizni tanlang:*\n\nTugmani bosing 👇"),
            parse_mode="Markdown",
            reply_markup=CEFR_KB,
        )
        return S_CEFR_LEVEL
    await update.message.reply_text(
        step(10, "📜 *Milliy sertifikatingiz bormi?*\n_(O'zbekiston Milliy sertifikati)_"),
        parse_mode="Markdown",
        reply_markup=YES_NO,
    )
    return S_HAS_CERT


async def s_cefr_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["cefr_level"] = update.message.text.strip()
    await update.message.reply_text(
        step(10, "📜 *Milliy sertifikatingiz bormi?*\n_(O'zbekiston Milliy sertifikati)_"),
        parse_mode="Markdown",
        reply_markup=YES_NO,
    )
    return S_HAS_CERT


# ── 10. Milliy sertifikat ────────────────────────────────────────────────────
async def s_has_cert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    has = "ha" in update.message.text.lower()
    context.user_data["has_national_cert"] = 1 if has else 0
    await update.message.reply_text(
        step(11, (
            "📝 *O'zingiz haqingizda qisqacha yozing (bio):*\n\n"
            "📌 Misol:\n"
            "_\"10 yildan ortiq tajribaga ega bo'lgan matematika o'qituvchisi. "
            "Olimpiadachilarni tayyorlayman. Innovatsion ta'lim usullarini qo'llayman.\"_\n\n"
            "✍️ O'zingiz haqingizda yozing yoki o'tkazib yuboring:"
        )),
        parse_mode="Markdown",
        reply_markup=SKIP,
    )
    return S_BIO


# ── 11. Bio ───────────────────────────────────────────────────────────────────
async def s_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not skip_text(update.message.text):
        context.user_data["bio"] = update.message.text.strip()
    await update.message.reply_text(
        step(12, (
            "📸 *Professional rasmingizni yuboring*\n\n"
            "⚠️ Bu *majburiy* qadam!\n\n"
            "✅ Rasm talablari:\n"
            "• Yuqori sifatli (kamida 500×500 piksel)\n"
            "• Yuz aniq ko'rinsin\n"
            "• Professional ko'rinish (kostyum yoki rasmiy kiyim)\n"
            "• Yorug' fon yaxshiroq\n"
            "• Selfie emas, to'g'ri suratga olingan\n\n"
            "📎 Rasmni yuboring 👇"
        )),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return S_PHOTO


# ── 12. Rasm (MAJBURIY) ───────────────────────────────────────────────────────
async def s_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text(
            "❗ Iltimos, *rasm yuboring*.\n\n"
            "Faylni emas, to'g'ridan-to'g'ri rasmni yuboring 📎",
            parse_mode="Markdown",
        )
        return S_PHOTO

    # Eng yuqori sifatli rasmni olamiz (ro'yxatning oxirgisi)
    best_photo = update.message.photo[-1]
    file = await best_photo.get_file()
    uid = update.effective_user.id
    path = os.path.join(PHOTOS_DIR, f"{uid}.jpg")
    await file.download_to_drive(path)
    context.user_data["photo_path"] = path

    await update.message.reply_text(
        step(13, (
            "🏆 *Mukofot va yutuqlaringiz:*\n\n"
            "📌 Misol:\n"
            "• 2023 — Yilning eng yaxshi o'qituvchisi (tuman)\n"
            "• 2022 — Respublika olimpiadasi g'olibi bilan ishlagan\n"
            "• 2021 — Xalqaro konferensiya sertifikati\n\n"
            "✍️ Har bir mukofotni yangi qatordan yozing yoki o'tkazib yuboring:"
        )),
        parse_mode="Markdown",
        reply_markup=SKIP,
    )
    return S_AWARDS


# ── 13. Mukofotlar ────────────────────────────────────────────────────────────
async def s_awards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not skip_text(update.message.text):
        context.user_data["awards"] = update.message.text.strip()
    await send_summary(update, context)
    return S_CONFIRM


async def send_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    ielts_line = f"✅ Ha  |  Ball: *{d.get('ielts_score', '—')}*" if d.get("has_ielts") else "❌ Yo'q"
    cefr_line  = f"✅ Ha  |  Daraja: *{d.get('cefr_level', '—')}*" if d.get("has_cefr") else "❌ Yo'q"
    cert_line  = "✅ Ha" if d.get("has_national_cert") else "❌ Yo'q"

    text = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *USTOZ PROFILI — TEKSHIRUV*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *Ism-familiya:*  {d.get('full_name', '—')}\n"
        f"💼 *Lavozim:*  {d.get('position', '—')}\n"
        f"🎓 *Daraja:*  {d.get('degree', '—')}\n"
        f"📅 *Tajriba:*  {d.get('experience_years', '—')} yil\n\n"
        f"🏛 *Oliy ta'lim:*  {d.get('university', '—')}\n"
        f"📚 *Mutaxassislik:*  {d.get('specialization', '—')}\n"
        f"📖 *Fanlar:*  {d.get('subjects', '—')}\n\n"
        f"🇬🇧 *IELTS:*  {ielts_line}\n"
        f"🌍 *CEFR:*  {cefr_line}\n"
        f"📜 *Milliy sertifikat:*  {cert_line}\n\n"
        f"📸 *Rasm:*  ✅ Yuklangan\n"
        f"📝 *Bio:*  {d.get('bio', '—')}\n"
        f"🏆 *Mukofotlar:*  {d.get('awards', '—')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Ma'lumotlar to'g'rimi?"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=CONFIRM_KB)


# ── 14. Tasdiqlash ────────────────────────────────────────────────────────────
async def s_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text or ""

    if "Tasdiqlash" in text:
        uid = update.effective_user.id
        data = {k: v for k, v in context.user_data.items() if v is not None}
        upsert_teacher(uid, data)
        context.user_data.clear()
        await update.message.reply_text(
            "🎉 *Tabriklaymiz!*\n\n"
            "✅ Ma'lumotlaringiz muvaffaqiyatli saqlandi!\n"
            "Tez orada saytga qo'shiladi.\n\n"
            "👁 Profilingizni ko'rish uchun: /profile",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    elif "Qayta" in text or "yangilab" in text.lower():
        context.user_data.clear()
        await update.message.reply_text(
            "🔄 Qayta boshlaymiz.\n\nTo'liq *ism-familiyangizni* yozing:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return S_NAME

    else:
        await update.message.reply_text(
            "Iltimos, tugmalardan birini tanlang 👇",
            reply_markup=CONFIRM_KB,
        )
        return S_CONFIRM


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Bekor qilindi.\n/start — qayta boshlash uchun.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ── /profile ──────────────────────────────────────────────────────────────────
async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_teacher(update.effective_user.id)
    if not row:
        await update.message.reply_text(
            "Siz hali ro'yxatdan o'tmagansiz.\n/start yuboring.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    d = dict(row)
    ielts_line = f"✅ Ha  |  Ball: *{d.get('ielts_score', '—')}*" if d.get("has_ielts") else "❌ Yo'q"
    cefr_line  = f"✅ Ha  |  Daraja: *{d.get('cefr_level', '—')}*" if d.get("has_cefr") else "❌ Yo'q"
    cert_line  = "✅ Ha" if d.get("has_national_cert") else "❌ Yo'q"
    text = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 *USTOZ PROFILI*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *{d.get('full_name', '—')}*\n"
        f"💼 {d.get('position', '—')}\n"
        f"🎓 {d.get('degree', '—')}  |  📅 {d.get('experience_years', '—')} yil\n\n"
        f"🏛 {d.get('university', '—')}\n"
        f"📚 {d.get('specialization', '—')}\n"
        f"📖 {d.get('subjects', '—')}\n\n"
        f"🇬🇧 IELTS: {ielts_line}\n"
        f"🌍 CEFR: {cefr_line}\n"
        f"📜 Milliy sertifikat: {cert_line}\n"
    )
    if d.get("bio"):
        text += f"\n📝 _{d['bio']}_\n"
    if d.get("awards"):
        text += f"\n🏆 *Mukofotlar:*\n{d['awards']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")
    if d.get("photo_path") and os.path.exists(d["photo_path"]):
        with open(d["photo_path"], "rb") as f:
            await update.message.reply_photo(f, caption=f"📸 {d.get('full_name', '')}")


# ── Admin ──────────────────────────────────────────────────────────────────────
def is_admin(uid): return uid in ADMIN_IDS


async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    rows = get_all_teachers()
    if not rows:
        await update.message.reply_text("Hozircha hech kim ro'yxatdan o'tmagan.")
        return
    lines = [f"👥 *Jami: {len(rows)} ta ustoz*\n"]
    for i, r in enumerate(rows, 1):
        name = r["full_name"] or "—"
        pos  = r["position"] or "—"
        exp  = r["experience_years"] or 0
        lines.append(f"{i}. *{name}*\n   💼 {pos}  |  📅 {exp} yil\n   🆔 `{r['telegram_id']}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    rows = get_all_teachers()
    if not rows:
        await update.message.reply_text("Ma'lumot yo'q.")
        return

    data = [dict(r) for r in rows]
    await update.message.reply_text("⏳ Fayllar tayyorlanmoqda...")

    # Excel
    xl_path = export_excel(data)
    with open(xl_path, "rb") as f:
        await update.message.reply_document(
            f, filename="ustozlar.xlsx",
            caption=f"📊 Jami *{len(rows)}* ta ustoz ma'lumoti",
            parse_mode="Markdown",
        )
    os.remove(xl_path)

    # Rasmlar ZIP
    zip_path, photo_count = export_photos_zip(data)
    if photo_count > 0:
        with open(zip_path, "rb") as f:
            await update.message.reply_document(
                f, filename="rasmlar.zip",
                caption=f"📸 Jami *{photo_count}* ta ustoz rasmi (ZIP)",
                parse_mode="Markdown",
            )
        os.remove(zip_path)
    else:
        os.remove(zip_path)
        await update.message.reply_text("📸 Hozircha rasm yuklamagan ustozlar.")


async def admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bitta ustoz rasmini yuborish: /photo <telegram_id>"""
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "Foydalanish: `/photo <telegram_id>`\n\n"
            "Telegram ID larni ko'rish uchun: /list",
            parse_mode="Markdown",
        )
        return
    from database import get_teacher
    row = get_teacher(int(args[0]))
    if not row:
        await update.message.reply_text("❌ Bunday ID li ustoz topilmadi.")
        return
    d = dict(row)
    if not d.get("photo_path") or not os.path.exists(d["photo_path"]):
        await update.message.reply_text(
            f"❌ *{d.get('full_name', '—')}* rasim yuklamagan.",
            parse_mode="Markdown",
        )
        return
    with open(d["photo_path"], "rb") as f:
        await update.message.reply_photo(
            f,
            caption=(
                f"📸 *{d.get('full_name', '—')}*\n"
                f"💼 {d.get('position', '—')}\n"
                f"🆔 `{d['telegram_id']}`"
            ),
            parse_mode="Markdown",
        )


async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Foydalanish: /delete <telegram_id>")
        return
    delete_teacher(int(args[0]))
    await update.message.reply_text(f"✅ O'chirildi: `{args[0]}`", parse_mode="Markdown")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("update", start),
        ],
        states={
            S_NAME:         [MessageHandler(filters.TEXT & ~filters.COMMAND, s_name)],
            S_POSITION:     [MessageHandler(filters.TEXT & ~filters.COMMAND, s_position)],
            S_DEGREE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, s_degree)],
            S_EXPERIENCE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, s_experience)],
            S_UNIVERSITY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, s_university)],
            S_SPECIALIZATION:[MessageHandler(filters.TEXT & ~filters.COMMAND, s_specialization)],
            S_SUBJECTS:     [MessageHandler(filters.TEXT & ~filters.COMMAND, s_subjects)],
            S_HAS_IELTS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, s_has_ielts)],
            S_IELTS_SCORE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, s_ielts_score)],
            S_HAS_CEFR:     [MessageHandler(filters.TEXT & ~filters.COMMAND, s_has_cefr)],
            S_CEFR_LEVEL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, s_cefr_level)],
            S_HAS_CERT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, s_has_cert)],
            S_BIO:          [MessageHandler(filters.TEXT & ~filters.COMMAND, s_bio)],
            S_PHOTO:        [
                MessageHandler(filters.PHOTO, s_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, s_photo),
            ],
            S_AWARDS:       [MessageHandler(filters.TEXT & ~filters.COMMAND, s_awards)],
            S_CONFIRM:      [MessageHandler(filters.TEXT & ~filters.COMMAND, s_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("list", admin_list))
    app.add_handler(CommandHandler("export", admin_export))
    app.add_handler(CommandHandler("photo", admin_photo))
    app.add_handler(CommandHandler("delete", admin_delete))

    logger.info("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
