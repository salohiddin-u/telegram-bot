import telebot
from flask import Flask, request
import os
import sqlite3
from datetime import datetime
from telebot import types

TOKEN = "8487961141:AAEjAq48IPTWP5KCVGNLT8mcYBU_i_A7qug"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
application = app  # for Passenger (important)

CHANNEL_ID = "@Averna_LC"
PRIVATE_CHANNEL_ID = "-1003097563211"

# --- Inline buttons ---
channel_link_btn = types.InlineKeyboardMarkup()
channel_link_btn.add(
    types.InlineKeyboardButton(
        text="AVERNA LC",
        url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"
    )
)
channel_link_btn.add(
    types.InlineKeyboardButton(
        text="✅ I Joined",
        callback_data="check_subscription"
    )
)

@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    json_str = request.stream.read().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url="https://nononerous-philomena-cluelessly.ngrok-free.dev/" + TOKEN)
    return "Webhook set!", 200


def user_exists(user):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("SELECT 1 FROM users WHERE user = ?", (user,))
    exists = cur.fetchone() is not None
    con.close()
    return exists

def edit_status(user):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("UPDATE users SET status = ? WHERE user = ?", ("True", user))
    con.commit()
    con.close()

def get_status(user_id):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("SELECT status FROM users WHERE user = ?", (user_id,))
    user = cur.fetchone()
    con.close()
    return user[0] if user else None

def add_user(user, inviter_id):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    print(user)
    print(inviter_id)
    cur.execute(
        "INSERT OR IGNORE INTO users (user, invited_id, time) VALUES (?, ?, ?)",
        (user, inviter_id, datetime.utcnow().isoformat())
    )
    con.commit()
    con.close()


def add_user_pending(invited_id, inviter_id):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("SELECT 1 FROM pending WHERE invited_id = ?", (invited_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO pending (inviter_id, invited_id) VALUES (?, ?)",
            (inviter_id, invited_id)
        )
        con.commit()
    con.close()


def remove_pending(invited_id):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("DELETE FROM pending WHERE invited_id = ?", (invited_id,))
    con.commit()
    con.close()


def get_pending_inviter(user_id):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("SELECT inviter_id FROM pending WHERE invited_id = ?", (user_id,))
    inviter = cur.fetchone()
    con.close()
    return inviter[0] if inviter else None


def get_invited_people(user_id):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("SELECT user FROM users WHERE invited_id = ?", (user_id,))
    invited_people = cur.fetchall()
    con.close()
    return [row[0] for row in invited_people] if invited_people else []


# --- Helper to parse command arguments ---
def get_command_args(message):
    parts = message.text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else None


# --- Command handlers ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    args = get_command_args(message)
    member = bot.get_chat_member(CHANNEL_ID, user_id)

    subscribed = member.status in ["member", "administrator", "creator"]

    if not subscribed:
        if args:
            add_user_pending(user_id, int(args))
        bot.send_message(user_id, "🚀 Please join the channel first to continue.", reply_markup=channel_link_btn)
        return

    if args:
        inviter_id = int(args)
        if inviter_id == user_id:
            bot.reply_to(message, "⚠️ You can’t invite yourself!")
            return
        if not user_exists(user_id):
            add_user(user_id, inviter_id)
            bot.send_message(user_id, "✅ Welcome! You’ve joined through an invite link.")
            bot.send_message(inviter_id, f"🎉 {message.from_user.first_name} has joined using your referral link!")
        else:
            bot.reply_to(message, "⚠️ You’ve already joined before.")
    else:
        if not user_exists(user_id):
            add_user(user_id, None)
            print(user_id)
        bot.send_message(
            user_id,
            "👋 Welcome! Invite 5 friends to unlock access to the marathon channel.\n\n💡 Use <b>/invite</b> to get your personal referral link.",
            parse_mode="HTML",
        )


@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription(call):
    user_id = call.from_user.id
    member = bot.get_chat_member(CHANNEL_ID, user_id)
    subscribed = member.status in ["member", "administrator", "creator"]

    if subscribed:
        inviter_id = get_pending_inviter(user_id)
        if inviter_id:
            remove_pending(user_id)
            add_user(user_id, inviter_id)
            bot.edit_message_text(
                "✅ Awesome! You’ve joined the channel. Now invite 5 friends to unlock access to the marathon.\n\n💡 Use /invite to get your personal referral link.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            bot.send_message(
                inviter_id,
                f"🎉 {call.from_user.first_name} has joined using your referral link!"
            )
        else:
            if not user_exists(user_id):
                add_user(user_id, None)
            bot.edit_message_text(
                "✅ Great! You’ve joined the channel. Invite 5 friends to gain access to the marathon.\n\n💡 Use /invite to get your referral link.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
    else:
        bot.answer_callback_query(
            call.id,
            "❌ You haven’t joined the channel yet. Please join it first, then try again.",
            show_alert=True
        )


@bot.message_handler(commands=['invite'])
def invite_handler(message):
    user_id = message.from_user.id
    member = bot.get_chat_member(CHANNEL_ID, user_id)

    subscribed = member.status in ["member", "administrator", "creator"]

    if not subscribed:
        return start_handler(message)
    bot_info = bot.get_me()
    invite_link = f"https://t.me/share/url?url=https://t.me/{bot_info.username}?start={user_id}"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="✉️ Invite", url=invite_link))
    bot.send_message(
        user_id,
        "📨 Share your referral link with your friends!\n\n📊 Use <b>/stat</b> to check your invitation stats.",
        reply_markup=markup,
        parse_mode="HTML"
    )


@bot.message_handler(commands=['stat'])
def stat_handler(message):
    user_id = message.from_user.id
    invited_people = get_invited_people(user_id)

    if invited_people:
        text = f"👥 You’ve invited <b>{len(invited_people)}</b> people:\n"
        text += "\n".join([f"• User ID: {i}" for i in invited_people])
        bot.send_message(user_id, text, parse_mode="HTML")
        if get_status(user_id) == "True":
            bot.send_message(user_id, "⚠️You've already got a link.")
        elif get_status(user_id) == None:
            if len(invited_people) >= 5:
                channel_link = bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1)
                edit_status(user_id)
                bot.send_message(
                    user_id,
                    f"🎉 Congratulations! You’ve invited 5 friends!\nHere’s your exclusive channel access link:\n{channel_link.invite_link}"
                )
            else:
                bot.send_message(
                    user_id,
                    f"🔑 You need to invite <b>{5 - len(invited_people)}</b> more friends to unlock the channel access link.",
                    parse_mode="HTML"
                )
    else:
        bot.send_message(user_id, "❌ You haven’t invited anyone yet. Start sharing your referral link to earn access!")


@bot.message_handler(commands=['admin'])
def total_handler(message):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()

    # Count all users
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    # Count those who joined via referral
    cur.execute("SELECT COUNT(*) FROM users WHERE invited_id IS NOT NULL")
    referred_users = cur.fetchone()[0]

    con.close()

    bot.send_message(
        message.chat.id,
        f"📊 Total registered users: <b>{total_users}</b>\n"
        f"🔗 Joined via referral links: <b>{referred_users}</b>",
        parse_mode="HTML"
    )



@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.reply_to(message, message.text)


if __name__ == "__main__":
    app.run()
