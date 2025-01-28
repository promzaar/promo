import os
import json
import logging
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import asyncio
import datetime

load_dotenv()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv('BOT_TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

OWNER_ID = int(os.getenv('OWNER_ID'))
REQUIRED_CHANNELS = ["@myworldmyruless", "@channel2", "@channel3"]
WITHDRAWAL_CHAT_ID = -1002279182532

REFERRAL_REWARD = 10
REFERRAL_BONUS = 5
CONVERSION_RATE = 10
DAILY_BONUS = 5

USER_DATA_FILE = "user_data.json"

class ReferralState(StatesGroup):
    waiting_for_upi = State()

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r') as f:
                data = f.read()
                if data:
                    return json.loads(data)
                else:
                    print("Warning: user_data.json is empty. Starting with an empty dictionary.")
                    return {}
        except json.JSONDecodeError:
            print("Error: user_data.json contains invalid JSON. Starting with an empty dictionary.")
            return {}
    else:
        print(f"Info: {USER_DATA_FILE} not found. Starting with an empty dictionary.")
        return {}

def save_user_data(data):
    try:
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving user data: {e}")

user_data = load_user_data()

async def check_channel_membership(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

main_menu_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💰 Balance", callback_data="balance"),
         InlineKeyboardButton(text="💳 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton(text="🏦 Set UPI", callback_data="setupi"),
         InlineKeyboardButton(text="🎁 Daily Bonus", callback_data="daily_bonus")],
        [InlineKeyboardButton(text="🤝 Refer Friends", callback_data="refer"),
         InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton(text="ℹ️ My Info", callback_data="info")],
    ]
)

@dp.message(Command(commands=["start"]))
async def send_welcome(message: types.Message):
    user_id = str(message.from_user.id)
    args = message.text.split()
    
    if user_id not in user_data:
        user_data[user_id] = {
            "balance": 0,
            "referrals": [],
            "upi_id": None,
            "withdrawals": [],
            "pending_withdrawal": None,
            "last_daily_bonus": None,
            "used_referral": False
        }
        save_user_data(user_data)
    
    if len(args) > 1 and args[1].startswith("ref_"):
        await handle_referral(message, args[1])
    
    if not await check_channel_membership(int(user_id)):
        join_buttons = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"Join {channel}", url=f"https://t.me/{channel[1:]}")] for channel in REQUIRED_CHANNELS]
        )
        await message.reply(
            "👋 Welcome to the UPI Money Refer and Earn bot!\n\n"
            "🚨 Important: You must join our channels to use this bot.\n"
            "Please join all channels and then use /start again. 🙏",
            reply_markup=join_buttons
        )
    else:
        image_url = f"https://picsum.photos/seed/{random.randint(1, 1000)}/500/300"
        await message.reply_photo(
            photo=image_url,
            caption=(
                f"🎉 Welcome to the UPI Money Refer and Earn bot! 🤑\n\n"
                f"Share your referral link to earn coins! 🪙\n\n"
                f"🔹 Each referral earns you {REFERRAL_REWARD} coins\n"
                f"🔹 {CONVERSION_RATE} coins = ₹1\n\n"
                f"Use the buttons below to navigate:"
            ),
            reply_markup=main_menu_keyboard
        )

async def handle_referral(message: types.Message, referral_code: str):
    user_id = str(message.from_user.id)
    referrer_id = referral_code[4:]
    
    if referrer_id == user_id:
        await message.reply("❌ You can't refer yourself!")
        return
    
    if user_data[user_id]["used_referral"]:
        await message.reply("❌ You've already used a referral code.")
        return
    
    if referrer_id in user_data:
        if user_id not in user_data[referrer_id]["referrals"]:
            user_data[referrer_id]["referrals"].append(user_id)
            user_data[referrer_id]["balance"] += REFERRAL_REWARD
            user_data[user_id]["balance"] += REFERRAL_BONUS
            user_data[user_id]["used_referral"] = True
            save_user_data(user_data)
            await message.reply(f"✅ Referral successful! You earned {REFERRAL_BONUS} coins.")
            await bot.send_message(int(referrer_id), f"🎉 New referral! You earned {REFERRAL_REWARD} coins.")
        else:
            await message.reply("❌ You've already been referred by this user.")
    else:
        await message.reply("❌ Invalid referral code.")

