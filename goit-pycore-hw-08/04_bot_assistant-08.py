
import pickle
import re
from collections import UserDict
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path


# ============================================================
# НАЛАШТУВАННЯ
# ============================================================

# Файл для збереження адресної книги.
DATA_FILE = Path("data") / "addressbook.pkl"


# Colorama використовується для кольорового виведення.
# Якщо бібліотека не встановлена, бот працюватиме і без кольорів.
try:
    from colorama import Fore, init

    init(autoreset=True)

except ImportError:
    class Fore:
        GREEN = ""
        YELLOW = ""
        RED = ""
        CYAN = ""
        MAGENTA = ""
        RESET = ""


WELCOME_BANNER = r"""
 _____                _                 _    ______         _
/  __ \              | |               | |   | ___ \       | |
| /  \/  ___   _ __  | |_   __ _   ___ | |_  | |_/ /  ___  | |_
| |     / _ \ | '_ \ | __| / _` | / __|| __| | ___ \ / _ \ | __|
| \__/\| (_) || | | || |_ | (_| || (__ | |_  | |_/ /| (_) || |_
 \____/ \___/ |_| |_| \__| \__,_| \___| \__| \____/  \___/  \__|
"""


HELP_TEXT = """
Доступні команди:

  hello
      Привітання бота.

  add <ім'я> <телефон>
      Додати новий контакт або телефон до існуючого.
      Приклад: add John 0631234567

  change <ім'я> <старий_телефон> <новий_телефон>
      Змінити номер телефону.
      Приклад: change John 0631234567 0671234567

  phone <ім'я>
      Показати телефони контакту.
      Приклад: phone John

  all
      Показати всі контакти.

  add-birthday <ім'я> <дата>
      Додати або змінити день народження.
      Формат дати: DD.MM.YYYY

  show-birthday <ім'я>
      Показати день народження контакту.

  birthdays
      Показати дні народження на найближчі 7 календарних днів.

  help
      Показати список команд.

  close / exit
      Завершити роботу бота.
"""


# ============================================================
# ЧАСТИНА 1. КЛАСИ АДРЕСНОЇ КНИГИ
# ============================================================

class Field:
    """Базовий клас для полів запису."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Name(Field):
    """Клас для зберігання імені контакту."""

    def __init__(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Ім'я контакту не може бути порожнім.")

        super().__init__(value.strip())


class Phone(Field):
    """Клас для зберігання та перевірки номера телефону."""

    def __init__(self, value):
        if not self.validate(value):
            raise ValueError(
                "Некоректний номер телефону. "
                "Номер повинен містити рівно 10 цифр."
            )

        super().__init__(value)

    @staticmethod
    def validate(phone_number):
        """Перевіряє, чи складається номер рівно з 10 цифр."""

        return (
            isinstance(phone_number, str)
            and len(phone_number) == 10
            and phone_number.isdigit()
        )


class Birthday(Field):
    """Клас для зберігання та перевірки дати народження."""

    def __init__(self, value):
        try:
            # Перевіряємо формат DD.MM.YYYY.
            if not isinstance(value, str) or not re.fullmatch(
                r"\d{2}\.\d{2}\.\d{4}", value
            ):
                raise ValueError

            # Перевіряємо календарну дату.
            birthday_date = datetime.strptime(
                value, "%d.%m.%Y"
            ).date()

            super().__init__(birthday_date)

        except ValueError:
            raise ValueError(
                "Некоректний формат дати. "
                "Використовуйте DD.MM.YYYY."
            )

    @property
    def date(self):
        """Повертає дату народження як об'єкт date."""

        return self.value


