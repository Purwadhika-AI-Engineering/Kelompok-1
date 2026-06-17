import sqlite3
import pandas as pd
import os

def create_optimized_db():
    print("🤖 Starting Data Engineering ETL Pipeline for Agentic Olist...")
    
    db_path = os.path.join('..', 'OlistInsightAgent_APP', 'olist.db')
    
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    if os.path.exists(db_path):
        os.remove(db_path)
        print("🧹 Cleaned old database file.")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f'✅ Successfully created database connection at: {db_path}')

    print('\n📥 Loading source CSV datasets into memory...')
    orders = pd.read_csv('olist_orders_dataset.csv')
    items = pd.read_csv('olist_order_items_dataset.csv')
    payments = pd.read_csv('olist_order_payments_dataset.csv')
    reviews = pd.read_csv('olist_order_reviews_dataset.csv')
    customers = pd.read_csv('olist_customers_dataset.csv')
    products = pd.read_csv('olist_products_dataset.csv')
    sellers = pd.read_csv('olist_sellers_dataset.csv')
    translation = pd.read_csv('product_category_name_translation.csv')


    print('🧮 Constructing highly-compact order_summary table...')
    
    items['item_total_cost'] = items['price'] + items['freight_value']
    items_agg = items.groupby('order_id').agg(
        total_items=('order_item_id', 'count'),
        unique_products=('product_id', 'nunique'),
        total_items_price=('item_total_cost', 'sum')
    ).reset_index()

    # Pre-aggregate cash values from payments table
    payments_agg = payments.groupby('order_id').agg(
        total_amount_paid=('payment_value', 'sum'),
        payment_installments=('payment_installments', 'max'),
        payment_types=('payment_type', lambda x: ', '.join(sorted(x.unique())))
    ).reset_index()

    # Pre-aggregate review rating scores (collapsing multi-reviews if any)
    reviews_agg = reviews.groupby('order_id').agg(
        avg_review_score=('review_score', 'mean')
    ).reset_index()

    # Master join for order summary mapping customer details cleanly
    order_summary = orders[['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp']].copy()
    order_summary = order_summary.merge(
        customers[['customer_id', 'customer_unique_id', 'customer_city', 'customer_state']], 
        on='customer_id', 
        how='left'
    ).drop(columns=['customer_id']) # Drop confusing transactional customer_id

    order_summary = order_summary.merge(items_agg, on='order_id', how='left')
    order_summary = order_summary.merge(payments_agg, on='order_id', how='left')
    order_summary = order_summary.merge(reviews_agg, on='order_id', how='left')

    # Handle defaults/fill nulls structurally
    order_summary['total_items'] = order_summary['total_items'].fillna(0).astype(int)
    order_summary['unique_products'] = order_summary['unique_products'].fillna(0).astype(int)
    order_summary['total_items_price'] = order_summary['total_items_price'].fillna(0.0)
    order_summary['total_amount_paid'] = order_summary['total_amount_paid'].fillna(0.0)
    order_summary['payment_installments'] = order_summary['payment_installments'].fillna(0).astype(int)
    order_summary['payment_types'] = order_summary['payment_types'].fillna('unknown')

    # Calculated Voucher/Subsidy Column (Strategic Analytics Asset)
    order_summary['subsidy_difference'] = (order_summary['total_items_price'] - order_summary['total_amount_paid']).round(2)

    # Save to database
    order_summary.to_sql('order_summary', conn, if_exists='replace', index=False)
    print(' -> Table [order_summary] engineered successfully.')

    # ==========================================
    # STEP 3: PIPELINE FOR 'item_detail' (PRD 8.3)
    # ==========================================
    print('📦 Constructing granular item_detail table...')
    
    # Merge translation to product dimensions first
    products_enriched = products.merge(translation, on='product_category_name', how='left')
    products_enriched['product_category_en'] = products_enriched['product_category_name_english'].fillna(products_enriched['product_category_name']).fillna('unknown')
    
    # Flatten everything down to the order item grain
    item_detail = items[['order_id', 'order_item_id', 'product_id', 'seller_id', 'price', 'freight_value']].copy()
    item_detail = item_detail.merge(
        products_enriched[['product_id', 'product_category_en', 'product_description_lenght', 'product_photos_qty', 'product_weight_g']],
        on='product_id',
        how='left'
    )
    item_detail = item_detail.merge(
        sellers[['seller_id', 'seller_city', 'seller_state']],
        on='seller_id',
        how='left'
    )

    # Standardize column naming conventions to match your PRD
    item_detail.rename(columns={
        'product_description_lenght': 'product_description_length'
    }, inplace=True)

    # Save to database
    item_detail.to_sql('item_detail', conn, if_exists='replace', index=False)
    print(' -> Table [item_detail] engineered successfully.')

    # ==========================================
    # STEP 4: LOAD ORIGINAL COMPACT RAW TABLES AS BACKUP
    # ==========================================
    print('📂 Seeding raw tables as foundational architecture backups...')
    # Keeping raw tables for edge-case drill downs if necessary
    orders.to_sql('raw_orders', conn, if_exists='replace', index=False)
    reviews.to_sql('raw_reviews', conn, if_exists='replace', index=False)
    payments.to_sql('raw_payments', conn, if_exists='replace', index=False)

    # ==========================================
    # STEP 5: PERFORMANCE INDEXING (Cloud-Ready optimization)
    # ==========================================
    print('⚡ Building system indexes for low-latency queries...')
    # order_summary indexing
    cursor.execute("CREATE UNIQUE INDEX idx_os_order_id ON order_summary (order_id);")
    cursor.execute("CREATE INDEX idx_os_cust_uid ON order_summary (customer_unique_id);")
    cursor.execute("CREATE INDEX idx_os_cust_state ON order_summary (customer_state);")
    
    # item_detail indexing
    cursor.execute("CREATE INDEX idx_id_order_id ON item_detail (order_id);")
    cursor.execute("CREATE INDEX idx_id_prod_id ON item_detail (product_id);")
    cursor.execute("CREATE INDEX idx_id_seller_id ON item_detail (seller_id);")
    cursor.execute("CREATE INDEX idx_id_cat ON item_detail (product_category_en);")
    
    conn.commit()
    conn.close()
    print('\n✨ [DATABASE CONSTRUCTED SUCCESSFULLY] The schema is now fully agent-ready!')

if __name__ == '__main__':
    create_optimized_db()