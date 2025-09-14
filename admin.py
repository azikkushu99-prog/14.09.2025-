import logging
import os
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

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
    ADD_PRODUCT_STARS_PRICE = State()
    ADD_PRODUCT_INSTRUCTION = State()
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


def create_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📦 Покупка через оператора", "operator_categories"),
        ("⭐ Покупка за звезды", "stars_categories"),
        ("🏪 О магазине", "about_shop"),
        ("👤 Мой профиль", "profile"),
        ("🛟 Поддержка", "support"),
        ("🎁 Акции и скидки", "promotions"),
        ("⭐ Избранное", "favorites")
    ]
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    builder.adjust(2)
    return builder.as_markup()


def setup_admin_router(dp: Dispatcher):
    dp.include_router(admin_router)

    # Регистрируем обработчики в правильном порядке
    admin_router.callback_query.register(add_product_category_handler, F.data.startswith("admin_add_product_category_"))
    admin_router.callback_query.register(delete_category_handler, F.data.startswith("admin_delete_category_"))
    admin_router.callback_query.register(manage_products_handler, F.data.startswith("admin_manage_products_"))
    admin_router.callback_query.register(delete_product_handler, F.data.startswith("admin_delete_product_"))
    admin_router.callback_query.register(add_product_section_handler, F.data.startswith("admin_product_section_"))
    admin_router.callback_query.register(add_category_section_handler, F.data.startswith("admin_section_"))
    admin_router.callback_query.register(admin_callback_handler, F.data.startswith("admin_"))
    admin_router.callback_query.register(cancel_edit_handler, F.data == "admin_cancel_edit")

    admin_router.message.register(admin_command, Command("admin"))
    admin_router.message.register(add_category_name_handler, AdminStates.ADD_CATEGORY_NAME)
    admin_router.message.register(add_product_name_handler, AdminStates.ADD_PRODUCT_NAME)
    admin_router.message.register(add_product_price_handler, AdminStates.ADD_PRODUCT_PRICE)
    admin_router.message.register(add_product_stars_price_handler, AdminStates.ADD_PRODUCT_STARS_PRICE)
    admin_router.message.register(add_product_instruction_handler, AdminStates.ADD_PRODUCT_INSTRUCTION)
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
    keyboard.button(text="🏪 Редактировать 'О магазине'", callback_data="admin_edit_about_shop")
    keyboard.button(text="🎁 Редактировать 'Акции и скидки'", callback_data="admin_edit_promotions")
    keyboard.button(text="➕ Добавить категорию", callback_data="admin_add_category")
    keyboard.button(text="🛒 Добавить товар", callback_data="admin_add_product")
    keyboard.button(text="🗑️ Удаление категорий", callback_data="admin_manage_categories")
    keyboard.button(text="🗑️ Удаление товаров", callback_data="admin_manage_products")
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
        await callback_query.message.edit_text(
            f"📝 <b>Редактирование '{'О магазине' if section == 'about_shop' else 'Акции и скидки'}'</b>\n\n"
            f"Текущее содержание:\n{content}\n\n"
            "Отправьте новый текст:",
            parse_mode=ParseMode.HTML,
            reply_markup=create_cancel_edit_keyboard()  # Убрано .as_markup()
        )

    elif action == "admin_add_category":
        await start_add_category(callback_query, state)

    elif action == "admin_add_product":
        await start_add_product(callback_query, state)

    elif action == "admin_manage_categories":
        await show_categories_management(callback_query)

    elif action == "admin_manage_products":
        await show_products_management(callback_query)

    await callback_query.answer()


async def cancel_edit_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_admin_menu(callback_query=callback_query)
    await callback_query.answer("Редактирование отменено")