class Record:
    """Клас для зберігання інформації про один контакт."""

    def __init__(self, name):
        self.name = Name(name)
        self.phones = []
        self.birthday = None

    def add_phone(self, phone_number):
        """Додає телефон до контакту."""

        phone = Phone(phone_number)

        # Не дозволяємо додавати один і той самий номер двічі.
        if self.find_phone(phone_number):
            raise ValueError("Цей номер телефону вже є у контакті.")

        self.phones.append(phone)

    def find_phone(self, phone_number):
        """Шукає телефон за номером."""

        for phone in self.phones:
            if phone.value == phone_number:
                return phone

        return None

    def remove_phone(self, phone_number):
        """Видаляє телефон. Якщо його немає, генерує ValueError."""

        phone = self.find_phone(phone_number)

        if phone is None:
            raise ValueError(f"Телефон {phone_number} не знайдено.")

        self.phones.remove(phone)

    def edit_phone(self, old_phone, new_phone):
        """Безпечно змінює номер телефону."""

        old_phone_obj = self.find_phone(old_phone)

        if old_phone_obj is None:
            raise ValueError("Старий номер телефону не знайдено.")

        # Спочатку перевіряємо новий номер.
        new_phone_obj = Phone(new_phone)

        # Не дозволяємо дублювати інший номер цього контакту.
        existing_phone = self.find_phone(new_phone)

        if (
            existing_phone is not None
            and existing_phone is not old_phone_obj
        ):
            raise ValueError("Такий номер вже є у контакті.")

        # Змінюємо значення лише після успішної перевірки.
        old_phone_obj.value = new_phone_obj.value

    def add_birthday(self, birthday):
        """Додає або оновлює дату народження."""

        self.birthday = Birthday(birthday)

    def __str__(self):
        """Формує текстове представлення контакту."""

        phones_str = "; ".join(
            phone.value for phone in self.phones
        ) or "-"

        birthday_str = (
            self.birthday.value.strftime("%d.%m.%Y")
            if self.birthday
            else "-"
        )

        return (
            f"Ім'я: {self.name.value}, "
            f"телефони: {phones_str}, "
            f"день народження: {birthday_str}"
        )


class AddressBook(UserDict):
    """Клас адресної книги на основі UserDict."""

    def add_record(self, record):
        """Додає контакт. Дублікати заборонені."""

        name = record.name.value

        if name in self.data:
            raise ValueError(f"Контакт {name} вже існує.")

        self.data[name] = record

    def find(self, name):
        """Шукає контакт за ім'ям."""

        return self.data.get(name)

    def delete(self, name):
        """Видаляє контакт. Якщо його немає, генерує KeyError."""

        if name not in self.data:
            raise KeyError(f"Контакт {name} не знайдено.")

        del self.data[name]

    def get_upcoming_birthdays(self, days=7):
        """
        Повертає список контактів, яких потрібно привітати.

        Перевіряються сьогоднішній день і наступні 6 днів.
        Якщо день народження припадає на вихідний,
        дата привітання переноситься на понеділок.
        """

        upcoming_birthdays = []
        today = date.today()

        if days <= 0:
            return upcoming_birthdays

        # Сім календарних днів включно з поточним.
        last_day = today + timedelta(days=days - 1)

        for record in self.data.values():

            if record.birthday is None:
                continue

            birthday = record.birthday.date

            # Формуємо дату народження у поточному році.
            try:
                birthday_this_year = birthday.replace(
                    year=today.year
                )

            except ValueError:
                # 29 лютого у невисокосний рік.
                birthday_this_year = date(today.year, 2, 28)

            # Якщо день народження вже минув,
            # перевіряємо наступний рік.
            if birthday_this_year < today:
                try:
                    birthday_this_year = birthday.replace(
                        year=today.year + 1
                    )

                except ValueError:
                    birthday_this_year = date(
                        today.year + 1, 2, 28
                    )

            # Перевіряємо, чи день народження входить
            # у найближчі сім календарних днів.
            if today <= birthday_this_year <= last_day:

                congratulation_date = birthday_this_year

                # Субота — переносимо на понеділок.
                if congratulation_date.weekday() == 5:
                    congratulation_date += timedelta(days=2)

                # Неділя — переносимо на понеділок.
                elif congratulation_date.weekday() == 6:
                    congratulation_date += timedelta(days=1)

                upcoming_birthdays.append({
                    "name": record.name.value,
                    "congratulation_date": (
                        congratulation_date.strftime("%d.%m.%Y")
                    )
                })

        # Сортуємо список за датою привітання.
        upcoming_birthdays.sort(
            key=lambda item: datetime.strptime(
                item["congratulation_date"], "%d.%m.%Y"
            )
        )

        return upcoming_birthdays

    def __str__(self):
        """Повертає всі контакти у вигляді тексту."""

        return "\n".join(
            str(record) for record in self.data.values()
        )


