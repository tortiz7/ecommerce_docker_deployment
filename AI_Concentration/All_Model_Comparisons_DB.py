import pandas as pd
import numpy as np
import sqlite3
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
import tensorflow as tf
from tensorflow.keras import layers, Model

class FraudDetectionComparison:
    def __init__(self):
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        
    def load_data(self):
        conn = sqlite3.connect('db.sqlite3')
        self.data = pd.read_sql_query("SELECT * FROM account_stripemodel", conn)
        conn.close()
        
    def preprocess_data(self):
        print("Starting preprocessing...")
        processed = self.data.copy()
        
        # Fill NaN values in address fields first
        processed['address_country'] = processed['address_country'].fillna('Unknown')
        processed['address_state'] = processed['address_state'].fillna('Unknown')
        
        # Handle email domain
        processed['email'] = processed['email'].fillna('unknown@unknown.com')
        processed['email_domain'] = processed['email'].apply(lambda x: x.split('@')[1])
        
        # Calculate frequencies after handling NaN values
        processed['email_domain_freq'] = processed.groupby('email_domain')['id'].transform('count')
        processed['card_usage_count'] = processed.groupby('card_number')['id'].transform('count')
        processed['customer_transaction_count'] = processed.groupby('customer_id')['id'].transform('count')
        processed['country_freq'] = processed.groupby('address_country')['id'].transform('count')
        processed['state_freq'] = processed.groupby('address_state')['id'].transform('count')
        
        # Handle categorical variables
        categorical_cols = ['email_domain', 'address_country', 'address_state']
        for col in categorical_cols:
            processed[col] = self.label_encoder.fit_transform(processed[col])
        
        # Convert and clean exp_month and exp_year
        processed['exp_month'] = pd.to_numeric(processed['exp_month'], errors='coerce').fillna(1)
        processed['exp_year'] = pd.to_numeric(processed['exp_year'], errors='coerce').fillna(2024)
        
        self.features = [
            'card_usage_count', 
            'customer_transaction_count', 
            'email_domain_freq',
            'country_freq', 
            'state_freq',
            'email_domain', 
            'address_country', 
            'address_state',
            'exp_month', 
            'exp_year'
        ]
        
        print("\nFeature statistics:")
        print(processed[self.features].describe())
        print("\nChecking for NaN values in features:", processed[self.features].isnull().sum())
        
        return processed[self.features]
    
    def compare_models(self):
        print("Loading data...")
        self.load_data()
        
        print("Preprocessing data...")
        X = self.preprocess_data()
        X_scaled = self.scaler.fit_transform(X)
        
        print("\nShape of scaled data:", X_scaled.shape)
        print("Checking for NaN values in scaled data:", np.isnan(X_scaled).sum())
        
        # If there are any remaining NaN values, drop them
        if np.isnan(X_scaled).any():
            print("Removing any remaining NaN values...")
            mask = ~np.isnan(X_scaled).any(axis=1)
            X_scaled = X_scaled[mask]
            self.data = self.data[mask]
            print("Shape after removing NaN values:", X_scaled.shape)
        
        # 1. DBSCAN with different parameters
        print("\nRunning DBSCAN models...")
        dbscan_results = []
        eps_values = [0.3, 0.5, 0.7]
        min_samples_values = [3, 5, 7]
        
        for eps in eps_values:
            for min_samples in min_samples_values:
                try:
                    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
                    labels = dbscan.fit_predict(X_scaled)
                    n_outliers = sum(labels == -1)
                    dbscan_results.append({
                        'eps': eps,
                        'min_samples': min_samples,
                        'n_outliers': n_outliers
                    })
                    print(f"DBSCAN (eps={eps}, min_samples={min_samples}): {n_outliers} outliers")
                except Exception as e:
                    print(f"Error with DBSCAN (eps={eps}, min_samples={min_samples}): {str(e)}")
                    continue
        
        if not dbscan_results:
            print("No successful DBSCAN runs. Using default parameters...")
            dbscan = DBSCAN(eps=0.5, min_samples=5)
            dbscan_labels = dbscan.fit_predict(X_scaled)
        else:
            best_dbscan = min(dbscan_results, key=lambda x: abs(x['n_outliers'] - 20))
            print(f"\nBest DBSCAN parameters: eps={best_dbscan['eps']}, min_samples={best_dbscan['min_samples']}")
            final_dbscan = DBSCAN(eps=best_dbscan['eps'], min_samples=best_dbscan['min_samples'])
            dbscan_labels = final_dbscan.fit_predict(X_scaled)
        
        print("\nRunning Isolation Forest...")
        iso_forest = IsolationForest(contamination=0.01, random_state=42)
        iso_forest_labels = iso_forest.fit_predict(X_scaled)
        
        print("\nRunning Autoencoder...")
        autoencoder = self.create_autoencoder(X_scaled.shape[1])
        autoencoder.fit(X_scaled, X_scaled, epochs=50, batch_size=32, verbose=0)
        reconstructed = autoencoder.predict(X_scaled)
        mse = np.mean(np.power(X_scaled - reconstructed, 2), axis=1)
        threshold = np.percentile(mse, 99)
        autoencoder_outliers = mse > threshold
        
        results_df = pd.DataFrame({
            'DBSCAN': (dbscan_labels == -1).astype(int),
            'IsolationForest': (iso_forest_labels == -1).astype(int),
            'Autoencoder': autoencoder_outliers.astype(int)
        })
        
        results_df = pd.concat([self.data, results_df], axis=1)
        return results_df, pd.DataFrame(dbscan_results)
    
    def create_autoencoder(self, input_dim):
        input_layer = layers.Input(shape=(input_dim,))
        encoded = layers.Dense(32, activation='relu')(input_layer)
        encoded = layers.Dense(16, activation='relu')(encoded)
        encoded = layers.Dense(8, activation='relu')(encoded)
        
        decoded = layers.Dense(16, activation='relu')(encoded)
        decoded = layers.Dense(32, activation='relu')(decoded)
        decoded = layers.Dense(input_dim, activation='sigmoid')(decoded)
        
        autoencoder = Model(input_layer, decoded)
        autoencoder.compile(optimizer='adam', loss='mse')
        
        return autoencoder
    
    def analyze_results(self, results_df, dbscan_results):
        print("\nDBSCAN parameter testing results:")
        if len(dbscan_results) > 0:
            print(dbscan_results)
        else:
            print("No DBSCAN parameter testing results available")
        
        print("\nNumber of anomalies detected by each model:")
        for col in ['DBSCAN', 'IsolationForest', 'Autoencoder']:
            print(f"{col}: {results_df[col].sum()} anomalies")
        
        print("\nOverlap analysis:")
        for i in ['DBSCAN', 'IsolationForest', 'Autoencoder']:
            for j in ['DBSCAN', 'IsolationForest', 'Autoencoder']:
                if i < j:
                    overlap = results_df[(results_df[i] == 1) & (results_df[j] == 1)].shape[0]
                    print(f"Overlap between {i} and {j}: {overlap} cases")
        
        print("\nCharacteristics of flagged transactions:")
        for model in ['DBSCAN', 'IsolationForest', 'Autoencoder']:
            anomalies = results_df[results_df[model] == 1]
            if len(anomalies) > 0:
                print(f"\n{model} anomalies ({len(anomalies)} total):")
                print("Top countries:", anomalies['address_country'].value_counts().head())
                print("Top states:", anomalies['address_state'].value_counts().head())
                print("Top email domains:", anomalies['email'].apply(lambda x: x.split('@')[1]).value_counts().head())
                
                filename = f'{model.lower()}_anomalies.csv'
                anomalies.to_csv(filename, index=False)
                print(f"Saved details to {filename}")

if __name__ == "__main__":
    print("Starting fraud detection model comparison...")
    detector = FraudDetectionComparison()
    results_df, dbscan_results = detector.compare_models()
    detector.analyze_results(results_df, dbscan_results)