async def edit_section_text_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    section = user_data.get('editing_section')

    if not section:
        await message.answer("❌ Ошибка: не указан раздел для редактирования")
        await state.clear()
        return

    await state.update_data(new_content=message.text)
    await state.set_state(AdminStates.EDIT_SECTION_PHOTO)

    await message.answer(
        "✅ Текст сохранен. Теперь отправьте новое фото для раздела или нажмите 'Пропустить'",
        reply_markup=create_skip_photo_keyboard().as_markup()
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

    # Обрабатываем фото, если оно есть
    if message.photo:
        photo = message.photo[-1]
        photo_file = await message.bot.get_file(photo.file_id)
        photo_path = f"{SECTION_FOLDERS[section]}/{photo.file_id}.jpg"

        # Скачиваем фото
        await message.bot.download_file(photo_file.file_path, photo_path)

        # Сохраняем путь к фото в БД
        db.update_section_photo(section, photo_path)

        await message.answer(
            f"✅ Раздел '{'О магазине' if section == 'about_shop' else 'Акции и скидки'}' успешно обновлен с новым текстом и фото!",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
    else:
        await message.answer(
            f"✅ Раздел '{'О магазине' if section == 'about_shop' else 'Акции и скидки'}' успешно обновлен с новым текстом!",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )

    await state.clear()


def create_skip_photo_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⏭️ Пропустить загрузку фото", callback_data="admin_skip_photo")
    keyboard.button(text="❌ Отменить редактирование", callback_data="admin_cancel_edit")
    keyboard.adjust(1)
    return keyboard


@admin_router.callback_query(F.data == "admin_skip_photo")
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

    await callback_query.message.edit_text(
        f"✅ Раздел '{'О магазине' if section == 'about_shop' else 'Акции и скидки'}' успешно обновлен с новым текстом!",
        reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
    )

    await state.clear()
    await callback_query.answer()


async def start_add_category(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "📝 <b>Добавление новой категории</b>\n\n"
        "Введите название категории:",
        parse_mode=ParseMode.HTML,
        reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
    )
    await state.set_state(AdminStates.ADD_CATEGORY_NAME)


async def add_category_name_handler(message: types.Message, state: FSMContext):
    category_name = message.text
    await state.update_data(category_name=category_name)

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📦 Покупка через оператора", callback_data="admin_section_operator")
    keyboard.button(text="⭐ Покупка за звезды", callback_data="admin_section_stars")
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

    section_name = "оператора" if section == "operator" else "звезд"

    if db.add_category(category_name, None, None, section):
        await callback_query.message.edit_text(
            f"✅ Категория '{category_name}' успешно добавлена в раздел '{section_name}'!",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
    else:
        await callback_query.message.edit_text(
            "❌ Не удалось добавить категорию. Возможно, категория с таким именем уже существует.",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )

    await state.clear()
    await callback_query.answer()


async def start_add_product(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📦 Покупка через оператора", callback_data="admin_product_section_operator")
    keyboard.button(text="⭐ Покупка за звезды", callback_data="admin_product_section_stars")
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
            f"❌ Нет доступных категорий в выбранном разделе. Сначала добавьте категорию в раздел {'оператора' if section == 'operator' else 'звезд'}.",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
        await callback_query.answer()
        return

    keyboard = InlineKeyboardBuilder()
    for category in categories:
        keyboard.button(text=category['name'], callback_data=f"admin_add_product_category_{category['id']}")

    keyboard.button(text="⬅️ Отмена", callback_data="admin_back")
    keyboard.adjust(1)

    await callback_query.message.edit_text(
        "📦 Выберите категорию для товара:",
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
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_NAME)

    except Exception as e:
        logger.error(f"Ошибка при выборе категории: {e}")
        await callback_query.answer("❌ Ошибка при выборе категории")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка при выборе категории.",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )


async def add_product_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(product_name=message.text)
    user_data = await state.get_data()
    section = user_data.get('product_section')

    if section == "stars":
        await message.answer(
            "⭐ Введите цену товара в звездах (только число):",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_STARS_PRICE)
    else:
        await message.answer(
            "💵 Введите цену товара в рублях (только число):",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_PRICE)


async def add_product_price_handler(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        user_data = await state.get_data()

        name = user_data.get('product_name')
        category_id = user_data.get('product_category_id')
        section = user_data.get('product_section')

        if category_id is None or section is None:
            await message.answer(
                "❌ Не выбрана категория или раздел. Попробуйте добавить товар еще раз.",
                reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
            )
            await state.clear()
            return

        if db.add_product(name, "", price, 0, category_id, None, None, section):
            await message.answer(
                f"✅ Товар '{name}' успешно добавлен в категорию!",
                reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
            )
        else:
            await message.answer(
                "❌ Не удалось добавить товар в базу данных.",
                reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
            )
    except ValueError:
        await message.answer(
            "❌ Неверный формат цены. Введите число:",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении товара: {e}")
        await message.answer(
            "❌ Произошла ошибка при добавлении товара.",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )

    await state.clear()


async def add_product_stars_price_handler(message: types.Message, state: FSMContext):
    try:
        stars_price = int(message.text)
        await state.update_data(product_stars_price=stars_price)

        await message.answer(
            "📋 Пришлите инструкцию для активации подписки:",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
        await state.set_state(AdminStates.ADD_PRODUCT_INSTRUCTION)
    except ValueError:
        await message.answer(
            "❌ Неверный формат цены. Введите целое число:",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )


async def add_product_instruction_handler(message: types.Message, state: FSMContext):
    instruction = message.text
    user_data = await state.get_data()

    name = user_data.get('product_name')
    stars_price = user_data.get('product_stars_price')
    category_id = user_data.get('product_category_id')
    section = user_data.get('product_section')

    if db.add_product(name, "", 0, stars_price, category_id, instruction, None, section):
        await message.answer(
            f"✅ Товар '{name}' успешно добавлен в раздел 'Покупка за звезды'!\n"
            f"⭐ Цена: {stars_price} звёзд\n"
            f"📋 Инструкция: {instruction}",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
    else:
        await message.answer(
            "❌ Не удалось добавить товар в базу данных.",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )

    await state.clear()


async def show_categories_management(callback_query: types.CallbackQuery):
    categories = db.get_all_categories()

    if not categories:
        await callback_query.message.edit_text(
            "🗑️ <b>Удаление категорий</b>\n\n"
            "Пока нет добавленных категорий.",
            parse_mode=ParseMode.HTML,
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
        return

    text = "🗑️ <b>Удаление категорий</b>\n\nВыберите категорию для удаления:\n\n"
    keyboard = InlineKeyboardBuilder()

    for category in categories:
        products_count = len(db.get_products_by_category(category['id']))
        section_name = "оператора" if category['section'] == 'operator' else "звезд"
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
                reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
            )
        else:
            await callback_query.message.edit_text(
                "❌ Не удалось удалить категорию.",
                reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
            )
    else:
        await callback_query.message.edit_text(
            "❌ Категория не найдена.",
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )

    await callback_query.answer()


async def show_products_management(callback_query: types.CallbackQuery):
    categories = db.get_all_categories()

    if not categories:
        await callback_query.message.edit_text(
            "🗑️ <b>Удаление товары</b>\n\n"
            "Пока нет добавленных категорий.",
            parse_mode=ParseMode.HTML,
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
        return

    text = "🗑️ <b>Удаление товаров</b>\n\nВыберите категорию для управления товарами:\n\n"
    keyboard = InlineKeyboardBuilder()

    for category in categories:
        products = db.get_products_by_category(category['id'])
        section_name = "оператора" if category['section'] == 'operator' else "звезд"
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
            reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
        )
        return

    text = f"🗑️ <b>Товары в категории: {category['name']}</b>\n\nВыберите товар для удаления:\n\n"
    keyboard = InlineKeyboardBuilder()

    for product in products:
        if product['section'] == 'operator':
            text += f"• {product['name']} - {product['price']} руб.\n"
        else:
            text += f"• {product['name']} - {product['stars_price']} звёзд\n"

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
                reply_markup=create_back_to_admin_menu_keyboard()  # Убрано .as_markup()
            )
        else:
            await callback_query.message.edit_text(
                "❌ Не удалось удалить товар.",
            )
    else:
        await callback_query.message.edit_text(
            "❌ Товар не найден.",
            reply_markup=create_back_to_admin_menu_keyboard()
        )

    await callback_query.answer()