# ============================================================
# ЧАСТИНА 2. ЗБЕРЕЖЕННЯ ТА ЗАВАНТАЖЕННЯ АДРЕСНОЇ КНИГИ
# ============================================================

def save_data(book, filename=DATA_FILE):
    """Зберігає весь об'єкт AddressBook у файл за допомогою pickle."""

    if not isinstance(book, AddressBook):
        raise TypeError(
            "Для збереження потрібно передати AddressBook."
        )

    file_path = Path(filename)

    # Створюємо папку data, якщо її ще немає.
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Режим wb — запис у бінарному форматі.
    with file_path.open("wb") as file:
        pickle.dump(
            book,
            file,
            protocol=pickle.HIGHEST_PROTOCOL
        )


def load_data(filename=DATA_FILE):
    """Відновлює AddressBook із pickle-файлу."""

    file_path = Path(filename)

    # Якщо файл ще не створений, повертаємо порожню книгу.
    if not file_path.exists():
        return AddressBook()

    try:
        # Режим rb — читання у бінарному форматі.
        with file_path.open("rb") as file:
            book = pickle.load(file)

        # Перевіряємо, що у файлі збережено саме AddressBook.
        if not isinstance(book, AddressBook):
            print(
                f"{Fore.YELLOW}Файл містить дані невідомого формату. "
                "Створено нову адресну книгу."
            )
            return AddressBook()

        return book

    except (
        pickle.UnpicklingError,
        EOFError,
        AttributeError,
        ImportError,
        IndexError,
        TypeError
    ) as error:
        print(
            f"{Fore.YELLOW}Не вдалося прочитати файл адресної книги: "
            f"{error}. Створено нову адресну книгу."
        )
        return AddressBook()


# ============================================================
# ЧАСТИНА 3. ОБРОБКА КОМАНД
# ============================================================

def parse_input(user_input):
    """Розділяє введений рядок на команду та аргументи."""

    parts = user_input.strip().split()

    if not parts:
        return "", []

    command = parts[0].lower()
    args = parts[1:]

    return command, args


def input_error(func):
    """Декоратор для обробки помилок введення."""

    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except ValueError as error:
            return f"{Fore.YELLOW}{error}"

        except KeyError as error:
            message = (
                error.args[0]
                if error.args
                else "Контакт не знайдено."
            )
            return f"{Fore.YELLOW}{message}"

        except IndexError as error:
            message = (
                error.args[0]
                if error.args
                else "Введіть необхідні аргументи команди."
            )
            return f"{Fore.YELLOW}{message}"

    return inner


def save_after_change(book):
    """Зберігає адресну книгу після зміни контактів."""

    save_data(book)


@input_error
def add_contact(args, book):
    """Додає новий контакт або телефон до існуючого."""

    if len(args) != 2:
        raise ValueError(
            "Введіть ім'я та телефон: add <ім'я> <телефон>."
        )

    name, phone = args

    # Перевіряємо телефон до створення нового контакту.
    validated_phone = Phone(phone)

    record = book.find(name)

    if record is None:
        record = Record(name)
        record.add_phone(validated_phone.value)
        book.add_record(record)

        save_after_change(book)

        return f"{Fore.GREEN}Контакт успішно додано."

    record.add_phone(validated_phone.value)

    save_after_change(book)

    return f"{Fore.GREEN}Телефон додано до існуючого контакту."


@input_error
def change_contact(args, book):
    """Змінює телефон контакту."""

    if len(args) != 3:
        raise ValueError(
            "Введіть: change <ім'я> <старий_телефон> <новий_телефон>."
        )

    name, old_phone, new_phone = args

    record = book.find(name)

    if record is None:
        raise KeyError("Контакт не знайдено.")

    record.edit_phone(old_phone, new_phone)

    save_after_change(book)

    return f"{Fore.GREEN}Номер телефону успішно змінено."


@input_error
def show_phone(args, book):
    """Показує телефони контакту."""

    if len(args) != 1:
        raise IndexError(
            "Введіть ім'я контакту: phone <ім'я>."
        )

    name = args[0]

    record = book.find(name)

    if record is None:
        raise KeyError("Контакт не знайдено.")

    phones = "; ".join(
        phone.value for phone in record.phones
    ) or "-"

    return f"{Fore.GREEN}{name}: {phones}"


