from datetime import datetime
import os
import asyncio
import sqlite3

from aiogram.enums import ChatMemberStatus
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
import uvicorn
from aiogram.filters import Command, CommandObject


BOT_TOKEN = "7979914433:AAFRxIJpK0JSr82489Id6MWUHcaqsnghFyI"
WEBHOOK_URL = "https://nononerous-philomena-cluelessly.ngrok-free.dev/webhook"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CHANNEL_ID = "@chaenlle3"

channel_link_btn = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Channel Name",
                url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="✅ I joined",
                callback_data="check_subscription"
            )
        ]
    ]
)


def user_exists(user):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("SELECT 1 FROM users WHERE user = ?", (user,))
    exists = cur.fetchone() is not None
    con.close()
    return exists


def add_user(user, inviter_id):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user, invited_id, time) VALUES (?, ?, ?)",
        (user, inviter_id, datetime.utcnow().isoformat()),
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


def get_inviter(user_id):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute("SELECT invited_id FROM users WHERE user = ?", (user_id,))
    inviter = cur.fetchone()
    con.close()
    return inviter[0] if inviter else None


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


@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
    subscribed = member.status in [
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR
    ]

    if subscribed:
        inviter_id = get_pending_inviter(user_id)
        if inviter_id:
            remove_pending(invited_id=user_id)
            add_user(user_id, inviter_id)
            await callback.message.edit_text("✅ Great! You’ve joined the channel.")
            await bot.send_message(
                inviter_id,
                f"🎉 {callback.from_user.first_name} joined using your referral link!"
            )
        else:
            add_user(user_id, None)
            await callback.message.edit_text("✅ Great! You’ve joined the channel.")
    else:
        await callback.answer(
            "❌ Still not joined. Please join and try again.",
            show_alert=True
        )


@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
    subscribed = member.status in [
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR
    ]

    if not subscribed:
        if command.args:
            add_user_pending(user_id, int(command.args))
        await message.answer("Please, join the channel.", reply_markup=channel_link_btn)
        return
    else:
        if command.args:
            inviter_id = int(command.args)
            if inviter_id == user_id:
                await message.answer("⚠️ You cannot invite yourself!")
                return

            if not user_exists(user_id):
                add_user(user_id, inviter_id)
                await message.answer("✅ Welcome! You joined via an invite.")
                await bot.send_message(
                    inviter_id,
                    f"🎉 {message.from_user.first_name} joined using your link!"
                )
            else:
                await message.reply("✅ You already joined.")
        else:
            if not user_exists(user_id):
                add_user(user_id, None)
            await message.answer(
                "👋 Welcome! Invite friends and get an access to the marathon channel.\n\n"
                "<i>Use /invite to get your referral link.</i>",
                parse_mode="HTML",
                reply_markup=channel_link_btn
            )


@dp.message(Command("invite"))
async def invite_handler(message: types.Message):
    user_id = message.from_user.id
    bot_username = (await bot.get_me()).username
    invite_link = f"https://t.me/share/url?url=https://t.me/{bot_username}?start={user_id}"

    await message.reply(
        "📨 Share your referral link with friends!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✉️ Invite", url=invite_link)]
            ]
        )
    )


@dp.message(Command("stat"))
async def get_handler(message: types.Message):
    user_id = message.from_user.id
    invited_people = get_invited_people(user_id)

    if invited_people:
        await message.answer(
            f"👥 You invited {len(invited_people)} people:\n" +
            "\n".join([f"• {i}" for i in invited_people])
        )
        if len(invited_people)>=10:
            channel_link = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
            await message.answer(f"🎉 Congratulations! You have 10 people. \nHere is the channel link: {channel_link.invite_link}")
    else:
        await message.answer("❌ You haven’t invited anyone yet.")


@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"{message.text}")


app = FastAPI()


@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook set to: {WEBHOOK_URL}")


@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()


@app.post("/webhook")
async def process_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def home():
    return {"status": "Bot is running with webhook!"}


if __name__ == "__main__":
    uvicorn.run("bot:app", host="0.0.0.0", port=5500)
