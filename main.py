import logging
import asyncio
import uuid
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from db import db
from admin import setup_admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = '7243978024:AAG41V9EMPrJ4HZntWQfTVGskLjOEDo5BZM'

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)
user_router = Router()

setup_admin_router(dp)
dp.include_router(user_router)


def create_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📦 Покупка через оператора", "operator_categories"),
        ("⭐ Покупка за звезды", "stars_categories"),
        ("🏪 О магазине", "about_shop"),
        ("🛟 Поддержка", "support"),
        ("🎁 Акции и скидки", "promotions")
    ]
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    builder.adjust(2)
    return builder.as_markup()


def create_back_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    return builder.as_markup()


def create_back_to_products_button(category_id, section_type):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к товарам", callback_data=f"{section_type}_category_{category_id}")
    return builder.as_markup()


def create_stars_payment_keyboard(product_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Купить за звезды", callback_data=f"buy_with_stars_{product_id}")
    builder.button(text="⬅️ Назад к товарам", callback_data="stars_category_back")
    builder.adjust(1)
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
    if callback_data == 'stars_category_back':
        await show_categories(callback_query, 'stars')
        return
    if callback_data == 'operator_categories':
        await show_categories(callback_query, 'operator')
        return
    if callback_data == 'stars_categories':
        await show_categories(callback_query, 'stars')
        return
    if callback_data.startswith('buy_with_stars_'):
        product_id = int(callback_data.split('_')[3])
        await process_stars_payment(callback_query, product_id)
        return
    if callback_data.startswith('operator_category_'):
        category_id = int(callback_data.split('_')[2])
        await show_products(callback_query, category_id, 'operator')
        return
    if callback_data.startswith('stars_category_'):
        category_id = int(callback_data.split('_')[2])
        await show_products(callback_query, category_id, 'stars')
        return
    if callback_data.startswith('operator_product_'):
        product_id = int(callback_data.split('_')[2])
        await show_product_details(callback_query, product_id, 'operator')
        return
    if callback_data.startswith('stars_product_'):
        product_id = int(callback_data.split('_')[2])
        await show_product_details(callback_query, product_id, 'stars')
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
    section_name = "Покупка через оператора" if section_type == 'operator' else "Покупка за звезды"
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
    section_name = "Покупка через оператора" if section_type == 'operator' else "Покупка за звезды"
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
                    keyboard.button(text=f"{product['name']} - {product['stars_price']} звёзд",
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
            text = f"⭐ <b>{product['name']}</b>\n\n{product['description']}\n\n💫 Цена: {product['stars_price']} звёзд\n📦 Категория: {category['name'] if category else 'Неизвестно'}"
            reply_markup = create_stars_payment_keyboard(product_id)
        try:
            await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except:
            await callback_query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await callback_query.answer("Товар не найден.")
    await callback_query.answer()


async def process_stars_payment(callback_query: types.CallbackQuery, product_id: int):
    product = db.get_product_by_id(product_id)
    user_id = callback_query.from_user.id
    if not product or product['stars_price'] <= 0:
        await callback_query.answer("❌ Этот товар нельзя купить за звезды.")
        return
    payload = str(uuid.uuid4())
    payment_id = db.create_star_payment(user_id=user_id, product_id=product_id, amount=product['stars_price'],
                                        payload=payload)
    if not payment_id:
        await callback_query.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        return

    prices = [LabeledPrice(label=product['name'], amount=product['stars_price'])]

    try:
        await bot.send_invoice(
            chat_id=callback_query.message.chat.id,
            title=product['name'],
            description=f"Оплата {product['stars_price']} звёзд",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="create_invoice_stars",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке инвойса: {e}")
        await callback_query.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        db.update_star_payment_status(payment_id, "failed")

    await callback_query.answer()


@user_router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    try:
        payment = db.get_star_payment_by_payload(pre_checkout_query.invoice_payload)
        if not payment:
            await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Платеж не найден")
            return
        product = db.get_product_by_id(payment['product_id'])
        if not product or product['stars_price'] <= 0:
            await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False,
                                                error_message="Товар больше не доступен")
            return
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        logger.error(f"Ошибка при обработке pre-checkout запроса: {e}")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False,
                                            error_message="Произошла ошибка при обработке платежа")


@user_router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    try:
        successful_payment = message.successful_payment
        user_id = message.from_user.id

        payment = db.get_star_payment_by_payload(successful_payment.invoice_payload)
        if not payment:
            logger.error(f"Платеж не найден для payload: {successful_payment.invoice_payload}")
            await message.answer("❌ Произошла ошибка при обработке вашего платежа. Обратитесь в поддержку.")
            return

        db.update_star_payment_status(
            payment_id=payment['id'],
            status="completed",
            telegram_payment_charge_id=successful_payment.telegram_payment_charge_id,
            provider_payment_charge_id=successful_payment.provider_payment_charge_id
        )

        product = db.get_product_by_id(payment['product_id'])
        if not product:
            logger.error(f"Товар не найден для payment: {payment}")
            await message.answer("❌ Произошла ошибка при обработке вашего платежа. Обратитесь в поддержку.")
            return

        success_text = f"""
🎉 <b>Покупка успешно завершена!</b>

Вы приобрели: <b>{product['name']}</b>
Стоимость: <b>{successful_payment.total_amount} звёзд</b>
"""
        await message.answer(success_text, parse_mode=ParseMode.HTML)

        if product.get('activation_instruction'):
            instruction_text = f"""
📋 <b>Инструкция для активации:</b>
{product['activation_instruction']}

💫 <i>Спасибо за покупку! Если возникнут проблемы, обратитесь в поддержку.</i>
"""
            await message.answer(instruction_text, parse_mode=ParseMode.HTML)
        else:
            await message.answer("❌ Инструкция по активации не найдена. Пожалуйста, обратитесь в поддержку @sssofbot13")

    except Exception as e:
        logger.error(f"Ошибка при обработке успешного платежа: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке вашего платежа. Обратитесь в поддержку.")


@user_router.message()
async def handle_text(message: types.Message):
    await message.answer("Пожалуйста, воспользуйтесь кнопками меню для навигации по боту 👇",
                         reply_markup=create_main_menu_keyboard())


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