@input_error
def show_all(args, book):
    """Показує всі контакти адресної книги."""

    if args:
        raise ValueError(
            "Команда all не приймає аргументів."
        )

    if not book:
        return f"{Fore.YELLOW}Адресна книга порожня."

    return f"{Fore.GREEN}{book}"


@input_error
def add_birthday(args, book):
    """Додає або змінює день народження контакту."""

    if len(args) != 2:
        raise ValueError(
            "Введіть: add-birthday <ім'я> <DD.MM.YYYY>."
        )

    name, birthday = args

    record = book.find(name)

    if record is None:
        raise KeyError(
            "Контакт не знайдено. Спочатку додайте контакт."
        )

    was_updated = record.birthday is not None

    record.add_birthday(birthday)

    save_after_change(book)

    if was_updated:
        return f"{Fore.GREEN}День народження оновлено."

    return f"{Fore.GREEN}День народження додано."


@input_error
def show_birthday(args, book):
    """Показує день народження контакту."""

    if len(args) != 1:
        raise IndexError(
            "Введіть ім'я контакту: show-birthday <ім'я>."
        )

    name = args[0]

    record = book.find(name)

    if record is None:
        raise KeyError("Контакт не знайдено.")

    if record.birthday is None:
        return (
            f"{Fore.YELLOW}"
            "Для цього контакту день народження не вказано."
        )

    birthday = record.birthday.value.strftime("%d.%m.%Y")

    return f"{Fore.GREEN}{name}: {birthday}"


@input_error
def birthdays(args, book):
    """Показує найближчі дні народження."""

    if args:
        raise ValueError(
            "Команда birthdays не приймає аргументів."
        )

    upcoming = book.get_upcoming_birthdays()

    if not upcoming:
        return (
            f"{Fore.YELLOW}"
            "Найближчими 7 днями днів народження немає."
        )

    lines = [
        f"{item['congratulation_date']}: {item['name']}"
        for item in upcoming
    ]

    return (
        f"{Fore.GREEN}Найближчі дні народження:\n"
        + "\n".join(lines)
    )


# ============================================================
# ЧАСТИНА 4. ГОЛОВНИЙ ЦИКЛ ПРОГРАМИ
# ============================================================

def main():
    """Керує циклом взаємодії з користувачем."""

    # Відновлюємо адресну книгу з попереднього сеансу.
    book = load_data()

    print(f"{Fore.CYAN}{WELCOME_BANNER}")
    print(f"{Fore.CYAN}Welcome to the assistant bot!")
    print(
        f"Введіть '{Fore.MAGENTA}help{Fore.RESET}' "
        "для перегляду списку команд."
    )

    try:
        while True:
            try:
                user_input = input("\nEnter a command: ").strip()

            except (EOFError, KeyboardInterrupt):
                print(f"\n{Fore.CYAN}Роботу бота завершено.")
                break

            # Ігноруємо порожнє введення.
            if not user_input:
                continue

            command, args = parse_input(user_input)

            if command in ("close", "exit"):
                print(f"{Fore.CYAN}Good bye!")
                break

            elif command == "hello" and not args:
                print(f"{Fore.GREEN}How can I help you?")

            elif command == "help" and not args:
                print(HELP_TEXT)

            elif command == "add":
                print(add_contact(args, book))

            elif command == "change":
                print(change_contact(args, book))

            elif command == "phone":
                print(show_phone(args, book))

            elif command == "all":
                print(show_all(args, book))

            elif command == "add-birthday":
                print(add_birthday(args, book))

            elif command == "show-birthday":
                print(show_birthday(args, book))

            elif command == "birthdays":
                print(birthdays(args, book))

            else:
                print(
                    f"{Fore.YELLOW}Невідома команда. "
                    "Введіть 'help' для перегляду доступних команд."
                )

    finally:
        # Зберігаємо адресну книгу перед завершенням програми.
        save_data(book)
        print(f"{Fore.GREEN}Адресну книгу збережено.")


# Запускаємо бота лише під час прямого запуску файлу.
if __name__ == "__main__":
    try:
        main()

    except OSError as error:
        print(f"{Fore.RED}Помилка роботи з файлом: {error}")


# Як запустити&
# Введи в термінал:
# poetry run python 04_bot_assistant.py
