import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile

from db import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECTION_FOLDERS = {
    "about_shop": "Photo2",
    "promotions": "Photo3"
}

for folder in SECTION_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)


class AdminStates(StatesGroup):
    ADD_CATEGORY_NAME = State()
    ADD_CATEGORY_SECTION = State()
    ADD_PRODUCT_NAME = State()
    ADD_PRODUCT_PRICE = State()
    ADD_PRODUCT_SBP_PRICE = State()
    ADD_PRODUCT_DESCRIPTION = State()
    ADD_PRODUCT_SECTION = State()
    EDIT_SECTION_TEXT = State()
    EDIT_SECTION_PHOTO = State()


admin_router = Router()


def create_back_to_admin_menu_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⬅️ Назад в админ-панель", callback_data="admin_back")
    return keyboard.as_markup()


def create_cancel_edit_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="❌ Отменить редактирование", callback_data="admin_cancel_edit")
    return keyboard.as_markup()


def create_photo_edit_keyboard(has_photo: bool = False):
    keyboard = InlineKeyboardBuilder()

    if has_photo:
        keyboard.button(text="🗑️ Удалить фото", callback_data="admin_delete_photo")

    keyboard.button(text="⏭️ Пропустить загрузку фото", callback_data="admin_skip_photo")
    keyboard.button(text="❌ Отменить редактирование", callback_data="admin_cancel_edit")
    keyboard.adjust(1)
    return keyboard


def create_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📦 Покупка через оператора", "operator_categories"),
        ("💳 Покупка через СБП", "sbp_categories"),
        ("📦 Наличие товаров", "about_shop"),
        ("🛟 Поддержка", "support"),
        ("🎁 Акции и скидки", "promotions")
    ]
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    builder.adjust(2)
    return builder.as_markup()


