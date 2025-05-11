# -*- coding: utf-8 -*-
    import logging
    import json
    import os
    from telegram import Update, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton
    from telegram.error import ChatMigrated
    from telegram.ext import (
        ApplicationBuilder,
        MessageHandler,
        filters,
        CommandHandler,
        CallbackQueryHandler,
        ContextTypes
    )

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

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        my_username = load_my_username()
        target_chat_id = load_target_chat_id()

        if not update.message:
            return

        text = update.message.text or ""
        print(f"📩 Bot nhận tin nhắn: {text}")
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
            "text": text,
            "chat_title": update.message.chat.title or "Private",
            "chat_id": update.message.chat.id,
            "message_id": update.message.message_id,
            "status": "pending"
        }
        MENTION_TASKS.append(task)
        save_tasks()

        index = len([t for t in MENTION_TASKS if t["status"] == "pending"])

        summary = (
            f"📌 Mention từ [@{task['from']}] trong *{task['chat_title']}*
"
            f"Nội dung:
```{task['text']}```
"
            f"Trạng thái: ❗ Chưa xử lý
"
            f"Dùng /todo để xem danh sách"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Đã xử lý", callback_data=f"done_{index-1}")]
        ])

        try:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=summary,
                parse_mode="Markdown",
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
                parse_mode="Markdown",
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
                await query.edit_message_text(f"✅ Đã xử lý mention từ @{MENTION_TASKS[idx]['from']}")
            else:
                await query.edit_message_text("❌ Không tìm thấy mention.")

    async def todo_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
        load_tasks()
        pending = [t for t in MENTION_TASKS if t['status'] == 'pending']
        if not pending:
            await update.message.reply_text("✅ Không có mention nào đang chờ.")
            return

        response = "📋 *Mention chưa xử lý:*
"
        for i, task in enumerate(pending):
            response += f"{i+1}. @{task['from']} - {task['text'][:40]}...
"
        await update.message.reply_text(response, parse_mode="Markdown")

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

        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(CommandHandler("todo", todo_list))
        app.add_handler(CommandHandler("done", done))
        app.add_handler(CommandHandler("remind", remind))
        app.add_handler(CallbackQueryHandler(handle_done_button))

        print("🚀 Bot đang chạy. Đang lắng nghe @mention...")
        app.run_polling()