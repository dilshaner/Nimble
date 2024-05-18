import telebot
import requests
import threading
import time

bot_token = "5404890563:AAHZRg1u774XC4mGv95VP3nbocXYoNTbw44"
bot = telebot.TeleBot(bot_token)

user_data = {}
channel_id = -1002077759391
start_time = time.time()


def generate_ascii_graph(earnings_data, time_unit):
    max_earnings = max(earnings_data.values())
    ascii_graph = ""
    for time_stamp, earnings in earnings_data.items():
        bar_length = int((earnings / max_earnings) * 10)
        ascii_graph += f"{time_stamp}: {earnings} {'|' * bar_length}\n"
    return ascii_graph


def send_loading_animation(chat_id):
    message = bot.send_message(chat_id, "Checking balance [░░░░░░░░░░░░░░] 0%")
    for i in range(1, 11):
        progress = i * 10
        text = f"Checking balance [{'▒' * i}{'░' * (10 - i)}] {progress}%"
        bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=text)
        time.sleep(0.01)  # Adjust the sleep duration to control the speed of animation


def get_balance(wallet_address):
    try:
        response = requests.post('https://nimble-api.urlrevealer.com/check_balance', json={'address': wallet_address})
        if response.status_code == 200:
            data = response.json()
            return data.get('msg', 'Error: No message in response')
        else:
            return f"Error: Unable to fetch balance (status code: {response.status_code})"
    except Exception as e:
        return f"An error occurred: {str(e)}"


def get_total_earnings(wallet_address):
    try:
        response = requests.post('https://nimble-api.urlrevealer.com/get_total_earnings',
                                 json={'address': wallet_address})
        if response.status_code == 200:
            earnings_data = response.json()
            total_earnings = earnings_data.get('total_earnings', None)
            if total_earnings is not None and isinstance(total_earnings, (int, float)):
                return str(total_earnings)
            else:
                return "Error: Total earnings data is not a number"
        else:
            return "Error: Unable to fetch total earnings"
    except Exception as e:
        return f"An error occurred: {str(e)}"


def send_server_stats_to_channel():
    uptime = time.time() - start_time
    num_users = len(user_data)
    num_wallets = sum(len(wallets) for wallets in user_data.values())
    message = (f"Server Stats:\n"
               f"Uptime: {uptime // 3600:.0f} hours {uptime % 3600 // 60:.0f} minutes\n"
               f"Number of Users: {num_users}\n"
               f"Number of Wallet Addresses: {num_wallets}")
    bot.send_message(channel_id, message)


def update_balances():
    while True:
        for chat_id, data_list in user_data.items():
            for data in data_list:
                if time.time() - data['last_update'] >= 3600:  # 1 hour
                    balance = get_balance(data['address'])
                    bot.send_message(chat_id, balance)
                    data['last_update'] = time.time()
        time.sleep(60)


update_thread = threading.Thread(target=update_balances)
update_thread.start()


def send_periodic_stats():
    while True:
        send_server_stats_to_channel()
        time.sleep(86400)  # 24 hours


stats_thread = threading.Thread(target=send_periodic_stats)
stats_thread.start()


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    submit_wallet_button = telebot.types.InlineKeyboardButton("Submit Wallet", callback_data='submit_wallet')
    donation_button = telebot.types.InlineKeyboardButton("Donate", url='https://www.buymeacoffee.com/airdroplk')
    markup.add(submit_wallet_button, donation_button)

    welcome_message = (
        "Welcome to Nimble Balance Checker Bot! Just click 'Submit Wallet', enter your Master address, "
        "and a button appears in your feed for easy Nimble point checks. Join @airdrop_LK for more updates. "
        "Support me with donations. Thank you!"
    )
    bot.send_message(message.chat.id, welcome_message, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'submit_wallet')
def submit_wallet(call):
    bot.send_message(call.message.chat.id, "Please send me your Nimble wallet address.")


@bot.message_handler(func=lambda message: True)
def handle_wallet_address(message):
    if message.text.strip().startswith('nimble'):
        save_nimble_address(message)
    else:
        bot.send_message(message.chat.id, "Invalid Nimble wallet address. Please enter a valid Nimble wallet address.")


