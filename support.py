import os
import telebot
from telebot import types
from translate import Translator
from groq import Groq
from datetime import datetime, timedelta
import threading
import time

API_KEY = 'token'
bot = telebot.TeleBot(API_KEY)

os.environ["GROQ_API_KEY"] = "token"

client = Groq()
translator_to_en = Translator(provider='mymemory', to_lang='en')
translator_to_uk = Translator(provider='mymemory', to_lang='uk')

user_language = {}
user_history = {}
banned_users = {}

can_use_groq = False
e_message = False

group_chat_id = -1002240331774

def save_message_user(message, chat_id):
    file_name = f'chat_{chat_id}.txt'
    with open(file_name, 'a', encoding='utf-8') as file:
        file.write(f"User: {message}\n")

def save_message_bot(message, chat_id):
    file_name = f'chat_{chat_id}.txt'
    with open(file_name, 'a', encoding='utf-8') as file:
        file.write(f"Bot: {message}\n")

def create_language_keyboard(language):
    keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    if language == '🇺🇦 Українська':
        keyboard.row('🇺🇦 Українська')
        keyboard.row('🇬🇧 English')
    else:
        keyboard.row('🇬🇧 English')
        keyboard.row('🇺🇦 Українська')
    return keyboard

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_message = message.text
    save_message_user(user_message, chat_id)
    user_language[message.chat.id] = '🇬🇧 English'  
    bot.send_message(
        message.chat.id,
        "Please select your language / Будь ласка, оберіть свою мову:",
        reply_markup=create_language_keyboard('🇺🇦 Українська')
    )

@bot.message_handler(func=lambda message: message.text in ['🇺🇦 Українська', '🇬🇧 English'])
def handle_language_selection(message):
    global can_use_groq
    chat_id = message.chat.id
    user_message = message.text
    save_message_user(user_message, chat_id)
    user_language[message.chat.id] = message.text

    if message.text == '🇺🇦 Українська':
        bot.send_message(message.chat.id, "Ви обрали українську мову. Я штучний інтелект підтримки. Я спробую вам допомогти. Якщо буде якийсь глюк, баг і т.д. у боті, напишіть /start . Якщо я не зможу допомогти, я зроблю запрос до команди допомоги. Як я можу допомогти? 😊")
    elif message.text == '🇬🇧 English':
        bot.send_message(message.chat.id, "You have chosen the 🇬🇧 English language. I am an artificial intelligence support. I will try to help you. If there is any glitch, bug, etc. in the bot, write /start . If I can't help you, I'll make a request to the support team. How can I help 😊?")
    else:
        bot.send_message(message.chat.id, "Please select a valid language.")
        return

    can_use_groq = True
    user_history[message.chat.id] = []

def unban_user(chat_id):
    banned_users.pop(chat_id, None)
    bot.send_message(chat_id, "Ви знову можете спілкуватися.")

@bot.message_handler(commands=['ban'])
def handle_ban_command(message):
    if message.chat.id != group_chat_id:
        bot.send_message(message.chat.id, "Цю команду можуть використовувати тільки адміністратори! ❌")
        return

    try:
        command_parts = message.text.split(maxsplit=3)
        if len(command_parts) < 3:
            raise ValueError("Invalid command format")

        chat_id = int(command_parts[1])
        ban_time = int(command_parts[2])
        reason = command_parts[3] if len(command_parts) > 3 else "No reason provided."

        banned_users[chat_id] = datetime.now() + timedelta(seconds=ban_time)
        bot.send_message(chat_id, f"Ви були заблоковані на {ban_time} секунд. Причина: {reason}")

        threading.Timer(ban_time, unban_user, args=[chat_id]).start()
        bot.send_message(message.chat.id, f"Користувач {chat_id} був успішно заблокований на {ban_time} секунд. ✅")

    except ValueError:
        bot.send_message(message.chat.id, "Неправильний формат команди. Використовуйте /ban {chat-id} {time} {reason}")

@bot.message_handler(commands=['unban'])
def handle_unban_command(message):
    if message.chat.id != group_chat_id:
        bot.send_message(message.chat.id, "Цю команду можуть використовувати тільки адміністратори! ❌")
        return

    try:
        command_parts = message.text.split(maxsplit=2)
        if len(command_parts) < 2:
            raise ValueError("Invalid command format")

        chat_id = int(command_parts[1])
        if chat_id in banned_users:
            banned_users.pop(chat_id)
            bot.send_message(chat_id, "Ви були розблоковані достроково. Можете спілкуватися.")
            bot.send_message(message.chat.id, f"Користувач {chat_id} був успішно розблокований. ✅")
        else:
            bot.send_message(message.chat.id, f"Користувач {chat_id} не знайдений у списку заблокованих. ❌")

    except ValueError:
        bot.send_message(message.chat.id, "Неправильний формат команди. Використовуйте /unban {chat-id}")