def create_close_request_keyboard(order_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Закрыть заявку", callback_data=f"close_request_{order_id}")
    return builder.as_markup()


def create_skip_description_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🚫 Не добавлять описание", callback_data="admin_skip_description")
    keyboard.adjust(1)
    return keyboard.as_markup()


def setup_admin_router(dp: Dispatcher):
    dp.include_router(admin_router)

    # Регистрируем обработчики в правильном порядке
    admin_router.callback_query.register(cancel_edit_handler, F.data == "admin_cancel_edit")
    admin_router.callback_query.register(skip_photo_handler, F.data == "admin_skip_photo")
    admin_router.callback_query.register(delete_photo_handler, F.data == "admin_delete_photo")
    admin_router.callback_query.register(skip_description_handler, F.data == "admin_skip_description")
    admin_router.callback_query.register(add_product_category_handler, F.data.startswith("admin_add_product_category_"))
    admin_router.callback_query.register(delete_category_handler, F.data.startswith("admin_delete_category_"))
    admin_router.callback_query.register(manage_products_handler, F.data.startswith("admin_manage_products_"))
    admin_router.callback_query.register(delete_product_handler, F.data.startswith("admin_delete_product_"))
    admin_router.callback_query.register(add_product_section_handler, F.data.startswith("admin_product_section_"))
    admin_router.callback_query.register(add_category_section_handler, F.data.startswith("admin_section_"))
    admin_router.callback_query.register(admin_callback_handler, F.data.startswith("admin_"))
    admin_router.callback_query.register(show_closed_orders_handler, F.data == "admin_closed_orders")

    admin_router.message.register(admin_command, Command("admin"))
    admin_router.message.register(add_category_name_handler, AdminStates.ADD_CATEGORY_NAME)
    admin_router.message.register(add_product_name_handler, AdminStates.ADD_PRODUCT_NAME)
    admin_router.message.register(add_product_price_handler, AdminStates.ADD_PRODUCT_PRICE)
    admin_router.message.register(add_product_sbp_price_handler, AdminStates.ADD_PRODUCT_SBP_PRICE)
    admin_router.message.register(add_product_description_handler, AdminStates.ADD_PRODUCT_DESCRIPTION)
    admin_router.message.register(edit_section_text_handler, AdminStates.EDIT_SECTION_TEXT)
    admin_router.message.register(edit_section_photo_handler, AdminStates.EDIT_SECTION_PHOTO)


async def admin_command(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return

    await show_admin_menu(message)


async def show_admin_menu(message: types.Message = None, callback_query: types.CallbackQuery = None):
    text = """
👑 <b>Панель администратора</b>

Выберите действие:
"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📦 Редактировать 'Наличие товаров'", callback_data="admin_edit_about_shop")
    keyboard.button(text="🎁 Редактировать 'Акции и скидки'", callback_data="admin_edit_promotions")
    keyboard.button(text="➕ Добавить категорию", callback_data="admin_add_category")
    keyboard.button(text="🛒 Добавить товар", callback_data="admin_add_product")
    keyboard.button(text="🗑️ Удаление категорий", callback_data="admin_manage_categories")
    keyboard.button(text="🗑️ Удаление товаров", callback_data="admin_manage_products")
    keyboard.button(text="📄 Открытые заявки", callback_data="admin_pending_orders")
    keyboard.button(text="📂 Закрытые заявки", callback_data="admin_closed_orders")
    keyboard.button(text="⬅️ Назад в главное меню", callback_data="admin_back_to_main")
    keyboard.adjust(1)

    if message:
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard.as_markup())
    elif callback_query:
        await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard.as_markup())
        await callback_query.answer()


async def admin_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    if not db.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ У вас нет прав администратора.")
        return

    action = callback_query.data

    if action == "admin_back_to_main":
        await callback_query.message.edit_text(
            "Главное меню:",
            reply_markup=create_main_menu_keyboard()
        )

    elif action == "admin_back":
        await state.clear()
        await show_admin_menu(callback_query=callback_query)

    elif action.startswith("admin_edit_"):
        section = action.replace("admin_edit_", "")
        await state.update_data(editing_section=section)
        await state.set_state(AdminStates.EDIT_SECTION_TEXT)

        content = db.get_section_content(section)
        section_name = "Наличие товаров" if section == "about_shop" else "Акции и скидки"
        await callback_query.message.edit_text(
            f"📝 <b>Редактирование '{section_name}'</b>\n\n"
            f"Текущее содержание:\n{content}\n\n"
            "Отправьте новый текст:",
            parse_mode=ParseMode.HTML,
            reply_markup=create_cancel_edit_keyboard()
        )

    elif action == "admin_add_category":
        await start_add_category(callback_query, state)

    elif action == "admin_add_product":
        await start_add_product(callback_query, state)

    elif action == "admin_manage_categories":
        await show_categories_management(callback_query)

    elif action == "admin_manage_products":
        await show_products_management(callback_query)

    elif action == "admin_pending_orders":
        await show_pending_orders(callback_query)

    elif action == "admin_closed_orders":
        await show_closed_orders_handler(callback_query)

    await callback_query.answer()


async def show_pending_orders(callback_query: types.CallbackQuery):
    orders = db.get_orders_by_status('pending')

    if not orders:
        await callback_query.message.edit_text(
            "📄 <b>Открытые заявки</b>\n\nНа данный момент открытых заявок нет.",
            parse_mode=ParseMode.HTML,
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        return

    # Отправляем каждую заявку отдельным сообщением
    for order in orders:
        product = db.get_product_by_id(order['product_id'])
        category = db.get_category_by_id(product['category_id']) if product else None
        category_name = category['name'] if category else 'Неизвестно'

        # Используем сохраненное имя пользователя из базы данных
        caption = (
            f"📄 <b>Заявка #{order['id']}</b>\n\n"
            f"👤 Пользователь: {order['username']}\n"  # Уже отформатировано в основном коде
            f"📦 Категория: {category_name}\n"
            f"🛒 Товар: {product['name'] if product else 'Неизвестно'}\n"
            f"💵 Сумма: {order['amount']} руб.\n"
            f"🕒 Время: {order['created_at']}"
        )

        # Отправляем фото чека, если оно есть
        if order['photo_path'] and os.path.exists(order['photo_path']):
            await callback_query.message.answer_photo(
                photo=FSInputFile(order['photo_path']),
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=create_close_request_keyboard(order['id'])
            )
        else:
            await callback_query.message.answer(
                caption,
                parse_mode=ParseMode.HTML,
                reply_markup=create_close_request_keyboard(order['id'])
            )

    await callback_query.answer("Все открытые заявки отправлены")


async def show_closed_orders_handler(callback_query: types.CallbackQuery):
    # Сначала удаляем старые заявки (старше 7 дней)
    deleted_count = delete_old_closed_orders(7)

    orders = db.get_orders_by_status('closed')

    if not orders:
        await callback_query.message.edit_text(
            "📂 <b>Закрытые заявки</b>\n\nНа данный момент закрытых заявок нет.",
            parse_mode=ParseMode.HTML,
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        return

    # Отправляем сообщение о количестве удаленных заявок
    if deleted_count > 0:
        await callback_query.message.answer(
            f"🗑️ <b>Автоматически удалено {deleted_count} старых заявок</b>",
            parse_mode=ParseMode.HTML
        )

    # Отправляем каждую закрытую заявку отдельным сообщением с фото
    for order in orders:
        product = db.get_product_by_id(order['product_id'])
        category = db.get_category_by_id(product['category_id']) if product else None
        category_name = category['name'] if category else 'Неизвестно'

        # Используем сохраненное имя пользователя из базы данных
        caption = (
            f"🔒 <b>Закрытая заявка #{order['id']}</b>\n\n"
            f"👤 Пользователь: {order['username']}\n"  # Уже отформатировано в основном коде
            f"📦 Категория: {category_name}\n"
            f"🛒 Товар: {product['name'] if product else 'Неизвестно'}\n"
            f"💵 Сумма: {order['amount']} руб.\n"
            f"🕒 Время: {order['created_at']}"
        )

        # Отправляем фото чека, если оно есть
        if order['photo_path'] and os.path.exists(order['photo_path']):
            await callback_query.message.answer_photo(
                photo=FSInputFile(order['photo_path']),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        else:
            await callback_query.message.answer(
                caption,
                parse_mode=ParseMode.HTML
            )

    # Добавляем кнопку возврата в конце
    await callback_query.message.answer(
        "📂 <b>Просмотр закрытых заявок завершен</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=create_back_to_admin_menu_keyboard()
    )

    await callback_query.answer("Все закрытые заявки отправлены")


def delete_old_closed_orders(days: int):
    """Удаляет закрытые заявки старше указанного количества дней"""
    closed_orders = db.get_orders_by_status('closed')
    deleted_count = 0
    cutoff_date = datetime.now() - timedelta(days=days)

    for order in closed_orders:
        order_date = datetime.strptime(order['created_at'], '%Y-%m-%d %H:%M:%S')
        if order_date < cutoff_date:
            # Удаляем файл чека, если он существует
            if order['photo_path'] and os.path.exists(order['photo_path']):
                try:
                    os.remove(order['photo_path'])
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла чека: {e}")

            # Удаляем заказ из базы данных
            if db.delete_order(order['id']):
                deleted_count += 1

    return deleted_count


async def cancel_edit_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_admin_menu(callback_query=callback_query)
    await callback_query.answer("Редактирование отменено")


async def delete_photo_handler(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    section = user_data.get('editing_section')

    if not section:
        await callback_query.answer("❌ Ошибка: не указан раздел для редактирования")
        return

    # Получаем текущий путь к фото
    current_photo_path = db.get_section_photo(section)

    # Удаляем фото из файловой системы
    if current_photo_path and os.path.exists(current_photo_path):
        try:
            os.remove(current_photo_path)
        except Exception as e:
            logger.error(f"Ошибка при удалении фото: {e}")

    # Обновляем базу данных
    db.update_section_photo(section, None)

    await callback_query.message.edit_text(
        "✅ Фото удалено! Текст раздела обновлен.",
        reply_markup=create_back_to_admin_menu_keyboard()
    )
    await state.clear()
    await callback_query.answer()


async def edit_section_text_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    section = user_data.get('editing_section')

    if not section:
        await message.answer("❌ Ошибка: не указан раздел для редактирования")
        await state.clear()
        return

    await state.update_data(new_content=message.text)
    await state.set_state(AdminStates.EDIT_SECTION_PHOTO)

    # Проверяем, есть ли текущее фото
    current_photo_path = db.get_section_photo(section)
    has_photo = current_photo_path is not None and os.path.exists(current_photo_path)

    await message.answer(
        "✅ Текст сохранен. Теперь отправьте новое фото для раздела или выберите действие:",
        reply_markup=create_photo_edit_keyboard(has_photo).as_markup()
    )


async def edit_section_photo_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    section = user_data.get('editing_section')
    new_content = user_data.get('new_content')

    if not section or not new_content:
        await message.answer("❌ Ошибка: данные не найдены")
        await state.clear()
        return

    # Сохраняем текст
    db.update_section_content(section, new_content)

    # Удаляем старое фото, если оно есть
    old_photo_path = db.get_section_photo(section)
    if old_photo_path and os.path.exists(old_photo_path):
        try:
            os.remove(old_photo_path)
        except Exception as e:
            logger.error(f"Ошибка при удалении старого фото: {e}")

    # Обрабатываем новое фото, если оно есть
    if message.photo:
        photo = message.photo[-1]
        photo_file = await message.bot.get_file(photo.file_id)
        photo_path = f"{SECTION_FOLDERS[section]}/{photo.file_id}.jpg"

        # Скачиваем фото
        await message.bot.download_file(photo_file.file_path, photo_path)

        # Сохраняем путь к фото в БД
        db.update_section_photo(section, photo_path)

        section_name = "Наличие товаров" if section == "about_shop" else "Акции и скидки"
        await message.answer(
            f"✅ Раздел '{section_name}' успешно обновлен с новым текстом и фото!",
            reply_markup=create_back_to_admin_menu_keyboard()
        )
    else:
        section_name = "Наличие товаров" if section == "about_shop" else "Акции и скидки"
        await message.answer(
            f"✅ Раздел '{section_name}' успешно обновлен с новым текстам!",
            reply_markup=create_back_to_admin_menu_keyboard()
        )

    await state.clear()


async def skip_photo_handler(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    section = user_data.get('editing_section')
    new_content = user_data.get('new_content')

    if not section or not new_content:
        await callback_query.message.edit_text("❌ Ошибка: данные не найдены")
        await state.clear()
        return

    # Сохраняем только текст
    db.update_section_content(section, new_content)

    section_name = "Наличие товаров" if section == "about_shop" else "Акции и скидки"
    await callback_query.message.edit_text(
        f"✅ Раздел '{section_name}' успешно обновлен с новым текстам!",
        reply_markup=create_back_to_admin_menu_keyboard()
    )

    await state.clear()
    await callback_query.answer()


async def start_add_category(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "📝 <b>Добавление новой категории</b>\n\n"
        "Введите название категории:",
        parse_mode=ParseMode.HTML,
        reply_markup=create_back_to_admin_menu_keyboard()
    )
    await state.set_state(AdminStates.ADD_CATEGORY_NAME)


async def add_category_name_handler(message: types.Message, state: FSMContext):
    category_name = message.text
    await state.update_data(category_name=category_name)

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📦 Покупка через оператора", callback_data="admin_section_operator")
    keyboard.button(text="💳 Покупка через СБП", callback_data="admin_section_sbp")
    keyboard.adjust(1)

    await message.answer(
        "📝 <b>Выберите раздел для категории:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(AdminStates.ADD_CATEGORY_SECTION)


async def add_category_section_handler(callback_query: types.CallbackQuery, state: FSMContext):
    section = callback_query.data.replace("admin_section_", "")
    user_data = await state.get_data()
    category_name = user_data.get('category_name')

    section_name = "оператора" if section == "operator" else "СБП"

    if db.add_category(category_name, None, None, section):
        await callback_query.message.edit_text(
            f"✅ Категория '{category_name}' успешно добавлена в раздел '{section_name}'!",
            reply_markup=create_back_to_admin_menu_keyboard()
        )
    else:
        await callback_query.message.edit_text(
            "❌ Не удалось добавить категорию. Возможно, категория с таким именем уже существует.",
            reply_markup=create_back_to_admin_menu_keyboard()
        )

    await state.clear()
    await callback_query.answer()


async def start_add_product(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📦 Покупка через оператора", callback_data="admin_product_section_operator")
    keyboard.button(text="💳 Покупка через СБП", callback_data="admin_product_section_sbp")
    keyboard.adjust(1)

    await callback_query.message.edit_text(
        "📝 <b>Выберите раздел для товара:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(AdminStates.ADD_PRODUCT_SECTION)


async def add_product_section_handler(callback_query: types.CallbackQuery, state: FSMContext):
    section = callback_query.data.replace("admin_product_section_", "")
    await state.update_data(product_section=section)

    # Для всех типов товаров запрашиваем категорию
    categories = db.get_categories_by_section(section)

    if not categories:
        await callback_query.message.edit_text(
            f"❌ Нет доступных категорий в выбранном разделе. Сначала добавьте категорию в раздел {'оператора' if section == 'operator' else 'СБП'}.",
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        await callback_query.answer()
        return

    keyboard = InlineKeyboardBuilder()
    for category in categories:
        keyboard.button(text=category['name'], callback_data=f"admin_add_product_category_{category['id']}")

    keyboard.button(text="⬅️ Отмена", callback_data="admin_back")
    keyboard.adjust(1)

    await callback_query.message.edit_text(
        "📦 Выберите категорие для товара:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard.as_markup()
    )
    await callback_query.answer()


async def add_product_category_handler(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        # Извлекаем category_id из callback_data
        callback_data = callback_query.data
        logger.info(f"Received callback data: {callback_data}")

        # Извлекаем число после префикса
        category_id = int(callback_data.replace("admin_add_product_category_", ""))
        logger.info(f"Extracted category ID: {category_id}")

        # Сохраняем category_id в состоянии
        await state.update_data(product_category_id=category_id)

        # Немедленно отвечаем на callback
        await callback_query.answer()

        # Запрашиваем название товара
        await callback_query.message.edit_text(
            "📝 Введите название товара:",
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_NAME)

    except Exception as e:
        logger.error(f"Ошибка при выборе категории: {e}")
        await callback_query.answer("❌ Ошибка при выборе категории")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка при выборе категории.",
            reply_markup=create_back_to_admin_menu_keyboard()
        )


async def add_product_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(product_name=message.text)
    user_data = await state.get_data()
    section = user_data.get('product_section')

    if section == "sbp":
        await message.answer(
            "💳 Введите цену товара в рублях для оплаты через СБП:",
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_SBP_PRICE)
    else:
        await message.answer(
            "💵 Введите цену товара в рублях (только число):",
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_PRICE)


async def add_product_price_handler(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(product_price=price)

        await message.answer(
            "📝 Введите описание товара (или нажмите кнопку чтобы пропустить):",
            reply_markup=create_skip_description_keyboard()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_DESCRIPTION)
    except ValueError:
        await message.answer(
            "❌ Неверный формат цены. Введите число:",
            reply_markup=create_back_to_admin_menu_keyboard()
        )


async def add_product_sbp_price_handler(message: types.Message, state: FSMContext):
    try:
        sbp_price = int(message.text)
        await state.update_data(product_stars_price=sbp_price)

        await message.answer(
            "📝 Введите описание товара (или нажмите кнопку чтобы пропустить):",
            reply_markup=create_skip_description_keyboard()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_DESCRIPTION)
    except ValueError:
        await message.answer(
            "❌ Неверный формат цена. Введите целое число:",
            reply_markup=create_back_to_admin_menu_keyboard()
        )


async def add_product_description_handler(message: types.Message, state: FSMContext):
    description = message.text
    await process_product_description(message, state, description)


async def skip_description_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await process_product_description(callback_query, state, "")


async def process_product_description(message_or_callback, state: FSMContext, description: str):
    user_data = await state.get_data()

    name = user_data.get('product_name')
    category_id = user_data.get('product_category_id')
    section = user_data.get('product_section')

    if section == "operator":
        price = user_data.get('product_price', 0)
        stars_price = 0
    else:
        price = 0
        stars_price = user_data.get('product_stars_price', 0)

    if db.add_product(name, description, price, stars_price, category_id, None, section):
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(
                f"✅ Товар '{name}' успешно добавлен!",
                reply_markup=create_back_to_admin_menu_keyboard()
            )
        else:
            await message_or_callback.message.edit_text(
                f"✅ Товар '{name}' успешно добавлен!",
                reply_markup=create_back_to_admin_menu_keyboard()
            )
    else:
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(
                "❌ Не удалось добавить товар в базу данных.",
                reply_markup=create_back_to_admin_menu_keyboard()
            )
        else:
            await message_or_callback.message.edit_text(
                "❌ Не удалось добавить товар в базу данных.",
                reply_markup=create_back_to_admin_menu_keyboard()
            )

    await state.clear()


async def show_categories_management(callback_query: types.CallbackQuery):
    categories = db.get_all_categories()

    if not categories:
        await callback_query.message.edit_text(
            "🗑️ <b>Удаление категорий</b>\n\n"
            "Пока нет добавленных категорий.",
            parse_mode=ParseMode.HTML,
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        return

    text = "🗑️ <b>Удаление категорий</b>\n\nВыберите категорию для удаления:\n\n"
    keyboard = InlineKeyboardBuilder()

    for category in categories:
        products_count = len(db.get_products_by_category(category['id']))
        section_name = "оператора" if category['section'] == 'operator' else "СБП"
        text += f"• {category['name']} (раздел: {section_name}, {products_count} товаров)\n"
        keyboard.button(text=f"🗑️ {category['name']}", callback_data=f"admin_delete_category_{category['id']}")

    keyboard.button(text="⬅️ Назад", callback_data="admin_back")
    keyboard.adjust(1)

    await callback_query.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard.as_markup()
    )


async def delete_category_handler(callback_query: types.CallbackQuery):
    category_id = int(callback_query.data.split('_')[3])
    category = db.get_category_by_id(category_id)

    if category:
        # Сначала удаляем все товары в этой категории
        products = db.get_products_by_category(category_id)
        for product in products:
            db.delete_product(product['id'])

        # Затем удаляем саму категорию
        if db.delete_category(category_id):
            await callback_query.message.edit_text(
                f"✅ Категория '{category['name']}' и все её товары ({len(products)} шт.) успешно удалены!",
                reply_markup=create_back_to_admin_menu_keyboard()
            )
        else:
            await callback_query.message.edit_text(
                "❌ Не удалось удалить категорию.",
                reply_markup=create_back_to_admin_menu_keyboard()
            )
    else:
        await callback_query.message.edit_text(
            "❌ Категория не найдена.",
            reply_markup=create_back_to_admin_menu_keyboard()
        )

    await callback_query.answer()


async def show_products_management(callback_query: types.CallbackQuery):
    categories = db.get_all_categories()

    if not categories:
        await callback_query.message.edit_text(
            "🗑️ <b>Удаление товаров</b>\n\n"
            "Пока нет добавленных категорий.",
            parse_mode=ParseMode.HTML,
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        return

    text = "🗑️ <b>Удаление товаров</b>\n\nВыберите категорию для управления товарами:\n\n"
    keyboard = InlineKeyboardBuilder()

    for category in categories:
        products = db.get_products_by_category(category['id'])
        section_name = "оператора" if category['section'] == 'operator' else "СБП"
        text += f"📦 {category['name']} (раздел: {section_name}, {len(products)} товаров)\n"
        keyboard.button(text=f"📋 {category['name']}", callback_data=f"admin_manage_products_{category['id']}")

    keyboard.button(text="⬅️ Назад", callback_data="admin_back")
    keyboard.adjust(1)

    await callback_query.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard.as_markup()
    )


async def manage_products_handler(callback_query: types.CallbackQuery):
    category_id = int(callback_query.data.split('_')[3])
    category = db.get_category_by_id(category_id)
    products = db.get_products_by_category(category_id)

    if not products:
        await callback_query.message.edit_text(
            f"🗑️ <b>Товары в категории: {category['name']}</b>\n\n"
            "Пока нет товаров в этой категории.",
            parse_mode=ParseMode.HTML,
            reply_markup=create_back_to_admin_menu_keyboard()
        )
        return

    text = f"🗑️ <b>Товары в категории: {category['name']}</b>\n\nВыберите товар для удаления:\n\n"
    keyboard = InlineKeyboardBuilder()

    for product in products:
        if product['section'] == 'operator':
            text += f"• {product['name']} - {product['price']} руб.\n"
        else:
            text += f"• {product['name']} - {product['stars_price']} руб.\n"

        keyboard.button(text=f"🗑️ {product['name']}", callback_data=f"admin_delete_product_{product['id']}")

    keyboard.button(text="⬅️ Назад", callback_data="admin_manage_products")
    keyboard.adjust(1)

    await callback_query.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard.as_markup()
    )


async def delete_product_handler(callback_query: types.CallbackQuery):
    product_id = int(callback_query.data.split('_')[3])
    product = db.get_product_by_id(product_id)

    if product:
        if db.delete_product(product_id):
            await callback_query.message.edit_text(
                f"✅ Товар '{product['name']}' успешно удален!",
                reply_markup=create_back_to_admin_menu_keyboard()
            )
        else:
            await callback_query.message.edit_text(
                "❌ Не удалось удалить товар.",
                reply_markup=create_back_to_admin_menu_keyboard()
            )
    else:
        await callback_query.message.edit_text(
            "❌ Товар не найден.",
            reply_markup=create_back_to_admin_menu_keyboard()
        )

    await callback_query.answer()
