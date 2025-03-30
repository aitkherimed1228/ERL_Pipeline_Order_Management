import logging
import requests
import pandas as pd
import io
import duckdb
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator

# Détails de l'API
API_URL = "https://my.api.mockaroo.com/sales_data"
API_KEY = "ec446b50"  # Clé API
HEADERS = {"X-API-Key": API_KEY}

# Chemin vers la base DuckDB
DB_PATH = "airflow\Db\ecommerce.db"

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Fonctions définies
def fetch_data(**kwargs):
    """
    Récupère les données depuis l'API et retourne le contenu CSV.
    Cette valeur sera transmise via XCom.
    """
    try:
        logging.info("Fetching data from API...")
        response = requests.get(API_URL, headers=HEADERS, verify=False)
        response.raise_for_status()
        csv_content = response.text
        logging.info("Data fetched successfully.")
        return csv_content
    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed: {e}")
        raise

def store_data(csv_content):
    """Ajoute les nouvelles données à la table existante"""
    try:
        logging.info("Début du stockage incrémental...")
        
        # Préparation des données
        df = pd.read_csv(io.StringIO(csv_content))
        df = df.rename(columns=lambda x: x.strip())
        df["Datetime_ingestion"] = datetime.now()
        
        # Réordonner et filtrer les colonnes pour qu'elles correspondent à la définition de la table
        required_columns = [
            "client_id", "nom_client", "email", "ville", "pays", "genre",
            "commande_id", "date_commande", "montant_total", "statut",
            "produit_id", "nom_produit", "prix_unitaire", "quantite",
            "sous_total", "stock", "paiement_id", "mode_paiement",
            "statut_paiement", "date_paiement", "Datetime_ingestion"
        ]
        df = df[required_columns]

        with duckdb.connect(DB_PATH) as conn:
            # Création du schéma raw si nécessaire
            conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw.ecom_db (
                    client_id INTEGER,
                    nom_client TEXT,
                    email TEXT,
                    ville TEXT,
                    pays TEXT,
                    genre TEXT,
                    commande_id INTEGER PRIMARY KEY, 
                    date_commande DATE,
                    montant_total DECIMAL(10,2),
                    statut TEXT,
                    produit_id INTEGER,
                    nom_produit TEXT,
                    prix_unitaire DECIMAL(10,2),
                    quantite INTEGER,
                    sous_total DECIMAL(10,2),
                    stock INTEGER,
                    paiement_id INTEGER,
                    mode_paiement TEXT,
                    statut_paiement TEXT,
                    date_paiement DATE,
                    Datetime_ingestion TIMESTAMP
                )
            """)
            
            # Insertion seulement des nouvelles commandes
            conn.register("new_data", df)
            result = conn.execute("""
                INSERT INTO raw.ecom_db 
                SELECT * FROM new_data
                WHERE commande_id NOT IN (
                    SELECT commande_id FROM raw.ecom_db
                )
            """)
            
            logging.info(f"{result.rowcount} nouvelles commandes ajoutées")
    except Exception as e:
        logging.error(f"Erreur de stockage : {e}")
        raise

def load_refined():
    """Met à jour les tables transformées avec les nouvelles données"""
    try:
        logging.info("Mise à jour des tables transformées...")
        
        with duckdb.connect(DB_PATH) as conn:
            # Clients - Mise à jour incrémentale
            conn.execute("""
                CREATE TABLE IF NOT EXISTS refined.clients (
                    client_id INTEGER PRIMARY KEY,
                    nom_client TEXT,
                    email TEXT,
                    ville TEXT,
                    pays TEXT,
                    genre TEXT
                );
                
                INSERT INTO refined.clients
                SELECT 
                    client_id,
                    nom_client,
                    email,
                    ville,
                    pays,
                    genre
                FROM raw.ecom_db
                WHERE client_id NOT IN (
                    SELECT client_id FROM refined.clients
                )
            """)
            
            # Commandes - Mise à jour incrémentale
            conn.execute("""
                CREATE TABLE IF NOT EXISTS refined.commandes (
                    commande_id INTEGER PRIMARY KEY,
                    client_id INTEGER,
                    date_commande DATE,
                    montant_total DECIMAL(10,2),
                    statut TEXT
                );
                
                INSERT INTO refined.commandes
                SELECT 
                    commande_id,
                    client_id,
                    date_commande,
                    montant_total,
                    statut
                FROM raw.ecom_db
                WHERE commande_id NOT IN (
                    SELECT commande_id FROM refined.commandes
                )
            """)
            
            # DetailsCommandes - Mise à jour incrémentale
            conn.execute("""
                CREATE TABLE IF NOT EXISTS refined.details_commandes (
                    commande_id INT, 
                    produit_id INT, 
                    quantite INT, 
                    prix_unitaire DECIMAL(10,2), 
                    sous_total DECIMAL(10,2)
                );
                
                INSERT INTO refined.details_commandes
                SELECT 
                    commande_id, 
                    produit_id, 
                    quantite, 
                    prix_unitaire, 
                    sous_total
                FROM raw.ecom_db
                WHERE commande_id NOT IN (
                    SELECT commande_id FROM refined.details_commandes
                )
            """)
            
            # Produits - Mise à jour incrémentale
            conn.execute("""
                CREATE TABLE IF NOT EXISTS refined.produits (
                    produit_id INT PRIMARY KEY, 
                    nom_produit TEXT, 
                    prix_unitaire DECIMAL(10,2), 
                    stock INT
                );
                
                INSERT INTO refined.produits
                SELECT 
                    produit_id, 
                    nom_produit, 
                    prix_unitaire, 
                    stock
                FROM raw.ecom_db
                WHERE produit_id NOT IN (
                    SELECT produit_id FROM refined.produits
                )
            """)
            
            # Paiements - Mise à jour incrémentale
            conn.execute("""
                CREATE TABLE IF NOT EXISTS refined.paiements (
                    paiement_id INT PRIMARY KEY, 
                    commande_id INT, 
                    mode_paiement TEXT, 
                    statut_paiement TEXT, 
                    date_paiement DATE
                );
                
                INSERT INTO refined.paiements
                SELECT 
                    paiement_id, 
                    commande_id, 
                    mode_paiement, 
                    statut_paiement, 
                    date_paiement
                FROM raw.ecom_db
                WHERE paiement_id NOT IN (
                    SELECT paiement_id FROM refined.paiements
                )
            """)
        logging.info("Mise à jour des tables transformées terminée")
    except Exception as e:
        logging.error(f"Erreur de transformation : {e}")
        raise

# Définition du DAG et de ses arguments par défaut
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2025, 3, 30),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "ecommerce_data_pipeline",
    default_args=default_args,
    description="Pipeline pour charger les données depuis l'API, alimenter la table raw et mettre à jour les tables refined",
    schedule_interval= timedelta(minutes=1),
    catchup=False,
)

# Tâche 1 : Récupération des données
fetch_task = PythonOperator(
    task_id="fetch_data",
    python_callable=fetch_data,
    provide_context=True,
    dag=dag,
)

# Tâche 2 : Stockage incrémental dans la table raw
def task_store_data(**kwargs):
    ti = kwargs["ti"]
    csv_content = ti.xcom_pull(task_ids="fetch_data")
    store_data(csv_content)

store_task = PythonOperator(
    task_id="store_data",
    python_callable=task_store_data,
    provide_context=True,
    dag=dag,
)

# Tâche 3 : Chargement des données dans les tables refined
load_refined_task = PythonOperator(
    task_id="load_refined",
    python_callable=load_refined,
    dag=dag,
)

# Définition des dépendances
fetch_task >> store_task >> load_refined_task
