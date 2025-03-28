import logging
import requests
import pandas as pd
import io
import duckdb

# API Details
API_URL = "https://my.api.mockaroo.com/sales_data"
API_KEY = "ec446b50"  # API Key from cURL command
HEADERS = {"X-API-Key": API_KEY}  # Required header

# DuckDB database file
DB_PATH = "ecommerce.db"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def fetch_and_load_data():
    """Fetch data from API and load it into DuckDB tables."""
    try:
        logging.info("Fetching data from API...")
        response = requests.get(API_URL, headers=HEADERS)
        response.raise_for_status()  # Raise error for bad responses (4xx, 5xx)
        
        # Convert CSV string to Pandas DataFrame
        csv_data = io.StringIO(response.text)
        df = pd.read_csv(csv_data)
        
        # Trim spaces from column names (if any)
        df.rename(columns=lambda x: x.strip(), inplace=True)

        with duckdb.connect(DB_PATH) as conn:
            # Ensure schema exists
            conn.execute("CREATE SCHEMA IF NOT EXISTS raw")

            # Create tables if not exist
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

            # Insert data into tables
            logging.info("Loading data into DuckDB...")
            
            # Load Clients Table
            clients_df = df[['client_id', 'nom_client', 'email', 'ville', 'pays', 'genre']].drop_duplicates()
            conn.execute("DELETE FROM raw.clients")  # Clear old data
            conn.register("clients_df", clients_df)
            conn.execute("INSERT INTO raw.clients SELECT * FROM clients_df")

            # Load Commandes Table
            commandes_df = df[['commande_id', 'client_id', 'date_commande', 'montant_total', 'statut']].drop_duplicates()
            conn.execute("DELETE FROM raw.commandes")
            conn.register("commandes_df", commandes_df)
            conn.execute("INSERT INTO raw.commandes SELECT * FROM commandes_df")

            # Load Produits Table
            produits_df = df[['produit_id', 'nom_produit', 'prix_unitaire', 'Stock']].drop_duplicates()
            conn.execute("DELETE FROM raw.produits")
            conn.register("produits_df", produits_df)
            conn.execute("INSERT INTO raw.produits SELECT * FROM produits_df")

            # Load Details Commandes Table
            details_df = df[['commande_id', 'produit_id', 'quantite', 'prix_unitaire', 'sous_total']].drop_duplicates()
            conn.execute("DELETE FROM raw.details_commandes")
            conn.register("details_df", details_df)
            conn.execute("INSERT INTO raw.details_commandes SELECT * FROM details_df")

            # Load Paiements Table
            paiements_df = df[['paiement_id', 'commande_id', 'mode_paiement', 'statut_paiement', 'date_paiement']].drop_duplicates()
            conn.execute("DELETE FROM raw.paiements")
            conn.register("paiements_df", paiements_df)
            conn.execute("INSERT INTO raw.paiements SELECT * FROM paiements_df")

            logging.info("Data successfully loaded into DuckDB.")

    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed: {e}")
    except duckdb.DataError as e:
        logging.error(f"DuckDB error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

def transform_data():
    """Apply transformations and create refined tables from raw data."""
    try:
        logging.info("Starting data transformation in refined layer...")
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
            logging.info("Sales summary transformation completed successfully.")
            
            # Transformation 2: Product performance analysis
            conn.execute("""
                CREATE OR REPLACE TABLE refined.product_performance AS
                SELECT 
                    p.produit_id,
                    p.nom_produit,
                    SUM(dc."quantité") AS totale_quantite_par_produit,
                    SUM(dc.sous_total) AS totale_revenue,
                    COUNT(DISTINCT dc.commande_id) AS nombre_commande
                FROM raw.produits p
                LEFT JOIN raw.details_commandes dc ON p.produit_id = dc.produit_id
                GROUP BY p.produit_id, p.nom_produit
            """)
            logging.info("Product performance transformation completed successfully.")

            logging.info("All data transformations in the refined layer have been completed.")
    except Exception as e:
        logging.error(f"Transformation error: {e}")



if __name__ == "__main__":
    fetch_and_load_data()
    transform_data()