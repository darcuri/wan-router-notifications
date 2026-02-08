# Creating a Telegram Bot for Notifications

## Step 1: Create the Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat and send `/newbot`
3. Follow prompts:
   - Bot name: `WAN Router Monitor` (or your choice)
   - Bot username: `your_wan_monitor_bot` (must end in `bot`)
4. Save the **bot token** - looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

## Step 2: Get Your Chat ID

1. Start a chat with your new bot (search for it by username)
2. Send any message to the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find `"chat":{"id":` in the response - that number is your chat ID

## Step 3: Configure the Application

Add to your `.env` file:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

## Step 4: Test

Run the monitor in mock mode to verify Telegram works:

```bash
python -m local.main --mock-snmp -v
```

You should see test messages in your Telegram chat.

## Troubleshooting

- **No messages received**: Make sure you've started a chat with the bot first
- **401 Unauthorized**: Check your bot token is correct
- **Chat not found**: Verify the chat ID is correct
