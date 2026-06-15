import sqlite3
import pandas as pd
import os
import glob

print('Creating database...')
db_path = os.path.join('..', 'OlistInsightAgent_APP', 'olist.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
print(f'successfully created database {db_path}')

print('Creating tables...')

csv_files = glob.glob("olist_*_dataset.csv")
if not csv_files:
    print("No Olist CSV files found in the current directory. Please check your path.")
else:
    print(f"Found {len(csv_files)} CSV files to import.")

for file in csv_files:
    table_name = os.path.splitext(os.path.basename(file))[0].replace('olist_', '').replace('_dataset', '')
    print(f'Processing file: {file} into table: {table_name}')
    try:
        df = pd.read_csv(file)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        print(f'Created table {table_name} from {file}')
    except Exception as e:
        print(f'Error processing file {table_name}: {e}')
    
print('All tables created successfully.')
conn.close()

