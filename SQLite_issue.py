from sqlite3 import connect

conn = connect('library.db')
cursor = conn.cursor()

cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS books(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        year INTEGER NOT NULL
    );
    '''
)


def add_book(title: str, author: str, year: int):
    '''
    Добавляет новую книгу в базу данных
    :param title: str
    :param author: str
    :param year: int
    :return:
    '''
    cursor.execute(
        '''
        INSERT INTO books(title, author, year)
        VALUES (?,?,?);
        ''',
        (title, author, year)
    )
    conn.commit()


def get_all_books() -> list:
    '''
    Возвращает список всех книг в базе данных
    :return: list
    '''
    books = cursor.execute(
        '''
        SELECT * FROM books;
        '''
    ).fetchall()
    return list(books)


def update_info(id: int, title: str, author: str, year: int):
    '''
    Обновляет информацию о книге по ее идентификатору
    :param id: int
    :param title: str
    :param author: str
    :param year: int
    :return:
    '''
    cursor.execute(
        '''
        UPDATE books
        SET title = ?, author = ?, year = ?
        WHERE id = ?
        ''',
        (title, author, year, id)
    )
    conn.commit()


def delete_book(id: int):
    '''
    Удаляет информацию о книге по ее идентификатору
    :param id: int
    :return:
    '''
    cursor.execute(
        f'''
        DELETE FROM books
        WHERE id = {id}
        '''
    )
    conn.commit()


# Создание экземпляров
add_book('okokok', 'pisatel', 1932)
add_book('lalala', 'avtor', 2015)
print(get_all_books())

# Обновление информации
update_info(2, 'lalala', 'avtorKA', 2025)
print(get_all_books())

# Удаление экземпляра
delete_book(1)
print(get_all_books())


cursor.close()
conn.close()