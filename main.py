import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile

from db import db
from admin import setup_admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = '7243978024:AAG41V9EMPrJ4HZntWQfTVGskLjOEDo5BZM'

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)
user_router = Router()


# Состояние для ожидания чека
class PaymentStates(StatesGroup):
    WAITING_RECEIPT = State()


setup_admin_router(dp)
dp.include_router(user_router)


def create_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📦 Наличие товаров", "about_shop"),
        ("💳 Покупка через СБП", "sbp_categories"),
        ("📦 Покупка через оператора", "operator_categories"),
        ("🎁 Акции и скидки", "promotions"),
        ("🛟 Поддержка", "support")
    ]
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    builder.adjust(1)  # Изменено на 1 кнопку в строке
    return builder.as_markup()


def create_back_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    return builder.as_markup()


def create_back_to_products_button(category_id, section_type):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к товарам", callback_data=f"{section_type}_category_{category_id}")
    return builder.as_markup()


def create_sbp_payment_keyboard(product_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Отправить фото чека", callback_data=f"send_receipt_{product_id}")
    builder.button(text="⬅️ Назад к товарам", callback_data="sbp_category_back")
    builder.adjust(1)
    return builder.as_markup()


def create_close_request_keyboard(order_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Закрыть заявку", callback_data=f"close_request_{order_id}")
    return builder.as_markup()


@user_router.message(Command('start'))
async def send_welcome(message: types.Message):
    user_name = message.from_user.first_name
    reply_markup = create_main_menu_keyboard()
    welcome_text = f"""
✨ <b>Добро пожаловать, {user_name}!</b> ✨
🏪 <i>Добро пожаловать в наш магазин — место, где вы найдете всё, что нужно!</i>
👇 <b>Выберите нужный раздел:</b>
    """
    if db.is_admin(message.from_user.id):
        welcome_text += "\n\n👑 <i>Вы также можете использовать /admin для доступа к панели управления</i>"
    await message.answer(welcome_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


@user_router.callback_query()
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    callback_data = callback_query.data
    if callback_data.startswith('admin_'):
        logger.info(f"Admin callback received, skipping user handler: {callback_data}")
        return
    if callback_data == 'sbp_category_back':
        await show_categories(callback_query, 'sbp')
        return
    if callback_data == 'operator_categories':
        await show_categories(callback_query, 'operator')
        return
    if callback_data == 'sbp_categories':
        await show_categories(callback_query, 'sbp')
        return
    if callback_data.startswith('send_receipt_'):
        product_id = int(callback_data.split('_')[2])
        await process_receipt_request(callback_query, product_id, state)
        return
    if callback_data.startswith('operator_category_'):
        category_id = int(callback_data.split('_')[2])
        await show_products(callback_query, category_id, 'operator')
        return
    if callback_data.startswith('sbp_category_'):
        category_id = int(callback_data.split('_')[2])
        await show_products(callback_query, category_id, 'sbp')
        return
    if callback_data.startswith('operator_product_'):
        product_id = int(callback_data.split('_')[2])
        await show_product_details(callback_query, product_id, 'operator')
        return
    if callback_data.startswith('sbp_product_'):
        product_id = int(callback_data.split('_')[2])
        await show_product_details(callback_query, product_id, 'sbp')
        return
    if callback_data in ['about_shop', 'promotions']:
        content = db.get_section_content(callback_data)
        photo_path = db.get_section_photo(callback_data)
        if content:
            if photo_path:
                try:
                    await callback_query.message.answer_photo(
                        FSInputFile(photo_path),
                        caption=content,
                        parse_mode=ParseMode.HTML,
                        reply_markup=create_back_button()
                    )
                    await callback_query.message.delete()
                except Exception as e:
                    logger.error(f"Ошибка при отправке фото: {e}")
                    await callback_query.message.answer(
                        content,
                        parse_mode=ParseMode.HTML,
                        reply_markup=create_back_button()
                    )
            else:
                await callback_query.message.answer(
                    content,
                    parse_mode=ParseMode.HTML,
                    reply_markup=create_back_button()
                )
            await callback_query.answer()
            return
    if callback_data == 'support':
        text = """
🛟 <b>Поддержка</b>
По всем вопросам обращайтесь @sssofbot13
        """
        reply_markup = create_back_button()
    elif callback_data == 'back_to_main':
        text = "👇 <b>Выберите нужный раздел:</b>"
        reply_markup = create_main_menu_keyboard()
        try:
            await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except:
            await callback_query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        await callback_query.answer()
        return
    elif callback_data.startswith('close_request_'):
        await close_request_handler(callback_query)
        return
    else:
        text = "Неизвестная команда"
        reply_markup = create_back_button()

    try:
        await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except:
        try:
            await callback_query.message.delete()
        except:
            pass
        await callback_query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    await callback_query.answer()


async def show_categories(callback_query: types.CallbackQuery, section_type: str):
    categories = db.get_categories_by_section(section_type)
    section_name = "Покупка через оператора" if section_type == 'operator' else "Покупка через СБП"
    if not categories:
        text = f"📦 <b>{section_name}</b>\n\nПока нет добавленных категорий."
        reply_markup = create_back_button()
        try:
            await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except:
            await callback_query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        text = f"📦 <b>{section_name}</b>\n\nВыберите категорию:"
        keyboard = InlineKeyboardBuilder()
        for category in categories:
            products_count = len(db.get_products_by_category_and_section(category['id'], section_type))
            keyboard.button(text=f"{category['name']} ({products_count} товаров)",
                            callback_data=f"{section_type}_category_{category['id']}")
        keyboard.button(text="⬅️ Назад", callback_data="back_to_main")
        keyboard.adjust(1)
        try:
            await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard.as_markup())
        except:
            await callback_query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard.as_markup())
    await callback_query.answer()


async def show_products(callback_query: types.CallbackQuery, category_id: int, section_type: str):
    category = db.get_category_by_id(category_id)
    section_name = "Покупка через оператора" if section_type == 'operator' else "Покупка через СБП"
    if category:
        products = db.get_products_by_category_and_section(category_id, section_type)
        if not products:
            text = f"📦 <b>{category['name']}</b>\n\nПока нет товаров в этой категории."
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="⬅️ Назад к категориям", callback_data=f"{section_type}_categories")
            try:
                await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML,
                                                       reply_markup=keyboard.as_markup())
            except:
                await callback_query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard.as_markup())
        else:
            text = f"📦 <b>{category['name']}</b>\n\nВыберите товар:"
            keyboard = InlineKeyboardBuilder()
            for product in products:
                if section_type == 'operator':
                    keyboard.button(text=f"{product['name']} - {product['price']} руб.",
                                    callback_data=f"{section_type}_product_{product['id']}")
                else:
                    keyboard.button(text=f"{product['name']} - {product['stars_price']} руб.",
                                    callback_data=f"{section_type}_product_{product['id']}")
            keyboard.button(text="⬅️ Назад к категориям", callback_data=f"{section_type}_categories")
            keyboard.adjust(1)
            try:
                await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML,
                                                       reply_markup=keyboard.as_markup())
            except:
                await callback_query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard.as_markup())
    else:
        await callback_query.answer("Категория не найдена.")
    await callback_query.answer()


