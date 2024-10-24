import aiohttp
import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import TOKEN, OAUTH_TOKEN, FOLDER_ID, API_URL

ALLOWED_UPDATES = ['message']

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

DATA_FILE = 'user_dictionaries.json'
# в этом файле содержаться личные словари всех пользователей в виде словаря {<user_id>: {<слово>: [<варианты перевода>]}


class LearningWord(StatesGroup):  # LearningWord представляет группу состояний для процесса изучения слов.
    word = State()


def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)


# запись обновлений словарей пользователя в файл JSON
def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


# загрузка словарей пользователей, чтобы они не очищались при перезапуске бота
user_dictionaries = load_data()


# Получает IAM токен для доступа к API Яндекс.Облака
async def get_iam_token():
    async with aiohttp.ClientSession() as session:
        async with session.post('https://iam.api.cloud.yandex.net/iam/v1/tokens', json={'yandexPassportOauthToken':
                                                                                        OAUTH_TOKEN}) as response:
            response.raise_for_status()
            data = await response.json()
            return data['iamToken']


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(f"Hello, {message.from_user.first_name}! Please type /help to get more information about me.")


@dp.message(Command('help'))
async def help_to_user(message: types.Message):
    await message.answer("You can ask the bot any question related to language learning, theory and grammar. In "
                         "addition, it is your smart dictionary, in which you can write down words and their "
                         "translation, as well as memorize them thanks to the interval repetition system.")
    await message.answer("To add a word to the dictionary, write to the bot /add_word, and then, in the same message, "
                         "separated by a space, the word itself and its translation.")
    await message.answer("To delete a word from the dictionary, write to the bot /delete_word, and then, in the same "
                         "message, the word itself.")
    await message.answer("To delete only one of the meanings of a word from the dictionary, write to the bot "
                         "/delete_meaning, and then, in the same message, separated by a space, the word itself and "
                         "its meaning that you want to delete.")
    await message.answer("To view your dictionary in alphabetical order, write to the bot /my_dict.")
    await message.answer("To start learning a word from the dictionary, write to the bot /learn. In the next message, "
                         "write the word you would like to learn. The bot will ask you to translate the word using "
                         "the interval repetition technique for better memorization: after a minute, after 2 minutes, "
                         "after an hour, after a day, after 3 days, after 1 week and after 2 weeks.\nUnfortunately, "
                         "at this stage of development, the bot can only teach you one word at a time.")


# добавляет слово в словарь пользователя, обрабатывая сообщение вида "/add_word <слово> <перевод>"
@dp.message(Command('add_word'))
async def add(message: types.Message):
    user_id = str(message.from_user.id)

    if user_id not in user_dictionaries:
        user_dictionaries[user_id] = {}

    # проверка корректности ввода
    data = message.text.split()
    if len(data) != 3:
        await message.answer("Please write a word and its meaning in the format: /add_word <word> <meaning>")
        return

    word, meaning = data[1], data[2]

    if word not in user_dictionaries[user_id]:
        user_dictionaries[user_id][word] = []

    if meaning in user_dictionaries[user_id][word]:
        await message.answer("This word already has this meaning in the dictionary.")
    else:
        user_dictionaries[user_id][word].append(meaning)
        save_data(user_dictionaries)
        await message.answer("The new word has been successfully added!")


# удаляет слово из словаря пользователя, обрабатывая сообщение вида "/delete_word <слово>"
@dp.message(Command('delete_word'))
async def delete_word(message: types.Message):
    user_id = str(message.from_user.id)

    if user_id not in user_dictionaries:
        await message.answer("Your dictionary is empty. Please add words first.")
        return

    data = message.text.split()

    # проверка корректности ввода
    if len(data) != 2:
        await message.answer("Please specify the word you want to delete.")
        return

    word = data[1]

    if word in user_dictionaries[user_id]:
        del user_dictionaries[user_id][word]
        save_data(user_dictionaries)
        await message.answer("The word has been successfully deleted.")
    else:
        await message.answer(
            "There is no such word in the dictionary. Please check the spelling. You can view your "
            "dictionary using the /my_dict command.")


