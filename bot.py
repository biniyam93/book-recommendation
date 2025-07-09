from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from test import BookRecommender  # Make sure the filename is correct!

# Initialize your recommender once
recommender = BookRecommender()

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm your Book Recommendation Bot.\n"
        "Tell me what you like to read!"
    )

# Message handler for user queries
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    reply = recommender.recommend(user_query)
    await update.message.reply_text(reply)

def main():
    TELEGRAM_TOKEN = "her the token"  # <<< Replace with your bot token!

    # Build the app
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running... Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