async def show_product_details(callback_query: types.CallbackQuery, product_id: int, section_type: str):
    product = db.get_product_by_id(product_id)
    if product:
        category = db.get_category_by_id(product['category_id'])
        if section_type == 'operator':
            text = f"🛒 <b>{product['name']}</b>\n\n{product['description']}\n\n💵 Цена: {product['price']} руб.\n📦 Категория: {category['name'] if category else 'Неизвестно'}\n\n📸 <b>Для покупки:</b>\n1. Сделайте скриншот этого сообщения\n2. Отправьте его @sssofbot13"
            reply_markup = create_back_to_products_button(product['category_id'], section_type)
        else:
            payment_details = """
💳 <b>Оплата через СБП</b>

Для оплаты переведите <b>{amount} руб.</b> на один из реквизитов:

📞 <b>+79955478027</b>
🔵 Озон Банк (Лучше сюда)  
🔵 ВТБ Банк
🟢 Сбер
🟡 Т-Банк 
🔴 Альфа 
🟣 Яндекс 
👤 <b>Софья Константиновна М.</b>

После оплаты нажмите кнопку "📸 Отправить фото чека"
""".format(amount=product['stars_price'])

            text = f"💳 <b>{product['name']}</b>\n\n{product['description']}\n\n💫 Цена: {product['stars_price']} руб.\n📦 Категория: {category['name'] if category else 'Неизвестно'}\n\n{payment_details}"
            reply_markup = create_sbp_payment_keyboard(product_id)
        try:
            await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except:
            await callback_query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await callback_query.answer("Товар не найден.")
    await callback_query.answer()