@bot.message_handler(func=lambda message: message.chat.type == 'private')
def handle_all_messages(message):
    global can_use_groq, e_message

    if message.chat.id in banned_users:
        remaining_time = (banned_users[message.chat.id] - datetime.now()).total_seconds()
        if remaining_time > 0:
            bot.send_message(message.chat.id, f"Ви заблоковані ще на {int(remaining_time)} секунд.")
            return
        else:
            banned_users.pop(message.chat.id, None)
            bot.send_message(message.chat.id, "Ваша блокування закінчилася. Ви знову можете спілкуватися.")
    
    chat_id = message.chat.id
    user_message = message.text
    save_message_user(user_message, chat_id)
    language = user_language.get(chat_id, '🇬🇧 English')

    if e_message:
        file_name = f'chat_{chat_id}.txt'
        with open(file_name, 'rb') as file:
            bot.send_document(group_chat_id, file)
        bot.send_message(group_chat_id, f'Last message: {message.text}\nChat ID: {chat_id}')
        user_history[chat_id] = []  # Clear user history
        e_message = False  # Reset e_message flag
    else:
        if can_use_groq:
            translated_message = translator_to_en.translate(user_message)
            print(translated_message)
            if chat_id not in user_history:
                user_history[chat_id] = []
            user_history[chat_id].append({"role": "user", "content": translated_message})

            messages = user_history[chat_id].copy()
            messages.insert(0, {
                "role": "system",
                "content": "Hi! You are now a support bot for the game ‘He is real’. Do not answer questions that do not relate to the game. If you don't know the answer to a question write ‘{support}’. This will send the request to the administrator.\nProblems and answers:\nIdea of a game: you have a dog, you have to look after it, walk it, play with it, etc.\nInterface problem: Game supports only 2340x1080 resolution\n\nIn game there is only 2 dogs - Black Scottish Terrier and White Scottish Terrier.\n\nThere are only 2 mini-games: agility and frisbee.\n\nGive answers only on 🇬🇧 English. Give short response."
            })

            completion = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                temperature=1,
                max_tokens=500,
                top_p=1,
                stream=False,
                stop=None
            )

            groq_response = completion.choices[0].message.content
            user_history[chat_id].append({"role": "assistant", "content": groq_response})
            print(groq_response)

            if "{support}" in groq_response:
                groq_response = groq_response.replace("{support}", "**запрос до підтримки надіслано**")
                e_message = True
                if language == '🇺🇦 Українська':
                    response_message = translator_to_uk.translate(groq_response)
                else:
                    response_message = groq_response

                bot.send_message(chat_id, response_message)
                save_message_bot(response_message, chat_id)
                
                file_name = f'chat_{chat_id}.txt'
                with open(file_name, 'rb') as file:
                    bot.send_document(group_chat_id, file)
                bot.send_message(group_chat_id, f'Chat ID: {chat_id}')
                time.sleep(2)
                bot.send_message(chat_id, "**Підтримка приєдналась до чату**")
            else:
                if language == '🇺🇦 Українська':
                    response_message = translator_to_uk.translate(groq_response)
                else:
                    response_message = groq_response

                save_message_bot(response_message, chat_id)
                bot.send_message(chat_id, response_message)

@bot.message_handler(commands=['reply'])
def handle_reply_command(message):
    chat_id = message.chat.id
    user_message = message.text
    save_message_user(user_message, chat_id)
    if message.chat.id != group_chat_id:
        bot.send_message(message.chat.id, "Цю команду можуть використовувати тільки адміністратори! ❌")
        return

    try:
        command_parts = message.text.split(maxsplit=2)
        if len(command_parts) < 3:
            raise ValueError("Invalid command format")

        chat_id = int(command_parts[1])
        reply_message = command_parts[2]

        bot.send_message(chat_id, reply_message)
        save_message_bot(reply_message, chat_id)

        bot.send_message(message.chat.id, "Повідомлення успішно відправлено. ✅")

    except ValueError:
        bot.send_message(message.chat.id, "Неправильний формат команди. Використовуйте /reply {chat-id} {message}")

@bot.message_handler(commands=['un_e'])
def handle_un_e_command(message):
    global e_message
    if message.chat.id != group_chat_id:
        bot.send_message(message.chat.id, "Цю команду можуть використовувати тільки адміністратори! ❌")
        return

    try:
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) < 2:
            raise ValueError("Invalid command format")

        chat_id = int(command_parts[1])
        e_message = False
        bot.send_message(chat_id, "Підтримка відключена. Ви можете продовжувати спілкування з ботом.")

        bot.send_message(message.chat.id, f"Підтримка для користувача {chat_id} була успішно відключена. ✅")

    except ValueError:
        bot.send_message(message.chat.id, "Неправильний формат команди. Використовуйте /un_e {chat-id}")

bot.polling()
