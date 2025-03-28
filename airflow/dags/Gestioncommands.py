from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging
import requests
import pandas as pd
import io
from io import StringIO
import duckdb

# API Details
API_URL = "https://my.api.mockaroo.com/sales_data"
API_KEY = "ec446b50"  # API Key from cURL command
HEADERS = {"X-API-Key": API_KEY}  # Required header

# DuckDB database file
DB_PATH = "Db\ecommerce.db"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def fetch_data(**context):
    """Fetch data from API and push the CSV response string via XCom."""
    try:
        logging.info("Fetching data from API...")
        response = requests.get(API_URL, headers=HEADERS)
        response.raise_for_status()  # Raise error for bad responses
        csv_content = response.text
        logging.info("Data fetched from API successfully.")

        # Push the CSV data to XCom so that downstream tasks can access it.
        context['ti'].xcom_push(key='csv_data', value=csv_content)
        logging.info("CSV data pushed to XCom.")
    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed: {e}")
        raise

def store_data(**context):
    """Retrieve CSV data from XCom and load it into DuckDB tables."""
    try:
        logging.info("Retrieving CSV data from XCom...")
        csv_content = context['ti'].xcom_pull(key='csv_data', task_ids='fetch_data')
        if not csv_content:
            raise ValueError("No CSV data found in XCom.")

        # Convert the CSV string to a DataFrame
        csv_data = io.StringIO(csv_content)
        df = pd.read_csv(csv_data)
        df.rename(columns=lambda x: x.strip(), inplace=True)

        with duckdb.connect(DB_PATH) as conn:
            # Create the raw schema if not exists
            conn.execute("CREATE SCHEMA IF NOT EXISTS raw")

            # Create tables if they do not exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw.clients (
                    client_id INT PRIMARY KEY,
                    nom_client TEXT,
                    email TEXT, 
                    ville TEXT,
                    pays TEXT, 
                    genre TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw.commandes (
                    commande_id INT PRIMARY KEY,
                    client_id INT, 
                    date_commande DATE, 
                    montant_total DECIMAL(10,2), 
                    statut TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw.produits (
                    produit_id INT PRIMARY KEY, 
                    nom_produit TEXT, 
                    prix_unitaire DECIMAL(10,2), 
                    stock INT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw.details_commandes (
                    commande_id INT, 
                    produit_id INT, 
                    quantite INT, 
                    prix_unitaire DECIMAL(10,2), 
                    sous_total DECIMAL(10,2)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw.paiements (
                    paiement_id INT PRIMARY KEY, 
                    commande_id INT, 
                    mode_paiement TEXT, 
                    statut_paiement TEXT, 
                    date_paiement DATE
                )
            """)

            logging.info("Inserting data into DuckDB tables...")

            # Insert data into the clients table
            clients_df = df[['client_id', 'nom_client', 'email', 'ville', 'pays', 'genre']].drop_duplicates()
            conn.execute("DELETE FROM raw.clients")
            conn.register("clients_df", clients_df)
            conn.execute("INSERT INTO raw.clients SELECT * FROM clients_df")

            # Insert data into the commandes table
            commandes_df = df[['commande_id', 'client_id', 'date_commande', 'montant_total', 'statut']].drop_duplicates()
            conn.execute("DELETE FROM raw.commandes")
            conn.register("commandes_df", commandes_df)
            conn.execute("INSERT INTO raw.commandes SELECT * FROM commandes_df")

            # Insert data into the produits table
            produits_df = df[['produit_id', 'nom_produit', 'prix_unitaire', 'Stock']].drop_duplicates(subset=['produit_id'])
            conn.execute("DELETE FROM raw.produits")
            conn.register("produits_df", produits_df)
            conn.execute("INSERT INTO raw.produits SELECT * FROM produits_df")

            # Insert data into the details_commandes table
            details_df = df[['commande_id', 'produit_id', 'quantite', 'prix_unitaire', 'sous_total']].drop_duplicates()
            conn.execute("DELETE FROM raw.details_commandes")
            conn.register("details_df", details_df)
            conn.execute("INSERT INTO raw.details_commandes SELECT * FROM details_df")

            # Insert data into the paiements table
            paiements_df = df[['paiement_id', 'commande_id', 'mode_paiement', 'statut_paiement', 'date_paiement']].drop_duplicates()
            conn.execute("DELETE FROM raw.paiements")
            conn.register("paiements_df", paiements_df)
            conn.execute("INSERT INTO raw.paiements SELECT * FROM paiements_df")

            logging.info("Data successfully stored into DuckDB.")

    except Exception as e:
        logging.error(f"Error during storing data: {e}")
        raise

def transform_data():
    """Apply transformations and create refined tables from the raw data in DuckDB."""
    try:
        logging.info("Starting data transformation...")
        with duckdb.connect(DB_PATH) as conn:
            # Create the refined schema if it doesn't exist
            conn.execute("CREATE SCHEMA IF NOT EXISTS refined")
            
            # Transformation 1: Sales summary by client
            conn.execute("""
                CREATE OR REPLACE TABLE refined.sales_summary AS
                SELECT 
                    c.client_id, 
                    c.nom_client, 
                    COUNT(co.commande_id) AS totale_commandes, 
                    SUM(co.montant_total) AS totale_ventes
                FROM raw.clients c
                LEFT JOIN raw.commandes co ON c.client_id = co.client_id
                GROUP BY c.client_id, c.nom_client
            """)
            logging.info("Sales summary transformation completed.")

            # Transformation 2: Product performance analysis
            conn.execute("""
                CREATE OR REPLACE TABLE refined.product_performance AS
                SELECT 
                    p.produit_id,
                    p.nom_produit,
                    SUM(dc.quantite) AS totale_quantite_par_produit,
                    SUM(dc.sous_total) AS totale_revenue,
                    COUNT(DISTINCT dc.commande_id) AS nombre_commande
                FROM raw.produits p
                LEFT JOIN raw.details_commandes dc ON p.produit_id = dc.produit_id
                GROUP BY p.produit_id, p.nom_produit
            """)
            logging.info("Product performance transformation completed.")

            logging.info("All data transformations in the refined layer have been completed.")

    except Exception as e:
        logging.error(f"Transformation error: {e}")
        raise

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2023, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

# Define the DAG
with DAG(
    'Etl_pipeline_order_management',
    default_args=default_args,
    description='ETL pipeline using XCom to pass data between tasks',
    schedule_interval=timedelta(minutes=3),
    catchup=False,
) as dag:

    fetch_task = PythonOperator(
        task_id='fetch_data',
        python_callable=fetch_data,
        provide_context=True
    )

    store_task = PythonOperator(
        task_id='store_data',
        python_callable=store_data,
        provide_context=True
    )

    transform_task = PythonOperator(
        task_id='transform_data',
        python_callable=transform_data
    )

    # Set task dependencies:
    # fetch_data -> store_data -> transform_data
    fetch_task >> store_task >> transform_task