@dp.callback_query(F.data == "balance")
async def check_balance(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    balance = user_data.get(user_id, {}).get("balance", 0)
    rupees = balance // CONVERSION_RATE
    coins = balance % CONVERSION_RATE
    await callback_query.answer(f"💰 Your balance: {balance} coins (₹{rupees}.{coins:02d})", show_alert=True)

@dp.callback_query(F.data == "withdraw")
async def withdraw(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    user = user_data.get(user_id, {})
    balance = user.get("balance", 0)
    upi_id = user.get("upi_id")

    min_withdrawal = CONVERSION_RATE * 10

    if balance < min_withdrawal:
        await callback_query.answer(f"❌ Minimum withdrawal: {min_withdrawal} coins (₹10)", show_alert=True)
    elif not upi_id:
        await callback_query.answer("❌ Set UPI ID first using 'Set UPI' button", show_alert=True)
    elif user.get("pending_withdrawal"):
        await callback_query.answer("❌ You have a pending withdrawal", show_alert=True)
    else:
        rupees = balance // CONVERSION_RATE
        user_data[user_id]["balance"] = balance % CONVERSION_RATE
        user_data[user_id]["pending_withdrawal"] = rupees
        save_user_data(user_data)
        await callback_query.answer(f"✅ Withdrawal of ₹{rupees} requested", show_alert=True)
        
        image_url = f"https://picsum.photos/seed/{random.randint(1, 1000)}/500/300"
        withdrawal_message = (
            f"💰 New Withdrawal Request\n\n"
            f"👤 User ID: {user_id}\n"
            f"💳 UPI ID: {upi_id}\n"
            f"💵 Amount: ₹{rupees}\n\n"
            f"Please process this withdrawal request."
        )
        
        await bot.send_photo(
            WITHDRAWAL_CHAT_ID,
            photo=image_url,
            caption=withdrawal_message
        )
        
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Mark as Completed", callback_data=f"complete_withdrawal:{user_id}")]
        ])
        await bot.send_photo(
            OWNER_ID,
            photo=image_url,
            caption=withdrawal_message,
            reply_markup=admin_keyboard
        )

