"""
E-commerce Fraud Detection Model

This model integrates with our e-commerce application's SQLite database to detect potential 
credit card fraud in our transactions. It uses the Isolation Forest algorithm to identify 
anomalous transactions based on various patterns and behaviors.

The model analyzes transaction patterns, location data, and user behaviors to flag potentially 
fraudulent activities in our payment processing system.

Author: [Your Name]
Project: E-commerce AI Implementation - Fraud Detection Module
Date: November 2024
"""

# Import required libraries for data processing and machine learning
import pandas as pd  # For handling transaction data
import numpy as np   # For numerical operations
import sqlite3      # To connect to our e-commerce database
from pathlib import Path  # For handling database file paths
from sklearn.ensemble import IsolationForest  # Our main fraud detection algorithm
from sklearn.preprocessing import LabelEncoder, StandardScaler  # For data preprocessing
from sklearn.impute import SimpleImputer  # For handling missing transaction data
from datetime import datetime  # For processing card expiration dates

class FraudDetectionModel:
    def __init__(self, db_path='db.sqlite3', table_name='account_stripemodel'):
        """
        Initialize our fraud detection system with the database connection details.
        
        Parameters:
        - db_path: Path to our SQLite database (defaults to our main db.sqlite3)
        - table_name: The stripe transactions table (account_stripemodel in our case)
        """
        self.db_path = db_path
        self.table_name = table_name
        self.isolation_forest = None  # Will store our trained model
        self.label_encoder = {}      # For converting text data to numbers
        self.scaler = StandardScaler()  # For normalizing our numerical data
        self.imputer = SimpleImputer(strategy='most_frequent')  # For handling missing values

    def connect_db(self):
        """
        Connect to our e-commerce application's SQLite database.
        This is the same database where we store all our Stripe transaction data.
        """
        try:
            # Make sure our database file exists before trying to connect
            if not Path(self.db_path).exists():
                raise FileNotFoundError(f"Database file not found: {self.db_path}")
            
            conn = sqlite3.connect(self.db_path)
            print(f"Successfully connected to database: {self.db_path}")
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            raise

    def load_data(self):
        """
        Load our Stripe transaction data from the database.
        This pulls all records from our account_stripemodel table where we store
        credit card transactions processed through our payment system.
        """
        try:
            # Establish database connection
            conn = self.connect_db()
            
            # First, verify that our Stripe transactions table exists
            verify_query = f"""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='{self.table_name}';
            """
            if not pd.read_sql_query(verify_query, conn)['name'].tolist():
                raise ValueError(f"Table '{self.table_name}' not found in database")

            # Get and display our table structure for verification
            schema_query = f"PRAGMA table_info({self.table_name});"
            schema = pd.read_sql_query(schema_query, conn)
            print("\nTable schema:")
            print(schema)
            
            # Pull all transaction records from our database
            query = f"SELECT * FROM {self.table_name}"
            df = pd.read_sql_query(query, conn)
            print(f"\nLoaded {len(df)} records from {self.table_name}")
            
            conn.close()
            
            # Convert expiration dates to numbers - they're stored as varchar in our db
            # but need to be numerical for the fraud detection analysis
            df['exp_month'] = pd.to_numeric(df['exp_month'], errors='coerce')
            df['exp_year'] = pd.to_numeric(df['exp_year'], errors='coerce')
            
            # Show info about our loaded data
            print("\nData info after loading:")
            print(df.info())
            
            return df
            
        except Exception as e:
            print(f"Error loading data: {e}")
            raise
    
    def extract_features(self, data):
        """
        Create features for fraud detection from our transaction data.
        
        This is where we look for patterns that might indicate fraud, such as:
        - Multiple cards being used by the same customer
        - Unusual transaction patterns
        - Multiple shipping addresses for the same card
        - Suspicious email patterns
        - Multiple users sharing the same card
        """
        try:
            features = data.copy()
            
            # Look for suspicious transaction patterns
            features['transactions_per_card'] = features.groupby('card_number')['id'].transform('count')
            features['transactions_per_customer'] = features.groupby('customer_id')['id'].transform('count')
            
            # Check for location-based suspicious patterns
            features['transactions_per_state'] = features.groupby('address_state')['id'].transform('count')
            features['transactions_per_zip'] = features.groupby('address_zip')['id'].transform('count')
            
            # Analyze email domains (fraudsters often use similar email providers)
            features['email_domain'] = features['email'].fillna('unknown').apply(
                lambda x: str(x).split('@')[1] if '@' in str(x) else 'unknown'
            )
            features['email_domain_freq'] = features.groupby('email_domain')['id'].transform('count')
            
            # Look for customers using multiple cards (potential card testing)
            features['cards_per_customer'] = features.groupby('customer_id')['card_number'].transform('nunique')
            
            # Check card expiration patterns
            current_year = datetime.now().year
            features['exp_month'] = pd.to_numeric(features['exp_month'], errors='coerce').fillna(1)
            features['exp_year'] = pd.to_numeric(features['exp_year'], errors='coerce').fillna(current_year)
            features['card_expiry_months'] = ((features['exp_year'] - current_year) * 12 + features['exp_month'])
            
            # Look for cards being used with multiple shipping addresses
            features['addresses_per_card'] = features.groupby('card_number')['address_zip'].transform('nunique')
            
            # Check for cards being used by multiple user accounts
            features['users_per_card'] = features.groupby('card_number')['user_id'].transform('nunique')
            features['cards_per_user'] = features.groupby('user_id')['card_number'].transform('nunique')
            
            # Remove fields we don't need for fraud detection
            cols_to_drop = ['id', 'email', 'card_id', 'customer_id', 'name_on_card']
            features = features.drop([col for col in cols_to_drop if col in features.columns], axis=1)
            
            print("\nFeature info after extraction:")
            print(features.info())
            
            return features
            
        except Exception as e:
            print(f"Error in feature extraction: {e}")
            raise

    def encode_categoricals(self, features):
        """
        Convert all our text-based data into numerical format for the fraud detection model.
        
        We need to convert things like:
        - State names
        - City names
        - Email domains
        - Card numbers
        - ZIP codes
        into numerical values because our fraud detection algorithm only works with numbers.
        """
        try:
            # List all the text-based fields we need to convert
            categorical_columns = ['address_state', 'address_city', 'address_country', 
                                 'email_domain', 'card_number', 'address_zip']
            
            for column in categorical_columns:
                if column in features.columns:
                    # Fill any missing values with 'unknown' before conversion
                    features[column] = features[column].fillna('unknown')
                    
                    # Create a new encoder if we haven't seen this field before
                    if column not in self.label_encoder:
                        self.label_encoder[column] = LabelEncoder()
                        features[column] = self.label_encoder[column].fit_transform(features[column].astype(str))
                    else:
                        # Use existing encoder for consistent number assignment
                        features[column] = self.label_encoder[column].transform(features[column].astype(str))
            
            print("\nFeature info after encoding:")
            print(features.info())
            
            return features
            
        except Exception as e:
            print(f"Error in categorical encoding: {e}")
            raise
    
    def prepare_features(self, data):
        """
        Prepare our transaction data for fraud detection analysis.
        
        This method:
        1. Creates fraud detection features from our transaction data
        2. Converts all text data to numbers
        3. Handles any missing values
        4. Scales all numbers to be in similar ranges
        """
        try:
            print("\nExtracting features...")
            features = self.extract_features(data)
            
            print("Encoding categorical variables...")
            features = self.encode_categoricals(features)
            
            print("Handling missing values...")
            # Fill in any missing values using the most common value for that field
            features = pd.DataFrame(self.imputer.fit_transform(features), columns=features.columns)
            
            print("Scaling numerical features...")
            # Scale all numbers to similar ranges so larger numbers don't dominate the analysis
            numerical_features = features.select_dtypes(include=['float64', 'int64']).columns
            features[numerical_features] = self.scaler.fit_transform(features[numerical_features])
            
            # Final check for any remaining missing values
            if features.isnull().any().any():
                print("\nWarning: NaN values still present after preparation:")
                print(features.isnull().sum()[features.isnull().sum() > 0])
            
            return features
            
        except Exception as e:
            print(f"Error in feature preparation: {e}")
            raise
    
    def fit(self, data=None):
        """
        Train our fraud detection model on our transaction data.
        
        We use the Isolation Forest algorithm which is good at finding unusual patterns
        in our transaction data that might indicate fraud.
        """
        try:
            if data is None:
                data = self.load_data()
            
            features = self.prepare_features(data)
            
            print("\nTraining Isolation Forest model...")
            # Initialize our fraud detection model with these parameters:
            # - contamination=0.01: we expect about 1% of transactions might be fraudulent
            # - n_estimators=200: use 200 trees for better accuracy
            # - bootstrap=True: use random sampling to make the model more robust
            self.isolation_forest = IsolationForest(
                contamination=0.01,
                max_samples='auto',
                n_estimators=200,
                max_features=1.0,
                bootstrap=True,
                n_jobs=-1,  # Use all CPU cores for faster processing
                random_state=42  # For consistent results
            )
            
            self.isolation_forest.fit(features)
            print("Model training completed successfully")
            
        except Exception as e:
            print(f"Error in model fitting: {e}")
            raise
    
    def predict(self, data=None):
        """
        Analyze our transactions and identify potentially fraudulent ones.
        
        Returns a DataFrame containing only the transactions that our model
        flags as potentially fraudulent.
        """
        try:
            if data is None:
                data = self.load_data()
            
            features = self.prepare_features(data)
            
            # Get fraud predictions and anomaly scores
            predictions = self.isolation_forest.predict(features)
            scores = self.isolation_forest.score_samples(features)
            
            # Add fraud flags and scores to our transaction data
            # -1 from predict() means fraudulent, convert to 1 for clarity
            data['fraud_flag'] = np.where(predictions == -1, 1, 0)
            data['anomaly_score'] = scores
            
            # Return only the suspicious transactions
            return data[data['fraud_flag'] == 1]
            
        except Exception as e:
            print(f"Error in prediction: {e}")
            raise

    def analyze_flagged_transactions(self, fraudulent_transactions):
        """
        Analyze why specific transactions were flagged as potentially fraudulent.
        
        This method helps us understand exactly what patterns triggered the fraud flags,
        which is useful for:
        - Explaining flags to our customer service team
        - Tuning the model's sensitivity
        - Identifying new fraud patterns in our system
        """
        try:
            # Get all our transaction data for comparison
            all_data = self.load_data()
            
            # List of numerical patterns we want to analyze
            numerical_features = [
                'transactions_per_card',     # How many times each card is used
                'transactions_per_customer', # Transactions per customer
                'transactions_per_state',    # Geographic patterns
                'transactions_per_zip',      # Local area patterns
                'email_domain_freq',         # Suspicious email patterns
                'cards_per_customer',        # Multiple cards per customer
                'card_expiry_months',        # Expiration date patterns
                'addresses_per_card',        # Multiple shipping addresses
                'users_per_card',           # Cards shared between accounts
                'cards_per_user'            # Users with multiple cards
            ]
            
            # Calculate statistics for each pattern
            stats = {}
            for feature in numerical_features:
                # If the feature doesn't exist yet, create it
                if feature not in all_data.columns:
                    if feature == 'transactions_per_card':
                        all_data[feature] = all_data.groupby('card_number')['id'].transform('count')
                    elif feature == 'transactions_per_customer':
                        all_data[feature] = all_data.groupby('customer_id')['id'].transform('count')
                    elif feature == 'transactions_per_state':
                        all_data[feature] = all_data.groupby('address_state')['id'].transform('count')
                    elif feature == 'transactions_per_zip':
                        all_data[feature] = all_data.groupby('address_zip')['id'].transform('count')
                    elif feature == 'email_domain_freq':
                        all_data['email_domain'] = all_data['email'].apply(lambda x: str(x).split('@')[1] if '@' in str(x) else 'unknown')
                        all_data[feature] = all_data.groupby('email_domain')['id'].transform('count')
                    elif feature == 'cards_per_customer':
                        all_data[feature] = all_data.groupby('customer_id')['card_number'].transform('nunique')
                    elif feature == 'card_expiry_months':
                        current_year = datetime.now().year
                        all_data['exp_month'] = pd.to_numeric(all_data['exp_month'], errors='coerce').fillna(1)
                        all_data['exp_year'] = pd.to_numeric(all_data['exp_year'], errors='coerce').fillna(current_year)
                        all_data[feature] = ((all_data['exp_year'] - current_year) * 12 + all_data['exp_month'])
                    elif feature == 'addresses_per_card':
                        all_data[feature] = all_data.groupby('card_number')['address_zip'].transform('nunique')
                    elif feature == 'users_per_card':
                        all_data[feature] = all_data.groupby('card_number')['user_id'].transform('nunique')
                    elif feature == 'cards_per_user':
                        all_data[feature] = all_data.groupby('user_id')['card_number'].transform('nunique')
                
                # Calculate average and standard deviation for normal vs fraudulent transactions
                stats[feature] = {
                    'normal_mean': all_data[~all_data.index.isin(fraudulent_transactions.index)][feature].mean(),
                    'normal_std': all_data[~all_data.index.isin(fraudulent_transactions.index)][feature].std(),
                    'fraud_mean': all_data[all_data.index.isin(fraudulent_transactions.index)][feature].mean(),
                    'fraud_std': all_data[all_data.index.isin(fraudulent_transactions.index)][feature].std()
                }
            
            # Analyze patterns in location data and other categorical fields
            categorical_features = ['address_state', 'address_city', 'address_country']
            cat_stats = {}
            for feature in categorical_features:
                # Compare frequency of values in normal vs fraudulent transactions
                normal_counts = all_data[~all_data.index.isin(fraudulent_transactions.index)][feature].value_counts(normalize=True)
                fraud_counts = all_data[all_data.index.isin(fraudulent_transactions.index)][feature].value_counts(normalize=True)
                
                # Flag values that appear much more often in fraudulent transactions
                cat_stats[feature] = {
                    'unusual_values': [
                        value for value in fraud_counts.index
                        if fraud_counts[value] > 2 * normal_counts.get(value, 0)  # Values twice as common in fraud
                    ]
                }
            
            return {
                'numerical_statistics': stats,          # Statistical analysis of patterns
                'categorical_patterns': cat_stats,      # Unusual location patterns
                'total_flagged': len(fraudulent_transactions),  # Total suspicious transactions
                'flagged_percentage': (len(fraudulent_transactions) / len(all_data)) * 100  # Fraud rate
            }
            
        except Exception as e:
            print(f"Error in fraud analysis: {e}")
            raise

    def evaluate_model(self, data=None, predictions=None):
        """
        Evaluate how well our fraud detection model is performing.
        
        This checks for specific suspicious patterns in our transaction data:
        - Customers with lots of different cards
        - Cards used with multiple shipping addresses
        - Cards being used very frequently
        - Cards shared between multiple user accounts
        """
        try:
            if data is None:
                data = self.load_data()
            if predictions is None:
                predictions = self.predict(data)
            
            # Calculate basic fraud detection statistics
            total_transactions = len(data)
            flagged_transactions = len(predictions)
            fraud_rate = (flagged_transactions / total_transactions) * 100
            
            # Check for specific suspicious patterns
            suspicious_patterns = {
                # Flag customers with more than 3 cards
                'multiple_cards_per_customer': len(data[data.groupby('customer_id')['card_number'].transform('nunique') > 3]),
                
                # Flag cards used with more than 2 shipping addresses
                'multiple_addresses': len(data[data.groupby('card_number')['address_zip'].transform('nunique') > 2]),
                
                # Flag cards used more than 10 times
                'high_frequency_cards': len(data[data.groupby('card_number')['id'].transform('count') > 10]),
                
                # Flag cards used by multiple user accounts
                'multiple_users_per_card': len(data[data.groupby('card_number')['user_id'].transform('nunique') > 1])
            }
            
            return {
                'total_transactions': total_transactions,
                'flagged_transactions': flagged_transactions,
                'fraud_rate': fraud_rate,
                'suspicious_patterns': suspicious_patterns
            }
            
        except Exception as e:
            print(f"Error in model evaluation: {e}")
            raise

