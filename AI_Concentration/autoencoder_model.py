"""
E-commerce Fraud Detection - Autoencoder Model

This model uses a deep learning autoencoder approach to detect fraudulent transactions
in our e-commerce system. It compares with our Isolation Forest approach to demonstrate
relative performance.
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from datetime import datetime
from sklearn.metrics import f1_score, accuracy_score

class AutoencoderFraudDetector:
    def __init__(self, db_path='db.sqlite3', table_name='account_stripemodel'):
        self.db_path = db_path
        self.table_name = table_name
        self.autoencoder = None
        self.label_encoder = {}
        self.scaler = StandardScaler()
        self.threshold = None
        self.input_dim = None
        
    def connect_db(self):
        try:
            if not Path(self.db_path).exists():
                raise FileNotFoundError(f"Database file not found: {self.db_path}")
            
            conn = sqlite3.connect(self.db_path)
            print(f"Successfully connected to database: {self.db_path}")
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            raise
            
    def load_data(self):
        try:
            conn = self.connect_db()
            
            verify_query = f"""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='{self.table_name}';
            """
            if not pd.read_sql_query(verify_query, conn)['name'].tolist():
                raise ValueError(f"Table '{self.table_name}' not found in database")

            query = f"SELECT * FROM {self.table_name}"
            df = pd.read_sql_query(query, conn)
            print(f"\nLoaded {len(df)} records from {self.table_name}")
            
            conn.close()
            return df
            
        except Exception as e:
            print(f"Error loading data: {e}")
            raise
            
    def prepare_data(self, data):
        try:
            df = data.copy()
            
            # First, create all the features we need
            df['transactions_per_card'] = df.groupby('card_number')['id'].transform('count')
            df['users_per_card'] = df.groupby('card_number')['user_id'].transform('nunique')
            df['addresses_per_card'] = df.groupby('card_number')['address_zip'].transform('nunique')
            df['transactions_per_state'] = df.groupby('address_state')['id'].transform('count')
            df['transactions_per_zip'] = df.groupby('address_zip')['id'].transform('count')
            
            # Convert expiration dates
            df['exp_month'] = pd.to_numeric(df['exp_month'], errors='coerce').fillna(1)
            df['exp_year'] = pd.to_numeric(df['exp_year'], errors='coerce').fillna(2024)
            
            # Calculate months until expiration
            current_year = datetime.now().year
            current_month = datetime.now().month
            df['months_to_expiry'] = ((df['exp_year'] - current_year) * 12 + 
                                    df['exp_month'] - current_month)
            
            # Encode categorical features
            categorical_columns = ['address_state', 'address_city', 'address_country', 'address_zip']
            for column in categorical_columns:
                if column in df.columns:
                    if column not in self.label_encoder:
                        self.label_encoder[column] = LabelEncoder()
                    df[column] = self.label_encoder[column].fit_transform(df[column].astype(str))
            
            # Drop unnecessary columns after feature creation
            cols_to_drop = ['id', 'card_id', 'customer_id', 'email', 'name_on_card', 
                           'card_number', 'user_id']
            df = df.drop([col for col in cols_to_drop if col in df.columns], axis=1)
            
            # Handle missing values
            df = df.fillna(df.mean())
            
            # Normalize
            df = pd.DataFrame(self.scaler.fit_transform(df), columns=df.columns)
            
            print("\nPrepared features:", df.columns.tolist())
            print("Data shape:", df.shape)
            
            return df
            
        except Exception as e:
            print(f"Error in data preparation: {e}")
            print("Available columns:", data.columns.tolist())
            raise
            
    def build_model(self, input_dim):
        input_layer = Input(shape=(input_dim,))
    
        # Encoder
        encoded = Dense(12, activation='relu')(input_layer)
        encoded = Dense(24, activation='relu')(encoded)
        encoded = Dropout(0.2)(encoded)
        encoded = Dense(12, activation='relu')(encoded)
        
        # Bottleneck
        bottleneck = Dense(4, activation='relu')(encoded)
        
        # Decoder
        decoded = Dense(12, activation='relu')(bottleneck)
        decoded = Dense(24, activation='relu')(decoded)
        decoded = Dropout(0.2)(decoded)
        decoded = Dense(12, activation='relu')(decoded)
        decoded = Dense(input_dim, activation='sigmoid')(decoded)
        
        # Create and compile model
        autoencoder = Model(inputs=input_layer, outputs=decoded)
        autoencoder.compile(optimizer='adam', 
                      loss='mse',
                      metrics=['mae', 'mse', 'accuracy'])  # Added accuracy metric
        return autoencoder
        
    def fit(self, data=None):
        try:
            if data is None:
             data = self.load_data()
        
            prepared_data = self.prepare_data(data)
            
            train_data, test_data = train_test_split(prepared_data, test_size=0.2, random_state=42)
            
            self.input_dim = train_data.shape[1]
            self.autoencoder = self.build_model(self.input_dim)
            
            early_stopping = EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True,
                min_delta=0.001
            )
            
            history = self.autoencoder.fit(
                train_data, train_data,
                epochs=100,
                batch_size=64,
                validation_split=0.2,
                shuffle=True,
                callbacks=[early_stopping],
                verbose=1
            )
            
            # Calculate reconstruction error and predictions
            predictions = self.autoencoder.predict(test_data)
            mse = np.mean(np.power(test_data - predictions, 2), axis=1)
            self.threshold = np.percentile(mse, 95)
            
            # Calculate binary predictions for F1 score
            binary_predictions = (mse > self.threshold).astype(int)
            
            # Assume anomalies in test set based on threshold
            assumed_true = (np.mean(np.power(test_data - test_data.mean(), 2), axis=1) > self.threshold).astype(int)
            
            # Calculate F1 score
            f1 = f1_score(assumed_true, binary_predictions)
            final_accuracy = history.history['accuracy'][-1]
            val_accuracy = history.history['val_accuracy'][-1]
            
            print("\nTraining completed:")
            print(f"Final loss: {history.history['loss'][-1]:.4f}")
            print(f"Final training accuracy: {final_accuracy:.4f}")
            print(f"Final validation accuracy: {val_accuracy:.4f}")
            print(f"F1 Score: {f1:.4f}")
            print(f"Threshold set at: {self.threshold:.4f}")
            
            # Store metrics for later use
            self.metrics = {
                'final_loss': history.history['loss'][-1],
                'final_accuracy': final_accuracy,
                'val_accuracy': val_accuracy,
                'f1_score': f1,
                'threshold': self.threshold
            }

        except Exception as e:
            print(f"Error in model training: {e}")
        raise
            
    def predict(self, data=None):
        try:
            if data is None:
                data = self.load_data()
            
            original_data = data.copy()
            prepared_data = self.prepare_data(data)
            
            predictions = self.autoencoder.predict(prepared_data)
            mse = np.mean(np.power(prepared_data - predictions, 2), axis=1)
            
            original_data['fraud_flag'] = (mse > self.threshold).astype(int)
            original_data['anomaly_score'] = mse
            
            return original_data[original_data['fraud_flag'] == 1]
            
        except Exception as e:
            print(f"Error in prediction: {e}")
            raise

if __name__ == "__main__":
    try:
        print("Initializing Autoencoder Fraud Detection...")
        model = AutoencoderFraudDetector()
        
        print("\nTraining model...")
        model.fit()
        
        print("\nAnalyzing transactions...")
        fraudulent_transactions = model.predict()
        
        print("\nAutoencoder Fraud Detection Results:")
        print(f"Total transactions analyzed: {len(model.load_data())}")
        print(f"Suspicious transactions identified: {len(fraudulent_transactions)}")
        print(f"Fraud rate: {(len(fraudulent_transactions) / len(model.load_data()) * 100):.2f}%")
        
        fraudulent_transactions.to_csv('autoencoder_fraudulent_transactions.csv', index=False)
        print("\nResults saved to 'autoencoder_fraudulent_transactions.csv'")
        
    except Exception as e:
        print(f"Error in Autoencoder fraud detection: {e}")
        import traceback
        print("\nError details:")
        print(traceback.format_exc())