@dp.callback_query(F.data.startswith("complete_withdrawal:"))
async def complete_withdrawal(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("❌ You are not authorized to perform this action.", show_alert=True)
        return

    user_id = callback_query.data.split(":")[1]
    if user_id in user_data and user_data[user_id].get("pending_withdrawal"):
        amount = user_data[user_id]["pending_withdrawal"]
        user_data[user_id]["withdrawals"].append(amount)
        user_data[user_id]["pending_withdrawal"] = None
        save_user_data(user_data)
        
        await callback_query.message.edit_caption(
            caption=f"✅ Withdrawal of ₹{amount} for User ID: {user_id} has been completed."
        )
        await callback_query.answer("✅ Withdrawal marked as completed.", show_alert=True)
        await bot.send_message(int(user_id), f"✅ Your withdrawal of ₹{amount} has been processed and sent to your UPI ID.")
    else:
        await callback_query.answer("❌ Invalid withdrawal or already processed.", show_alert=True)

@dp.callback_query(F.data == "refer")
async def refer_prompt(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    await callback_query.answer()
    await callback_query.message.reply(
        f"🤝 Your referral link is: {referral_link}\n"
        f"Share this link with your friends. When they join using your link, both of you will earn coins!"
    )

@dp.callback_query(F.data == "setupi")
async def set_upi_start(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await state.set_state(ReferralState.waiting_for_upi)
    await callback_query.message.reply("🏦 Please enter your UPI ID:")

@dp.message(ReferralState.waiting_for_upi)
async def set_upi_done(message: types.Message, state: FSMContext):
    upi_id = message.text.strip()
    user_id = str(message.from_user.id)
    
    if '@' not in upi_id:
        await message.reply("❌ Invalid UPI ID format. Please try again.")
        return

    user_data[user_id] = user_data.get(user_id, {"balance": 0, "referrals": [], "upi_id": None, "withdrawals": [], "pending_withdrawal": None, "last_daily_bonus": None})
    user_data[user_id]["upi_id"] = upi_id
    save_user_data(user_data)
    await state.clear()
    await message.reply(f"✅ Your UPI ID has been set to: {upi_id}")

@dp.callback_query(F.data == "daily_bonus")
async def daily_bonus(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    user = user_data.get(user_id, {})
    
    today = datetime.date.today().isoformat()
    
    if user.get("last_daily_bonus") == today:
        await callback_query.answer("❌ You've already claimed your daily bonus today", show_alert=True)
    else:
        user_data[user_id]["balance"] = user.get("balance", 0) + DAILY_BONUS
        user_data[user_id]["last_daily_bonus"] = today
        save_user_data(user_data)
        await callback_query.answer(f"✅ You've received {DAILY_BONUS} coins as your daily bonus!", show_alert=True)

@dp.callback_query(F.data == "leaderboard")
async def show_leaderboard(callback_query: types.CallbackQuery):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]['balance'], reverse=True)
    top_10 = sorted_users[:10]
    
    leaderboard = "🏆 Top 10 Earners:\n\n"
    for i, (user_id, data) in enumerate(top_10, 1):
        leaderboard += f"{i}. User{user_id}: {data['balance']} coins\n"
    
    await callback_query.answer()
    await callback_query.message.reply(leaderboard)

@dp.callback_query(F.data == "info")
async def show_user_info(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    user = user_data.get(user_id, {})
    
    balance = user.get("balance", 0)
    upi_id = user.get("upi_id", "Not set")
    referrals = len(user.get("referrals", []))
    last_daily_bonus = user.get("last_daily_bonus", "Not claimed yet")
    
    today = datetime.date.today().isoformat()
    can_claim_bonus = last_daily_bonus != today
    
    info_message = (
        f"👤 User Information\n\n"
        f"🆔 User ID: {user_id}\n"
        f"💰 Balance: {balance} coins\n"
        f"🏦 UPI ID: {upi_id}\n"
        f"🤝 Referrals: {referrals}\n"
        f"🎁 Daily Bonus: {'Available ✅' if can_claim_bonus else 'Claimed today ❌'}\n"
        f"📅 Last Bonus Claim: {last_daily_bonus}\n\n"
        f"Use the buttons below to navigate:"
    )
    
    await callback_query.answer()
    await callback_query.message.reply(info_message, reply_markup=main_menu_keyboard)

@dp.message(Command(commands=["panel"]))
async def admin_panel(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return

    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Bot Statistics", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💰 Pending Withdrawals", callback_data="admin_pending_withdrawals")],
            [InlineKeyboardButton(text="👥 User Management", callback_data="admin_user_management")],
        ]
    )

    await message.reply(
        "🔐 Admin Panel\n\n"
        "Welcome to the admin panel. Please select an option:",
        reply_markup=admin_keyboard
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("❌ You are not authorized to view this information.", show_alert=True)
        return

    total_users = len(user_data)
    total_balance = sum(user["balance"] for user in user_data.values())
    total_referrals = sum(len(user["referrals"]) for user in user_data.values())
    total_withdrawals = sum(len(user["withdrawals"]) for user in user_data.values())
    
    stats_message = (
        f"📊 Bot Statistics:\n\n"
        f"👥 Total Users: {total_users}\n"
        f"💰 Total Balance: {total_balance} coins\n"
        f"🤝 Total Referrals: {total_referrals}\n"
        f"💳 Total Withdrawals: {total_withdrawals}"
    )
    
    await callback_query.message.edit_text(stats_message)

@dp.callback_query(F.data == "admin_pending_withdrawals")
async def admin_pending_withdrawals(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("❌ You are not authorized to view this information.", show_alert=True)
        return

    pending_withdrawals = [
        (user_id, data["pending_withdrawal"], data["upi_id"])
        for user_id, data in user_data.items()
        if data.get("pending_withdrawal")
    ]

    if not pending_withdrawals:
        await callback_query.message.edit_text("No pending withdrawals at the moment.")
        return

    message = "💰 Pending Withdrawals:\n\n"
    for user_id, amount, upi_id in pending_withdrawals:
        message += f"User ID: {user_id}\nAmount: ₹{amount}\nUPI ID: {upi_id}\n\n"

    await callback_query.message.edit_text(message)

@dp.callback_query(F.data == "admin_user_management")
async def admin_user_management(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("❌ You are not authorized to access this feature.", show_alert=True)
        return

    user_management_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban_user")],
            [InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban_user")],
            [InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
    )

    await callback_query.message.edit_text(
        "👥 User Management\n\n"
        "Select an option:",
        reply_markup=user_management_keyboard
    )

@dp.message()
async def echo(message: types.Message):
    await message.reply("❓ I don't understand that command. Use /start to see available options.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