# Main execution block - this is where we run our fraud detection analysis
if __name__ == "__main__":
    try:
        # Initialize our fraud detection model
        print("Initializing fraud detection system...")
        model = FraudDetectionModel()
        
        # Train the model on our transaction data
        print("Training model...")
        model.fit()
        
        # Look for suspicious transactions
        print("\nAnalyzing transactions for potential fraud...")
        fraudulent_transactions = model.predict()
        
        # Evaluate the results
        print("\nEvaluating detection results...")
        evaluation = model.evaluate_model()
        
        # Print summary of findings
        print(f"\nFraud Detection Summary:")
        print(f"Total transactions analyzed: {evaluation['total_transactions']}")
        print(f"Suspicious transactions identified: {evaluation['flagged_transactions']}")
        print(f"Fraud rate: {evaluation['fraud_rate']:.2f}%")
        print("\nSuspicious Patterns Detected:")
        for pattern, count in evaluation['suspicious_patterns'].items():
            print(f"{pattern}: {count} cases")
        
        # Perform detailed analysis of flagged transactions
        print("\nAnalyzing suspicious transactions in detail...")
        analysis = model.analyze_flagged_transactions(fraudulent_transactions)
        
        # Print detailed analysis results
        print("\nDetailed Analysis of Suspicious Transactions:")
        print(f"\nTotal flagged transactions: {analysis['total_flagged']} ({analysis['flagged_percentage']:.2f}%)")
        
        # Compare normal vs suspicious transaction patterns
        print("\nPattern Analysis (Normal vs Suspicious Transactions):")
        for feature, stats in analysis['numerical_statistics'].items():
            print(f"\n{feature}:")
            print(f"  Normal transactions: mean={stats['normal_mean']:.2f}, std={stats['normal_std']:.2f}")
            print(f"  Suspicious transactions: mean={stats['fraud_mean']:.2f}, std={stats['fraud_std']:.2f}")
        
        # Report any unusual geographic or categorical patterns
        print("\nUnusual Patterns in Location Data:")
        for feature, stats in analysis['categorical_patterns'].items():
            if stats['unusual_values']:
                print(f"\n{feature} unusual patterns:")
                for value in stats['unusual_values']:
                    print(f"  - {value}")
        
        # Add detailed analysis to our flagged transactions report
        fraudulent_transactions['anomaly_details'] = 'Flagged by Isolation Forest'
        
        # Calculate how unusual each pattern is in the suspicious transactions
        for feature, stats in analysis['numerical_statistics'].items():
            if feature in fraudulent_transactions.columns:
                mean_diff = abs(fraudulent_transactions[feature] - stats['normal_mean'])
                std_diff = mean_diff / stats['normal_std']
                fraudulent_transactions[f'{feature}_std_deviation'] = std_diff
        
        # Save the detailed fraud analysis report
        fraudulent_transactions.to_csv('fraudulent_transactions_with_analysis.csv', index=False)
        print("\nDetailed fraud analysis has been saved to 'fraudulent_transactions_with_analysis.csv'")
        
    except Exception as e:
        print(f"Error in fraud detection process: {e}")
        import traceback
        print("\nError details:")
        print(traceback.format_exc())