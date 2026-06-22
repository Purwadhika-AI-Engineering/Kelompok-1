import sqlite3
import pandas as pd
import os


print("🤖 Starting PRD-Aligned Data Engineering Pipeline...")

db_path = os.path.join('OlistInsightAgent_APP', 'olist.db')

if os.path.exists(db_path):
    os.remove(db_path)
    print("🧹 Cleaned old database file.")

os.makedirs(os.path.dirname(db_path), exist_ok=True)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
print(f'✅ Successfully created database connection at: {db_path}')

# load the CSV files into pandas DataFrames
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'

print('\n📥 Loading source CSV datasets into memory...')
orders = pd.read_csv(os.path.join(script_dir, 'olist_orders_dataset.csv'))
items = pd.read_csv(os.path.join(script_dir, 'olist_order_items_dataset.csv'))
payments = pd.read_csv(os.path.join(script_dir, 'olist_order_payments_dataset.csv'))
reviews = pd.read_csv(os.path.join(script_dir, 'olist_order_reviews_dataset.csv'))
customers = pd.read_csv(os.path.join(script_dir, 'olist_customers_dataset.csv'))
products = pd.read_csv(os.path.join(script_dir, 'olist_products_dataset.csv'))
sellers = pd.read_csv(os.path.join(script_dir, 'olist_sellers_dataset.csv'))
translation = pd.read_csv(os.path.join(script_dir, 'product_category_name_translation.csv'))

'''
make the order_summary table with the following columns: 
order_id, customer_id, customer_unique_id, customer_state, customer_city, order_status, order_purchase_timestamp, order_approved_at, 
order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date, review_score, review_answer_timestamp, 
total_payment, payment_type, payment_installments, delivery_days, late_delivery, seller_prep_days, carrier_transit_days
'''

reviews_agg = reviews.groupby('order_id').agg(
    review_score=('review_score', 'last'),
    review_answer_timestamp=('review_answer_timestamp', 'last')
).reset_index()

payments_agg = payments.groupby('order_id').agg(
    total_payment=('payment_value', 'sum'),
    payment_type=('payment_type', lambda x: ', '.join(x.dropna().unique())),
    payment_installments=('payment_installments', 'max')
).reset_index()

order_summary = orders.merge(customers[['customer_id', 'customer_unique_id', 'customer_state', 'customer_city']], on='customer_id', how='left') \
    .merge(reviews_agg, on='order_id', how='left') \
    .merge(payments_agg, on='order_id', how='left')

date_cols = [
    'order_purchase_timestamp', 'order_approved_at', 
    'order_delivered_carrier_date', 'order_delivered_customer_date', 
    'order_estimated_delivery_date'
]
for col in date_cols:
    order_summary[col] = pd.to_datetime(order_summary[col], errors='coerce')

order_summary['delivery_days'] = (order_summary['order_delivered_customer_date'] - order_summary['order_purchase_timestamp']).dt.days
order_summary['late_delivery'] = order_summary['order_delivered_customer_date'] > order_summary['order_estimated_delivery_date']
order_summary['seller_prep_days'] = (order_summary['order_delivered_carrier_date'] - order_summary['order_approved_at']).dt.days
order_summary['carrier_transit_days'] = (order_summary['order_delivered_customer_date'] - order_summary['order_delivered_carrier_date']).dt.days

'''
make item_detail table with the following columns:
order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, 
freight_value, product_category_name_english, product_name_length, product_description_length, 
product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm
'''

products = products.rename(columns={'product_name_lenght': 'product_name_length', 'product_description_lenght': 'product_description_length'})

item_detail = items.merge(products, on='product_id', how='left') \
    .merge(translation, on='product_category_name', how='left') \
    .merge(sellers[['seller_id', 'seller_city', 'seller_state']], on='seller_id', how='left') \
    .merge(order_summary[['order_id', 'order_delivered_carrier_date']], on='order_id', how='left')

item_detail['shipping_limit_date'] = pd.to_datetime(item_detail['shipping_limit_date'], errors='coerce')
item_detail['order_delivered_carrier_date'] = pd.to_datetime(item_detail['order_delivered_carrier_date'], errors='coerce')

item_detail['seller_shipped_on_time'] = (
    (item_detail['shipping_limit_date'] >= item_detail['order_delivered_carrier_date']) & 
    (item_detail['order_delivered_carrier_date'].notna())
)

item_detail = item_detail.drop(columns=['product_category_name', 'order_delivered_carrier_date'])


'''
Write the DataFrames to the SQLite database.
on order_summary table, use 'replace' mode to overwrite if it already exists, and do not write the index, make the order_id the primary key.
on item_detail table, use 'replace' mode to overwrite if it already exists, and do not write the index, make the combination of order_id and order_item_id the primary key.
'''

order_summary.to_sql('order_summary', conn, if_exists='replace', index=False, dtype={'order_id': 'TEXT PRIMARY KEY'})

item_detail.to_sql('item_detail', conn, if_exists='replace', index=False)
cursor.execute("CREATE UNIQUE INDEX idx_item_detail_pk ON item_detail (order_id, order_item_id);")

print('✅ Successfully created tables: order_summary and item_detail in the SQLite database.')

conn.commit()
conn.close()
print("🔒 Database connection closed. PRD-Aligned Data Engineering Pipeline completed successfully!")

