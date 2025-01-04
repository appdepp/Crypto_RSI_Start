import os
import logging
from dotenv import load_dotenv
from binance.client import Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем API ключи из переменных окружения
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем клиента для Binance
binance_client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

# Топ-10 криптовалютных пар
TOP_CRYPTO_PAIRS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT',
    'XRPUSDT', 'DOGEUSDT', 'LUNAUSDT', 'MATICUSDT', 'DOTUSDT'
]

# Периоды для анализа (обновленные)
PERIODS = ['1m', '5m', '15m', '30m', '1h', '6h', '12h', '1d', '3d', '1M']
# Словарь для хранения выбранных значений
user_data = {}

# Пара по умолчанию для анализа
DEFAULT_PAIR = 'BTCUSDT'


# Команда старта
async def start(update: Update, context: CallbackContext) -> None:
    # Отправляем приветственное сообщение при запуске бота
    await update.message.reply_text(
        "Привет! Я бот для анализа криптовалют.\n"
        "Вы можете выбрать криптовалютную пару и период для анализа, а также получить информацию о RSI.\n"
        "Для начала выберите одну из команд ниже:",
        reply_markup=InlineKeyboardMarkup(keyboard)  # Тут можно указать клавиатуру с кнопками
    )


# Команда помощи
async def help_command(update: Update, context: CallbackContext) -> None:
    if update.callback_query:
        # Проверка если это callback для "Помощи"
        if update.callback_query.data == "help":
            await update.callback_query.message.reply_text(
                "📌 *Как пользоваться ботом:*\n"
                "1️⃣ Нажмите кнопку \"Топ-10 криптовалют\", чтобы выбрать криптовалюту для анализа.\n"
                "2️⃣ Затем выберите период анализа (например, 5m, 1h, 3d и т.д.).\n"
                "3️⃣ Бот покажет:\n"
                "   - Текущую цену криптовалюты\n"
                "   - 24-часовой объем торгов\n"
                "   - Процентное изменение за последние 24 часа\n"
                "   - Индикатор RSI (Relative Strength Index) и торговый сигнал\n\n"
                "📊 *Пример использования:*\n"
                "Вы выбрали пару BTCUSDT и период 1h. Бот покажет анализ цены биткоина за последний час.\n\n"
                "💡 *Полезные советы:*\n"
                "- RSI ниже 30 = сигнал на покупку.\n"
                "- RSI выше 70 = сигнал на продажу.\n"
                "- RSI между 30 и 70 = нейтральная зона.\n\n"
                "Если что-то не работает, попробуйте команду /start для перезапуска.",
                parse_mode="Markdown"
            )
            # Закрепляем сообщение
            await update.callback_query.message.pin()

# Инициализация кнопки помощи
keyboard = [
    [InlineKeyboardButton("📊 Топ-10 криптовалют", callback_data="top_pairs")],
    [InlineKeyboardButton("💬 Помощь", callback_data="help")]
]


# Обработчик команды /top_pairs
async def top_pairs(update: Update, context: CallbackContext) -> None:
    keyboard = []

    # Добавляем кнопки для криптовалютных пар
    for pair in TOP_CRYPTO_PAIRS:
        keyboard.append([InlineKeyboardButton(pair, callback_data=f"pair_{pair}")])

    # Добавляем кнопки для периодов, теперь они в одну строку
    period_buttons = [InlineKeyboardButton(period, callback_data=f"period_{period}") for period in PERIODS]

    # Мы делим список периодов на несколько строк, если кнопок слишком много
    keyboard.append(period_buttons[:5])  # Первая линия с периодами
    keyboard.append(period_buttons[5:])  # Вторая линия с периодами

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(
        "Выберите криптовалютную пару и период анализа:",
        reply_markup=reply_markup
    )


async def handle_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user = query.from_user.id

    # Обработка выбора пары
    if query.data.startswith("pair_"):
        pair = query.data.replace("pair_", "")
        user_data[user] = user_data.get(user, {})
        user_data[user]['pair'] = pair
        await query.answer(f"Вы выбрали пару: {pair} 🌟")

    # Обработка выбора периода
    elif query.data.startswith("period_"):
        period = query.data.replace("period_", "")
        user_data[user] = user_data.get(user, {})
        user_data[user]['period'] = period
        await query.answer(f"Вы выбрали период: {period} ⏳")

    # Если оба параметра выбраны, отображаем информацию
    if 'pair' in user_data[user] and 'period' in user_data[user]:
        pair = user_data[user]['pair']
        period = user_data[user]['period']

        try:
            # Получение данных Binance
            klines = binance_client.get_klines(symbol=pair, interval=period, limit=100)
            ticker = binance_client.get_ticker(symbol=pair)

            close_prices = [float(kline[4]) for kline in klines]
            rsi = calculate_rsi(close_prices, 14)

            # Формирование сообщения с информацией
            info_message = (
                f"ℹ️ *Информация о криптовалюте {pair}:*\n"
                f"🔹 Текущая цена: {ticker['lastPrice']} USD\n"
                f"📊 24h объем торгов: {ticker['quoteVolume']} USD\n"
                f"📈 24h изменение: {ticker['priceChangePercent']}%\n\n"
                f"📉 *RSI ({period}):* {rsi:.2f}\n"
            )

            if rsi < 30:
                info_message += "✅ *Сигнал на покупку!*"
            elif rsi > 70:
                info_message += "❌ *Сигнал на продажу!*"
            else:
                info_message += "⚖️ *RSI в нейтральной зоне.*"

            await query.message.reply_text(info_message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Ошибка при обработке данных: {e}")
            await query.message.reply_text(f"❌ Ошибка при получении данных с Binance: {e}")

        # Очищаем данные пользователя
        del user_data[user]

    await query.answer()


def calculate_rsi(prices, period):
    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            losses.append(abs(change))
            gains.append(0)

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def main():
    # Инициализация бота и обработчиков команд
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()


    # Обработчики команд
    application.add_handler(CommandHandler("start", start))  # Команда /start
    application.add_handler(CommandHandler("help", help_command))  # Команда /help
    application.add_handler(CallbackQueryHandler(top_pairs, pattern="^top_pairs$"))
    application.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    application.add_handler(CallbackQueryHandler(handle_selection, pattern="^pair_|^period_"))

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()
