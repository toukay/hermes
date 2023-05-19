import csv
import sqlite3
from argparse import ArgumentParser
import os

BACKUP_FOLDER = 'backup'

def main(args: ArgumentParser):
    if args.all:
        tables = list_tables()
        if args.exclude_tables:
            tables = [table for table in tables if table not in args.exclude_tables]
    elif args.tables:
        tables = args.tables

    if args.backup:
        data = fetch_data(tables)
        write_csvs(data)
    elif args.restore:
        data = read_csvs(tables)
        insert_data(data)
    elif args.delete:
        delete_data(tables)
    elif args.list:
        tables = list_tables()
        print(tables)
    else:
        print('No action specified')


def write_csvs(data: dict[str, list[list[str]]]) -> None:
    print("Writing CSVs...")
    for table_name, data in data.items():
        with open(f'{BACKUP_FOLDER}{os.sep}{table_name}.csv', 'w') as f:
            writer = csv.writer(f)
            writer.writerows(data)
    print("CSVs written")


def read_csvs(tables: list[str]) -> dict[str, list[list[str]]]:
    print("Reading CSVs...")
    data = {}
    for table in tables:
        with open(f'{BACKUP_FOLDER}{os.sep}{table}.csv', 'r') as f:
            reader = csv.reader(f)
            data[table] = list(reader)
    print("CSVs read")
    return data


def fetch_data(tables: list[str]) -> dict[str, list[list[str]]]:
    print("Fetching data...")
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        data = {}
        for table in tables:
            # clean table name to prevent SQL injection
            table = process_name(table)
            query = f'SELECT * FROM {table}'
            cursor.execute(query)
            data[table] = cursor.fetchall()
        print("Data fetched")
        return data
    except Exception as e:
        print(e)
    finally:
        conn.close()


def delete_data(tables: list[str]) -> None:
    print("Deleting data...")
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        for table in tables:
            table = process_name(table)
            query = f'DELETE FROM {table}'
            cursor.execute(query)
        conn.commit()
        print("Data deleted")
    except Exception as e:
        print(e)
    finally:
        conn.close()


def list_tables() -> list[str]:
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        query = "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        cursor.execute(query)
        tables = cursor.fetchall()
        tables = [table[0] for table in tables]
        return tables
    except Exception as e:
        print(e)
    finally:
        conn.close()


def insert_data(data: dict[str, list[list[str]]]) -> None:
    print("Inserting data...")
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        for table_name, table_data in data.items():
            table_name = process_name(table_name)
            for row in table_data:
                query = f'INSERT INTO {table_name} VALUES ({",".join(["?"] * len(row))})'
                cursor.execute(query, row)
        conn.commit()
        print("Data inserted")
    except Exception as e:
        print(e)
    finally:
        conn.close()

# def add_column(table: str, column_header: str, column_value: str, pos: int) -> None: # add column to csv file at position pos with default value
#     with open(f'{table}.csv', 'r') as f:
#         reader = csv.reader(f)
#         data = list(reader)
#     for row in data:
#         row.insert(pos, column_value)
#     with open(f'{table}.csv', 'w') as f:
#         writer = csv.writer(f)
#         writer.writerows(data)
        
def process_name(name: str) -> str:
    return name.replace(';', '').strip()


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('-b', '--backup', action='store_true', help='Backup tables') # use if args.backup
    parser.add_argument('-r', '--restore', action='store_true', help='Restore tables') # use if args.restore
    parser.add_argument('-t', '--tables', type=str, nargs='+', help='Tables to backup or restore') # use if args.tables
    parser.add_argument('-et', '--exclude-tables', type=str, nargs='+', help='Tables to exclude from backup or restore') # use if args.exclude_tables
    parser.add_argument('-a', '--all', action='store_true', help='Backup or restore all tables') # use if args.all
    parser.add_argument('-l', '--list', action='store_true', help='List all tables') # use if args.list
    parser.add_argument('-d', '--delete', action='store_true', help='Delete all tables') # use if args.delete
    # parser.add_argument('-ac', '--add-column', type=str, help='Add a column to a csv file with default value')
    # parser.add_argument('-dc', '--delete-column', type=str, help='Delete a column from a csv file')
    # parser.add_argument('-cp', '--column-position', type=int, help='Position of column to change')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    # create backup folder if it doesn't exist
    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)
    main(args)