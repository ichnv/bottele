# -*- coding: utf-8 -*-
import logging
import json
import os
import html
import uuid
from telegram import Update, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import ChatMigrated
from telegram.ext import (
        ApplicationBuilder,
        MessageHandler,
        filters,
        CommandHandler,
        CallbackQueryHandler,
        ContextTypes,
        ChatMemberHandler
    )
from datetime import datetime

MENTION_TASKS = []
DATA_FILE = "data/mention_tasks.json"
TOKEN_FILE = "config/token.txt"
TARGET_CHAT_FILE = "config/target_chat.txt"
USERNAME_FILE = "config/username.txt"

logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

def load_token():
        return open(TOKEN_FILE).read().strip()

def load_target_chat_id():
        return int(open(TARGET_CHAT_FILE).read().strip())

def save_target_chat_id(chat_id):
        with open(TARGET_CHAT_FILE, "w") as f:
            f.write(str(chat_id))

def load_my_username():
        return open(USERNAME_FILE).read().strip().lower()

def save_tasks():
        with open(DATA_FILE, "w") as f:
            json.dump(MENTION_TASKS, f, indent=2)

def load_tasks():
        global MENTION_TASKS
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                MENTION_TASKS = json.load(f)
        else:
            MENTION_TASKS = []

async def greet_on_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.my_chat_member

    if member.new_chat_member.status == "member":
        chat_id = member.chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Hi there! I help Mr. Ich track and respond to his messages.\n"
                "Ping me if you want Mr. Ich to see something fast!"
            )
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        my_username = load_my_username()
        target_chat_id = load_target_chat_id()

        if not update.message:
            return

        text = update.message.text or ""
        chat_id = update.message.chat.id
        chat_title = update.message.chat.title or "Private"
        print(f"📩 Bot nhận tin nhắn từ nhóm: {chat_title} (chat_id = {chat_id})")
        entities = update.message.entities or []

        mentioned = False
        for entity in entities:
            if entity.type == MessageEntity.MENTION:
                mention_text = text[entity.offset:entity.offset + entity.length]
                if mention_text.lower() in [f"@{my_username}", f"@{context.bot.username.lower()}"]:
                    mentioned = True
                    break

        if not mentioned:
            return

        task = {
            "from": update.message.from_user.username or update.message.from_user.first_name,
            "from_id": update.message.from_user.id,
            "text": text,
            "chat_title": update.message.chat.title or "Private",
            "chat_id": update.message.chat.id,
            "message_id": update.message.message_id,
            "status": "pending",
            "created": datetime.now().strftime("%Y-%m-%d")
        }
        MENTION_TASKS.append(task)
        save_tasks()

        index = len([t for t in MENTION_TASKS if t["status"] == "pending"])
        from_user = html.escape(task['from'])
        chat_title = html.escape(task['chat_title'])
        text = html.escape(task['text'])
        timestamp = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

        summary = (
                f"📌 <b>Mention</b> từ <b>@{from_user}</b> trong <b>{chat_title}</b>\n"
                f"🕐 <i>{timestamp}</i>\n\n"
                f"<pre>{text}</pre>\n"
                f"⏳ Trạng thái: <b>Chưa xử lý</b>"
            )

        keyboard = InlineKeyboardMarkup([
         [InlineKeyboardButton("📝 Đánh dấu là đã xử lý", callback_data=f"done_{len(MENTION_TASKS) - 1}")]
        ])

        try:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=summary,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            print(f"✅ Bot đã gửi tin nhắn tổng hợp về nhóm {target_chat_id}")
        except ChatMigrated as e:
            new_chat_id = e.new_chat_id
            print(f"⚠️ Chat migrated to new chat_id: {new_chat_id}. Cập nhật lại file.")
            save_target_chat_id(new_chat_id)
            await context.bot.send_message(
                chat_id=new_chat_id,
                text=summary,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as ex:
            print(f"❌ Lỗi khi gửi tin nhắn về nhóm: {ex}")

async def handle_done_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    load_tasks()
    data = query.data
    if data.startswith("done_"):
        idx = int(data.split("_")[1])
        if 0 <= idx < len(MENTION_TASKS):
            MENTION_TASKS[idx]['status'] = 'done'
            save_tasks()

            from_user = html.escape(MENTION_TASKS[idx]['from'])
            chat_title = html.escape(MENTION_TASKS[idx]['chat_title'])
            text = html.escape(MENTION_TASKS[idx]['text'])
            timestamp = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

            updated = (
                f"📌 <b>Mention</b> từ <b>@{from_user}</b> trong <b>{chat_title}</b>\n"
                f"🕐 <i>{timestamp}</i>\n\n"
                f"<pre>{text}</pre>\n"
                f"✅ Trạng thái: <b>Đã xử lý</b>"
            )

            await query.edit_message_text(updated, parse_mode="HTML")
            # Gửi trả lời tự động về nhóm A
            sender_id = MENTION_TASKS[idx].get("from_id")
            sender_name = MENTION_TASKS[idx].get("from", "người gửi")
            if sender_id:
                reply_text = (
                    f"🤖 Trả lời tự động: "
                    f"<a href='tg://user?id={sender_id}'>{html.escape(sender_name)}</a>, "
                    f"ichnv đã xử lý xong vấn đề của bạn."
                )

                await context.bot.send_message(
                    chat_id=MENTION_TASKS[idx]['chat_id'],
                    text=reply_text,
                    reply_to_message_id=MENTION_TASKS[idx]['message_id'],
                    parse_mode="HTML",
                    allow_sending_without_reply=True
                )
        else:
            await query.edit_message_text("❌ Không tìm thấy mention.", parse_mode="HTML")

async def todo_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_chat_id = load_target_chat_id()
    current_chat_id = update.message.chat.id

    if current_chat_id != target_chat_id:
        print(f"❌ /todo bị gọi từ nhóm không hợp lệ: {current_chat_id}")
        await update.message.reply_text("❌ Bạn không có quyền dùng /todo ở nhóm này.")
        return
    load_tasks()
    #pending = [t for t in MENTION_TASKS if t['status'] == 'pending']
    pending_with_index = [(idx, t) for idx, t in enumerate(MENTION_TASKS) if t['status'] == 'pending']

    if not pending_with_index:
        await update.message.reply_text("✅ Không có mention nào đang chờ.")
        return

    for idx, task in pending_with_index:
        from_user = html.escape(task['from'])
        chat_title = html.escape(task['chat_title'])
        text = html.escape(task['text'][:60])
        timestamp = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        status = task.get('status', 'pending')

        message = (
            f"📌 <b>Mention</b> từ <b>@{from_user}</b> trong <b>{chat_title}</b>\n"
            f"🕐 <i>{timestamp}</i>\n\n"
            f"<pre>{text}</pre>\n"
            f"⏳ Trạng thái: <b>Chưa xử lý</b>"
        )
        if status == 'pending':
                summary = (
                f"📌 <b>Mention</b> từ <b>@{from_user}</b> trong <b>{chat_title}</b>\n"
                f"🕐 <i>{timestamp}</i>\n\n"
                f"<pre>{text}</pre>\n"
                f"⏳ Trạng thái: <b>Chưa xử lý</b>"
        )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Đánh dấu là đã xử lý", callback_data=f"done_{idx}")]
                ])
        else:
            summary = (
            f"📌 <b>Mention</b> từ <b>@{from_user}</b> trong <b>{chat_title}</b>\n"
            f"🕐 <i>{timestamp}</i>\n\n"
            f"<pre>{text}</pre>\n"
            f"✅ Trạng thái: <b>Đã xử lý</b>"
        )
        keyboard = None

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Đã xử lý", callback_data=f"done_{idx}")]
        ])

        await update.message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=keyboard
        )

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_tasks()
    today_str = datetime.now().strftime("%Y-%m-%d")

    today_tasks = [t for t in MENTION_TASKS if t.get('created') == today_str]
    if not today_tasks:
        await update.message.reply_text("📭 Hôm nay không có mention nào.")
        return

    response = "📅 <b>Danh sách mention hôm nay:</b>\n\n"
    for i, task in enumerate(today_tasks):
        from_user = html.escape(task['from'])
        text = html.escape(task['text'][:50])
        status = task['status']
        status_str = "✅ Đã xử lý" if status == "done" else "⏳ Chưa xử lý"
        response += f"{i+1}. @{from_user}: <code>{text}</code>\n→ {status_str}\n\n"

    await update.message.reply_text(response.strip(), parse_mode="HTML")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            idx = int(context.args[0]) - 1
            load_tasks()
            pending = [t for t in MENTION_TASKS if t['status'] == 'pending']
            if 0 <= idx < len(pending):
                pending[idx]['status'] = 'done'
                save_tasks()
                await update.message.reply_text(f"✅ Đã đánh dấu mention #{idx+1} là đã xử lý.")
            else:
                await update.message.reply_text("⚠️ Số thứ tự không hợp lệ.")
        except:
            await update.message.reply_text("⚠️ Sai cú pháp. Dùng: /done <số thứ tự>")

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            idx = int(context.args[0]) - 1
            load_tasks()
            pending = [t for t in MENTION_TASKS if t['status'] == 'pending']
            if 0 <= idx < len(pending):
                pending[idx]['status'] = 'remind'
                save_tasks()
                await update.message.reply_text(f"⏰ Đã chuyển mention #{idx+1} sang trạng thái nhắc lại.")
            else:
                await update.message.reply_text("⚠️ Số thứ tự không hợp lệ.")
        except:
            await update.message.reply_text("⚠️ Sai cú pháp. Dùng: /remind <số thứ tự>")

if __name__ == '__main__':
        load_tasks()
        TOKEN = load_token()
        app = ApplicationBuilder().token(TOKEN).build()
        
        from telegram import ChatMember
        app.add_handler(ChatMemberHandler(
            greet_on_join,
            chat_member_types=[ChatMember.MEMBER]
        ))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(CommandHandler("todo", todo_list))
        app.add_handler(CommandHandler("today", today))
        app.add_handler(CommandHandler("done", done))
        app.add_handler(CommandHandler("remind", remind))
        app.add_handler(CallbackQueryHandler(handle_done_button))

        print("🚀 Bot đang chạy. Đang lắng nghe @mention...")
        app.run_polling()