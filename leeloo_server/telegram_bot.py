#!/usr/bin/env python3
"""
LEELOO Telegram Bot
Handles device pairing and optional messaging from phone.
"""

import os
import asyncio
import json
from typing import Optional

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
except ImportError:
    print("Installing python-telegram-bot...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'python-telegram-bot'])
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Bot token from environment
BOT_TOKEN = os.environ.get('LEELOO_BOT_TOKEN', '')

# Store user state (in production, use Redis or similar)
user_state = {}  # telegram_user_id -> {crew_code, crew_id, display_name}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id

    welcome_text = f"""
Welcome to LEELOO, {user.first_name}!

LEELOO is a music sharing device that lets you and your friends push songs to each other.

**What would you like to do?**
"""

    keyboard = [
        [InlineKeyboardButton("Create New Crew", callback_data='create_crew')],
        [InlineKeyboardButton("Join Existing Crew", callback_data='join_crew')],
    ]

    # If user already has a crew, show that option
    if user_id in user_state and user_state[user_id].get('crew_code'):
        crew_code = user_state[user_id]['crew_code']
        keyboard.append([InlineKeyboardButton(f"My Crew: {crew_code}", callback_data='my_crew')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == 'create_crew':
        await create_crew(query, user_id)

    elif query.data == 'join_crew':
        await prompt_join_crew(query, user_id, context)

    elif query.data == 'my_crew':
        await show_my_crew(query, user_id)

    elif query.data == 'pair_device':
        await show_pairing_code(query, user_id)

    elif query.data == 'send_message':
        await prompt_send_message(query, user_id, context)


async def create_crew(query, user_id: int):
    """Create a new crew for user"""
    # Generate crew code (in production, this calls relay_server)
    import secrets
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = ''.join(secrets.choice(chars) for _ in range(4))
    crew_code = f"LEELOO-{code}"

    user_state[user_id] = {
        'crew_code': crew_code,
        'display_name': query.from_user.first_name
    }

    text = f"""
**Your crew has been created!**

Crew Code: `{crew_code}`

**Next steps:**
1. Power on your LEELOO device
2. When it shows "Join Crew", enter this code
3. Share this code with friends so they can join too!

Each crew member will need:
- Their own LEELOO device
- This crew code to connect
"""

    keyboard = [
        [InlineKeyboardButton("Pair My Device", callback_data='pair_device')],
        [InlineKeyboardButton("Send Message to Crew", callback_data='send_message')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def prompt_join_crew(query, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Ask user for crew code to join"""
    context.user_data['awaiting_crew_code'] = True

    text = """
**Join an Existing Crew**

Please enter the crew code your friend shared with you.

It looks like: `LEELOO-XXXX`
"""
    await query.edit_message_text(text, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages from user"""
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    # Check if awaiting crew code
    if context.user_data.get('awaiting_crew_code'):
        context.user_data['awaiting_crew_code'] = False
        await join_crew(update, user_id, text)
        return

    # Check if awaiting message to send
    if context.user_data.get('awaiting_message'):
        context.user_data['awaiting_message'] = False
        await send_crew_message(update, user_id, update.message.text)
        return

    # Otherwise, show help
    await update.message.reply_text(
        "Use /start to see options, or /help for more info."
    )


async def join_crew(update: Update, user_id: int, crew_code: str):
    """Join user to an existing crew"""
    # Validate crew code format
    if not crew_code.startswith('LEELOO-') or len(crew_code) != 11:
        await update.message.reply_text(
            "Invalid crew code format. It should look like: LEELOO-XXXX\n\nTry again or use /start"
        )
        return

    # In production, validate against relay_server
    # For now, just accept it
    user_state[user_id] = {
        'crew_code': crew_code,
        'display_name': update.effective_user.first_name
    }

    text = f"""
**You've joined the crew!**

Crew Code: `{crew_code}`

Your LEELOO device will now receive messages from this crew.

**Next steps:**
1. Make sure your LEELOO is connected to the same crew code
2. Messages you send here will appear on all crew devices!
"""

    keyboard = [
        [InlineKeyboardButton("Send Message to Crew", callback_data='send_message')],
        [InlineKeyboardButton("Back to Start", callback_data='start')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_my_crew(query, user_id: int):
    """Show user's current crew info"""
    state = user_state.get(user_id, {})
    crew_code = state.get('crew_code', 'Not joined')

    text = f"""
**Your Crew**

Crew Code: `{crew_code}`

Share this code with friends to add them to your crew!

**Options:**
"""

    keyboard = [
        [InlineKeyboardButton("Pair New Device", callback_data='pair_device')],
        [InlineKeyboardButton("Send Message", callback_data='send_message')],
        [InlineKeyboardButton("Leave Crew", callback_data='leave_crew')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def show_pairing_code(query, user_id: int):
    """Show pairing info for device"""
    state = user_state.get(user_id, {})
    crew_code = state.get('crew_code', '')

    if not crew_code:
        await query.edit_message_text("You need to create or join a crew first! Use /start")
        return

    text = f"""
**Pair Your LEELOO Device**

1. Power on your LEELOO device
2. Wait for the setup screen
3. Enter this crew code:

`{crew_code}`

Your device will connect to your crew automatically!

**Troubleshooting:**
- Make sure your LEELOO is connected to WiFi
- The code is case-insensitive
- Contact support if issues persist
"""

    keyboard = [
        [InlineKeyboardButton("Back", callback_data='my_crew')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def prompt_send_message(query, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to type a message"""
    state = user_state.get(user_id, {})
    if not state.get('crew_code'):
        await query.edit_message_text("You need to join a crew first! Use /start")
        return

    context.user_data['awaiting_message'] = True

    text = """
**Send Message to Crew**

Type your message below. It will appear on all LEELOO devices in your crew!

Keep it short - the display is small.
"""
    await query.edit_message_text(text, parse_mode='Markdown')


async def send_crew_message(update: Update, user_id: int, message_text: str):
    """Send a message to all crew devices"""
    state = user_state.get(user_id, {})
    crew_code = state.get('crew_code')
    display_name = state.get('display_name', 'Phone')

    if not crew_code:
        await update.message.reply_text("You need to join a crew first!")
        return

    # In production, this would call relay_server.TelegramBridge
    # For now, just confirm
    text = f"""
**Message Sent!**

From: {display_name}
To: Crew {crew_code}
Message: "{message_text}"

Your crew's LEELOO devices will display this message.
"""

    keyboard = [
        [InlineKeyboardButton("Send Another", callback_data='send_message')],
        [InlineKeyboardButton("Back to Crew", callback_data='my_crew')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    text = """
**LEELOO Help**

LEELOO is a music sharing device for you and your friends.

**Commands:**
/start - Main menu
/help - This help message
/crew - Show your crew info
/pair - Get device pairing code

**What is a Crew?**
A crew is a group of friends with LEELOO devices. When someone in your crew pushes a song, it shows up on everyone's device!

**How to Set Up:**
1. Create a crew (or get a code from a friend)
2. Connect your LEELOO device to your crew
3. Start sharing music!

**Questions?**
Contact us at support@leeloo.fm
"""
    await update.message.reply_text(text, parse_mode='Markdown')


def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("ERROR: Set LEELOO_BOT_TOKEN environment variable")
        print("Get a token from @BotFather on Telegram")
        return

    print("Starting LEELOO Telegram Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running! Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == '__main__':
    main()