async def process_receipt_request(callback_query: types.CallbackQuery, product_id: int, state: FSMContext):
    product = db.get_product_by_id(product_id)

    if product:
        await state.set_state(PaymentStates.WAITING_RECEIPT)
        await state.update_data(product_id=product_id)
        await callback_query.message.answer("Пожалуйста, отправьте фото чека об оплате.")
    else:
        await callback_query.answer("Товар не найден.")

    await callback_query.answer()


@user_router.message(PaymentStates.WAITING_RECEIPT, F.photo)
async def handle_receipt_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    product_id = user_data.get('product_id')
    product = db.get_product_by_id(product_id)

    if product:
        # Создаем папку для чеков, если её нет
        os.makedirs("receipts", exist_ok=True)

        # Сохраняем фото чека
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path

        # Формируем путь для сохранения
        photo_filename = f"receipts/{message.from_user.id}_{message.message_id}.jpg"
        await bot.download_file(file_path, photo_filename)

        # Формируем информацию о пользователе
        username = message.from_user.username
        if username:
            user_display = f"@{username}"
        else:
            user_display = f"{message.from_user.first_name} (ID: {message.from_user.id})"

        # Создаем заказ в базе данных
        order_id = db.create_order(
            user_id=message.from_user.id,
            username=user_display,  # Используем отформатированное имя
            product_id=product_id,
            amount=product['stars_price'],
            photo_path=photo_filename,
            status='pending'
        )

        if not order_id:
            await message.answer("❌ Произошла ошибка при обработке чека. Попробуйте позже.")
            await state.clear()
            return

        # Получаем информацию о категории
        category = db.get_category_by_id(product['category_id'])
        category_name = category['name'] if category else 'Неизвестно'

        # Отправляем фото чека админам
        admin_ids = [785219206, 1927067668]  # ID админов
        for admin_id in admin_ids:
            try:
                caption = (
                    f"🆕 Новая заявка на оплату\n\n"
                    f"👤 Пользователь: {user_display}\n"  # Используем отформатированное имя
                    f"📦 Категория: {category_name}\n"
                    f"🛒 Товар: {product['name']}\n"
                    f"💵 Сумма: {product['stars_price']} руб.\n"
                    f"🕒 Время: {message.date.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                await bot.send_photo(
                    chat_id=admin_id,
                    photo=FSInputFile(photo_filename),
                    caption=caption,
                    reply_markup=create_close_request_keyboard(order_id)
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

        # Отправляем подтверждение пользователю
        await message.answer("✅ Ваш заказ успешно оплачен, ожидайте обратной связи от @sssofbot13☺️")
    else:
        await message.answer("❌ Произошла ошибка. Товар не найден.")

    await state.clear()


@user_router.message(PaymentStates.WAITING_RECEIPT)
async def handle_wrong_receipt(message: types.Message):
    await message.answer("Пожалуйста, отправьте фото чека об оплате.")


async def close_request_handler(callback_query: types.CallbackQuery):
    order_id = int(callback_query.data.split('_')[2])

    # Получаем заказ из базы данных
    order = db.get_order_by_id(order_id)
    if not order:
        await callback_query.answer("Заявка не найдена")
        return

    # Меняем статус заказа на 'closed' вместо удаления
    if db.update_order_status(order_id, 'closed'):
        # Удаляем сообщение с заявкой
        await callback_query.message.delete()
        await callback_query.answer("Заявка успешно закрыта")
    else:
        await callback_query.answer("❌ Ошибка при закрытии заявки")


@user_router.message()
async def handle_text(message: types.Message):
    await message.answer("Пожалуйста, воспользуйтесь кнопками меню для навигации по боту 👇",
                         reply_markup=create_main_menu_keyboard())


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
