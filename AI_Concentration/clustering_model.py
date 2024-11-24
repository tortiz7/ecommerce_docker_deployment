import pandas as pd
import numpy as np
import sqlite3
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import DBSCAN

# Database connection and data loading
def load_data():
    conn = sqlite3.connect('db.sqlite3')
    query = "SELECT * FROM account_stripemodel"
    data = pd.read_sql_query(query, conn)
    print("\nColumns in the database:")
    print(data.columns.tolist())
    print("\nSample of data:")
    print(data.head())
    conn.close()
    return data

def preprocess_data(data):
    # Print data info
    print("\nDataset Info:")
    print(data.info())
    
    # Basic feature engineering that doesn't depend on specific columns
    print("\nStarting feature engineering...")
    
    # Email domain extraction (if email exists)
    if 'email' in data.columns:
        data['email_domain'] = data['email'].apply(lambda x: x.split('@')[-1])
    
    # Card user count (if card_number exists)
    if 'card_number' in data.columns and 'user_id' in data.columns:
        data['card_user_count'] = data.groupby('card_number')['user_id'].transform('count')
    
    # Customer ID count (if customer_id exists)
    if 'customer_id' in data.columns and 'user_id' in data.columns:
        data['customer_id_count'] = data.groupby('customer_id')['user_id'].transform('count')
    
    # Label encoding for categorical variables
    categorical_cols = [col for col in ['address_country', 'address_state', 'email_domain'] 
                       if col in data.columns]
    le = LabelEncoder()
    for col in categorical_cols:
        data[col] = le.fit_transform(data[col])
    
    print("\nFeatures after preprocessing:")
    print(data.columns.tolist())
    
    return data

def main():
    print("Loading data...")
    data = load_data()
    
    print("\nPreprocessing data...")
    processed_data = preprocess_data(data)
    
    # Define features based on available columns
    potential_features = [
        'card_user_count', 'customer_id_count',
        'address_country', 'address_state', 
        'exp_month', 'exp_year'
    ]
    
    # Only use features that exist in the processed data
    features = [f for f in potential_features if f in processed_data.columns]
    print("\nFinal features being used:")
    print(features)
    
    X = processed_data[features]
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Initial DBSCAN with basic parameters
    print("\nRunning DBSCAN...")
    dbscan = DBSCAN(eps=0.5, min_samples=5)
    clusters = dbscan.fit_predict(X_scaled)
    
    # Add predictions to original data
    processed_data['is_anomaly'] = (clusters == -1).astype(int)
    
    # Print results
    print("\nResults:")
    print(f"Total number of transactions: {len(processed_data)}")
    print(f"Number of anomalies detected: {sum(processed_data['is_anomaly'])}")
    print(f"Percentage of anomalies: {(sum(processed_data['is_anomaly'])/len(processed_data))*100:.2f}%")

if __name__ == "__main__":
    main()