# удаляет значение слова из словаря пользователя, обрабатывая сообщение вида "/delete_word <слово> <значение>"
@dp.message(Command('delete_meaning'))
async def delete_meaning(message: types.Message):
    user_id = str(message.from_user.id)

    if user_id not in user_dictionaries:
        await message.answer("Your dictionary is empty. Please add words first.")
        return

    data = message.text.split()

    # проверка корректности ввода
    if len(data) != 3:
        await message.answer("Please write the word and its meaning that you want to delete.")
        return

    word, meaning = data[1], data[2]

    if word in user_dictionaries[user_id]:
        if meaning in user_dictionaries[user_id][word]:
            user_dictionaries[user_id][word].remove(meaning)
            save_data(user_dictionaries)
            await message.answer("The meaning has been successfully deleted.")
            # если после удаления значения у слова нет ни одного перевода в словаре, то оно удаляется из словаря
            if len(user_dictionaries[user_id][word]) == 0:
                del user_dictionaries[user_id][word]
                save_data(user_dictionaries)
        else:
            await message.answer("This meaning is not in the dictionary. Please check the spelling. You can view your "
                                 "dictionary using the /my_dict command.")
    else:
        await message.answer("This word does not exist in your dictionary.")


# выводит отсортированный словарь пользователя, обрабатывая сообщение вида "/my_dict"
@dp.message(Command('my_dict'))
async def view_dict(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in user_dictionaries or not user_dictionaries[user_id]:
        await message.answer("Your dictionary is empty.")
    else:
        dict_items = '\n'.join([f"{key}\t—\t{', '.join(value)}" for key, value in
                                sorted(user_dictionaries[user_id].items())])
        await message.answer(f"Your dictionary:\n{dict_items}")


# обрабатывает команду "/learn" и запрашивает у пользователя слово для изучения, устанавливая состояние машины
# состояний для ожидания ввода слова
@dp.message(Command('learn'))
async def send_delayed_messages(message: types.Message, state: FSMContext):
    await state.set_state(LearningWord.word)
    await message.answer("Enter the word you want to learn.")


# обрабатывает ввод слова, сохраняя его в состоянии, и проверяет, есть ли это слово в словаре пользователя. Если слово
# найдено, запускается процесс интервального повторения с заданными задержками.
@dp.message(LearningWord.word)
async def get_word(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    await state.update_data(word=message.text)
    await state.clear()

    global user_word

    user_word = message.text

    if message.text not in user_dictionaries[user_id]:
        await message.answer("The word is not found in your dictionary.")
        return

    await message.answer("The word has been successfully added to the study!")

    asyncio.create_task(repeat(user_id, message.text))


# отправляет сообщения для интервального повторения слова
async def repeat(user_id, word):
    for delay in [60, 120, 3600, 86400, 259200, 604800, 1209600]:
        # 1 минута, 2 минуты 1 час, 1 день, 3 дня, 1 неделя, 2 недели
        await asyncio.sleep(delay)
        await bot.send_message(user_id, f'Let\'s repeat the vocabulary! How to translate "{word}"? Enter your answer '
                                        f'using the command /check.')


# проверяет ответ пользователя и сообщает правильные варианты перевода, если ответ не верен
# если слово было удалено из словаря пользователя, функция уведомляет об этом
@dp.message(Command('check'))
async def check_answer(message: types.Message, state=FSMContext):
    user_id = str(message.from_user.id)

    data = message.text.split()
    user_ans = data[-1]

    if not user_word or user_word not in user_dictionaries[user_id]:
        await message.answer("The word has been removed from the dictionary.")
        await state.clear()
        return

    correct_answer = user_dictionaries[user_id][user_word]

    if user_ans.lower() in [elem.lower() for elem in correct_answer]:
        await message.answer("Well done! This is the correct answer.")
    else:
        await message.answer(f"You almost guessed it! Correct answers: {', '.join(correct_answer)}.")


# извлекает текст сообщения, получает IAM токен, формирует запрос к Yandex GPT и отправляет его. Затем она
# обрабатывает ответ и отправляет его обратно пользователю.
@dp.message()
async def process_message(message: types.Message):
    user_text = message.text

    # получение IAM токен
    iam_token = await get_iam_token()

    # отправка запроса к Yandex GPT
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt",
        "completionOptions": {"temperature": 0.3, "maxTokens": 1000},
        "messages": [
            {"role": "system", "text": "I am learning foreign languages and I want you to explain the theory to me "
                                       "and answer all my questions. Answer in English."},
            {"role": "user", "text": user_text}
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, json=data, headers={"Authorization": f"Bearer {iam_token}"}) as response:
            response.raise_for_status()
            result = await response.json()
            answer = result.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text',
                                                                                                  'Error receiving '
                                                                                                  'the response')
    await message.reply(answer)


# инициализации бота и запуска процесса опроса
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)


if __name__ == "__main__":
    asyncio.run(main())
