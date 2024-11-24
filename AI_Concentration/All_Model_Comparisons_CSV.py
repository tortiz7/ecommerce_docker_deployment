import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import IsolationForest
from sklearn.metrics import silhouette_score
from sklearn.cluster import DBSCAN
import tensorflow as tf
from tensorflow.keras import layers, Model

class EnhancedFraudDetection:
    def __init__(self):
        # Initialize scalers and encoders for data preprocessing
        self.scaler = StandardScaler()  # For normalizing numerical features
        self.label_encoder = LabelEncoder()  # For encoding categorical variables
        
    def load_data(self):
        """Load and perform initial data validation"""
        print("Loading CSV data...")
        self.data = pd.read_csv('account_stripemodel_fraud_data.csv')
        print(f"Loaded {len(self.data)} records")
        print("\nColumns in dataset:", self.data.columns.tolist())
        
    def preprocess_data(self):
        """
        Comprehensive data preprocessing including:
        - Feature engineering
        - Missing value handling
        - Categorical encoding
        - Fraud-indicative feature creation
        """
        print("\nPreprocessing data...")
        processed = self.data.copy()
        
        # Handle missing values
        processed['address_country'] = processed['address_country'].fillna('Unknown')
        processed['address_state'] = processed['address_state'].fillna('Unknown')
        processed['email'] = processed['email'].fillna('unknown@unknown.com')
        
        # Feature Engineering
        
        # Extract and analyze email domains
        processed['email_domain'] = processed['email'].apply(lambda x: x.split('@')[1])
        processed['email_domain_freq'] = processed.groupby('email_domain')['id'].transform('count')
        
        # Calculate usage patterns
        processed['card_usage_count'] = processed.groupby('card_number')['id'].transform('count')
        processed['customer_transaction_count'] = processed.groupby('customer_id')['id'].transform('count')
        
        # Location-based features
        processed['country_freq'] = processed.groupby('address_country')['id'].transform('count')
        processed['state_freq'] = processed.groupby('address_state')['id'].transform('count')
        
        # Fraud indicators: Multiple locations per customer
        processed['multiple_states'] = processed.groupby('customer_id')['address_state'].transform('nunique') > 1
        processed['multiple_countries'] = processed.groupby('customer_id')['address_country'].transform('nunique') > 1
        
        # Encode categorical variables
        categorical_cols = ['email_domain', 'address_country', 'address_state']
        for col in categorical_cols:
            processed[col] = self.label_encoder.fit_transform(processed[col])
        
        # Convert and clean card expiration dates
        processed['exp_month'] = pd.to_numeric(processed['exp_month'], errors='coerce').fillna(1)
        processed['exp_year'] = pd.to_numeric(processed['exp_year'], errors='coerce').fillna(2024)
        
        # Define features for model training
        self.features = [
            'card_usage_count',  # Frequency of card usage
            'customer_transaction_count',  # Customer activity level
            'email_domain_freq',  # Popularity of email domain
            'country_freq',  # Frequency of country in transactions
            'state_freq',  # Frequency of state in transactions
            'email_domain',  # Encoded email domain
            'address_country',  # Encoded country
            'address_state',  # Encoded state
            'exp_month',  # Card expiration month
            'exp_year',  # Card expiration year
            'multiple_states',  # Flag for multiple states per customer
            'multiple_countries'  # Flag for multiple countries per customer
        ]
        
        return processed[self.features]
    
    def optimize_isolation_forest(self, X_scaled):
        """
        Optimize Isolation Forest parameters using grid search
        Returns the best performing model configuration
        """
        print("\nOptimizing Isolation Forest...")
        # Define parameter grid
        param_grid = {
            'n_estimators': [100, 200, 300],  # Number of trees
            'contamination': [0.01, 0.02, 0.03],  # Expected percentage of anomalies
            'max_samples': ['auto', 100, 200]  # Samples to draw for each tree
        }
        
        best_score = float('-inf')
        best_params = None
        
        # Grid search with silhouette score optimization
        for n_estimators in param_grid['n_estimators']:
            for contamination in param_grid['contamination']:
                for max_samples in param_grid['max_samples']:
                    iso_forest = IsolationForest(
                        n_estimators=n_estimators,
                        contamination=contamination,
                        max_samples=max_samples,
                        random_state=42
                    )
                    labels = iso_forest.fit_predict(X_scaled)
                    
                    # Evaluate model quality using silhouette score
                    if len(set(labels)) > 1:
                        score = silhouette_score(X_scaled, labels)
                        if score > best_score:
                            best_score = score
                            best_params = {
                                'n_estimators': n_estimators,
                                'contamination': contamination,
                                'max_samples': max_samples
                            }
        
        print(f"Best Isolation Forest parameters: {best_params}")
        return IsolationForest(**best_params, random_state=42)
    
    def create_optimized_autoencoder(self, input_dim):
        """
        Create an optimized autoencoder with:
        - Dropout for regularization
        - L2 regularization to prevent overfitting
        - Optimal layer sizes for fraud detection
        """
        print("\nCreating optimized autoencoder...")
        input_layer = layers.Input(shape=(input_dim,))
        
        # Encoder layers with regularization
        encoded = layers.Dense(32, activation='relu', kernel_regularizer=tf.keras.regularizers.l2(0.01))(input_layer)
        encoded = layers.Dropout(0.2)(encoded)  # Prevent overfitting
        encoded = layers.Dense(16, activation='relu', kernel_regularizer=tf.keras.regularizers.l2(0.01))(encoded)
        encoded = layers.Dropout(0.2)(encoded)
        encoded = layers.Dense(8, activation='relu', kernel_regularizer=tf.keras.regularizers.l2(0.01))(encoded)
        
        # Decoder layers
        decoded = layers.Dense(16, activation='relu')(encoded)
        decoded = layers.Dropout(0.2)(decoded)
        decoded = layers.Dense(32, activation='relu')(decoded)
        decoded = layers.Dense(input_dim, activation='sigmoid')(decoded)
        
        autoencoder = Model(input_layer, decoded)
        autoencoder.compile(optimizer='adam', loss='mse')
        
        return autoencoder
    
    def run_comparison(self):
        self.load_data()
        X = self.preprocess_data()
        X_scaled = self.scaler.fit_transform(X)
        
        # Save preprocessed features for reference
        feature_stats = pd.DataFrame({
            'feature': self.features,
            'mean': X_scaled.mean(axis=0),
            'std': X_scaled.std(axis=0),
            'min': X_scaled.min(axis=0),
            'max': X_scaled.max(axis=0)
        })
        feature_stats.to_csv('feature_stats_fraud_data.csv', index=False)
        
        # 1. Optimized Isolation Forest
        iso_forest = self.optimize_isolation_forest(X_scaled)
        iso_forest_labels = iso_forest.fit_predict(X_scaled)
        
        # 2. Optimized Autoencoder
        autoencoder = self.create_optimized_autoencoder(X_scaled.shape[1])
        autoencoder.fit(X_scaled, X_scaled, 
                       epochs=100, 
                       batch_size=32, 
                       validation_split=0.2,
                       callbacks=[tf.keras.callbacks.EarlyStopping(patience=10)],
                       verbose=0)
        
        reconstructed = autoencoder.predict(X_scaled)
        mse = np.mean(np.power(X_scaled - reconstructed, 2), axis=1)
        threshold = np.percentile(mse, 98)  # Top 2% as anomalies
        autoencoder_outliers = mse > threshold
        
        # 3. DBSCAN (for comparison)
        dbscan = DBSCAN(eps=0.5, min_samples=3)
        dbscan_labels = dbscan.fit_predict(X_scaled)
        
        # Combine results
        results_df = pd.DataFrame({
            'DBSCAN': (dbscan_labels == -1).astype(int),
            'IsolationForest': (iso_forest_labels == -1).astype(int),
            'Autoencoder': autoencoder_outliers.astype(int)
        })
        
        # Add reconstruction error for autoencoder
        results_df['Autoencoder_Error'] = mse
        
        # Combine with original data
        full_results = pd.concat([self.data, results_df], axis=1)
        
        # Save detailed results for each model
        full_results[full_results['DBSCAN'] == 1].to_csv('fraud_data_dbscan_anomalies.csv', index=False)
        full_results[full_results['IsolationForest'] == 1].to_csv('fraud_data_iforest_anomalies.csv', index=False)
        full_results[full_results['Autoencoder'] == 1].to_csv('fraud_data_autoencoder_anomalies.csv', index=False)
        
        # Save combined results
        full_results.to_csv('fraud_data_all_model_results.csv', index=False)
        
        # Calculate and display metrics
        print("\nResults Summary:")
        print(f"Total records analyzed: {len(full_results)}")
        for model in ['DBSCAN', 'IsolationForest', 'Autoencoder']:
            anomalies = full_results[full_results[model] == 1]
            print(f"\n{model} Results:")
            print(f"Total anomalies detected: {len(anomalies)}")
            print(f"Unique countries: {anomalies['address_country'].nunique()}")
            print(f"Unique states: {anomalies['address_state'].nunique()}")
            print(f"Unique email domains: {anomalies['email'].apply(lambda x: x.split('@')[1]).nunique()}")
        
        # Calculate overlap
        print("\nModel Overlap Analysis:")
        for i in ['DBSCAN', 'IsolationForest', 'Autoencoder']:
            for j in ['DBSCAN', 'IsolationForest', 'Autoencoder']:
                if i < j:
                    overlap = len(full_results[(full_results[i] == 1) & (full_results[j] == 1)])
                    print(f"Overlap between {i} and {j}: {overlap} cases")

if __name__ == "__main__":
    print("Starting enhanced fraud detection comparison on fraud_data.csv...")
    detector = EnhancedFraudDetection()
    detector.run_comparison()