def save_nimble_address(message):
    if message.chat.id not in user_data:
        user_data[message.chat.id] = []

    user_data[message.chat.id].append({'address': message.text.lower(), 'last_update': time.time()})
    send_loading_animation(message.chat.id)  # Display the loading animation
    balance = get_balance(message.text.lower())
    create_inline_button(message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
def callback_remove_wallet(call):
    data = call.data.split('_')
    user_id = int(data[1])
    nimble_address = data[2]

    if user_id in user_data:
        user_data[user_id] = [wallet_data for wallet_data in user_data[user_id] if
                              wallet_data['address'] != nimble_address]
        if not user_data[user_id]:  # If no wallets left, remove the user_id entry
            del user_data[user_id]
        bot.answer_callback_query(call.id, "Wallet address removed.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        create_inline_button(call.message)
    else:
        bot.answer_callback_query(call.id, "Wallet address not found.")


def create_inline_button(message, wallet_removed=False):
    nimble_buttons = []
    for wallet_data in user_data.get(message.chat.id, []):
        nimble_address = wallet_data['address']
        balance = get_balance(nimble_address)
        earning_button = telebot.types.InlineKeyboardButton(f"{balance}",
                                                            callback_data=f'earning_{message.chat.id}_{nimble_address}')
        nimble_button = telebot.types.InlineKeyboardButton(f"{nimble_address}",
                                                           callback_data=f'nimble_{message.chat.id}_{nimble_address}')
        remove_button = telebot.types.InlineKeyboardButton("❌",
                                                           callback_data=f'remove_{message.chat.id}_{nimble_address}')
        check_h_button = telebot.types.InlineKeyboardButton("Check (H)",
                                                            callback_data=f'check_h_{message.chat.id}_{nimble_address}')
        check_d_button = telebot.types.InlineKeyboardButton("Check (D)",
                                                            callback_data=f'check_d_{message.chat.id}_{nimble_address}')
        check_w_button = telebot.types.InlineKeyboardButton("Check (W)",
                                                            callback_data=f'check_w_{message.chat.id}_{nimble_address}')

        nimble_buttons.append([earning_button, nimble_button, remove_button])
        nimble_buttons.append([check_h_button, check_d_button, check_w_button])

    markup = telebot.types.InlineKeyboardMarkup()

    if nimble_buttons:
        for buttons in nimble_buttons:
            markup.row(*buttons)
        update_button = telebot.types.InlineKeyboardButton("Update Balance", callback_data='update_balance')
        markup.row(update_button)
    else:
        submit_wallet_button = telebot.types.InlineKeyboardButton("Submit Wallet", callback_data='submit_wallet')
        markup.add(submit_wallet_button)

    donation_button = telebot.types.InlineKeyboardButton("Donate", url='https://www.buymeacoffee.com/airdroplk')
    markup.add(donation_button)

    if wallet_removed:
        message_text = "Your wallet address has been successfully deleted. However, you can click 'Submit Wallet' to submit your wallet anytime."
    else:
        message_text = "Your address is now successfully saved. You can simply tap on your address and instantly check your total rewards."\
                       "You can remove your current wallet address by clicking on ❌"\
                       "If you want to add more address send Wallet address directly to the Bot"

    bot.send_message(message.chat.id, message_text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'update_balance')
def callback_update_balance(call):
    create_inline_button(call.message)
    bot.answer_callback_query(call.id, "Balance updated.")


def generate_earnings_table(earnings_data, time_unit):
    table = "+------------+----------------+--------+\n"
    table += "|    Date    |     Time       | Amount |\n"
    table += "+------------+----------------+--------+\n"

    total_earnings = 0
    for entry in earnings_data:
        date = entry['date']
        time = entry['time'] if time_unit == 'hourly' else ""
        amount = entry['amount']
        total_earnings += amount
        table += f"| {date} | {time:>14} | {amount:>6} |\n"
        table += "+------------+----------------+--------+\n"

    table += f"|   Total    |                | {total_earnings:>6} |\n"
    table += "+------------+----------------+--------+"

    return table

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_h_'))
def callback_check_h(call):
    data = call.data.split('_')
    nimble_address = data[3]
    earnings_last_24_hours = get_hourly_earnings(nimble_address)
    table = generate_earnings_table(earnings_last_24_hours, 'hourly')
    bot.send_message(call.message.chat.id, f"Hourly Earnings for {nimble_address}:\n```\n{table}\n```", parse_mode='Markdown')

def get_hourly_earnings(nimble_address):
    # Replace this mock function with actual API call logic
    return [
        {'date': '2024-05-16', 'time': '00:00:00', 'amount': 5},
        {'date': '2024-05-16', 'time': '01:00:00', 'amount': 10},
        {'date': '2024-05-16', 'time': '02:00:00', 'amount': 15},
        # More hourly data
    ]

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_d_'))
def callback_check_d(call):
    data = call.data.split('_')
    nimble_address = data[3]
    earnings_last_7_days = get_daily_earnings(nimble_address)
    table = generate_earnings_table(earnings_last_7_days, 'daily')
    bot.send_message(call.message.chat.id, f"Daily Earnings for {nimble_address}:\n```\n{table}\n```", parse_mode='Markdown')

def get_daily_earnings(nimble_address):
    # Replace this mock function with actual API call logic
    return [
        {'date': '2024-05-10', 'time': '', 'amount': 100},
        {'date': '2024-05-11', 'time': '', 'amount': 150},
        {'date': '2024-05-12', 'time': '', 'amount': 200},
        {'date': '2024-05-13', 'time': '', 'amount': 250},
        {'date': '2024-05-14', 'time': '', 'amount': 300},
        {'date': '2024-05-15', 'time': '', 'amount': 350},
        {'date': '2024-05-16', 'time': '', 'amount': 400},
    ]


@bot.callback_query_handler(func=lambda call: call.data.startswith('check_w_'))
def callback_check_w(call):
    data = call.data.split('_')
    nimble_address = data[3]
    earnings_last_weeks = get_weekly_earnings(nimble_address)
    table = generate_earnings_table(earnings_last_weeks, 'weekly')
    bot.send_message(call.message.chat.id, f"Weekly Earnings for {nimble_address}:\n```\n{table}\n```", parse_mode='Markdown')

def get_weekly_earnings(nimble_address):
    # Replace this mock function with actual API call logic
    return [
        {'date': '2024-05-01', 'time': '', 'amount': 500},
        {'date': '2024-05-08', 'time': '', 'amount': 600},
        {'date': '2024-05-15', 'time': '', 'amount': 700},
        # More weekly data
    ]


bot.polling()